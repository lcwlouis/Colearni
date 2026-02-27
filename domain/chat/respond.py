"""Chat response orchestration with evidence verification."""

from __future__ import annotations

from adapters.db.documents import DocumentRow, get_document_by_id
from adapters.db.mastery import get_mastery_status
from adapters.embeddings.factory import build_embedding_provider
from adapters.llm.factory import build_graph_llm_client
from core.contracts import GraphLLMClient
from core.observability import (
    SPAN_KIND_CHAIN,
    observation_context,
    set_input_output,
    set_span_kind,
    start_span,
)
from core.schemas import (
    CITATION_LABEL_FROM_NOTES,
    AssistantDraft,
    AssistantResponseEnvelope,
    AssistantResponseKind,
    ChatRespondRequest,
    Citation,
    ConceptSwitchSuggestion,
    ConversationMeta,
    EvidenceItem,
    EvidenceSourceType,
    GroundingMode,
)
from core.settings import Settings, get_settings
from core.verifier import verify_assistant_draft
from sqlalchemy import text
from sqlalchemy.orm import Session

from domain.chat.concept_resolver import resolve_concept_for_turn
from domain.chat.prompt_kit import (
    build_full_tutor_prompt,
    build_social_response,
    classify_social_intent,
    get_persona,
)
from domain.chat.session_memory import load_assessment_context, load_history_text, persist_turn
from domain.chat.tutor_agent import build_tutor_response_text, resolve_tutor_style
from domain.readiness.analyzer import build_readiness_actions
from domain.retrieval.fts_retriever import PgFtsRetriever
from domain.retrieval.hybrid_retriever import HybridRetriever
from domain.retrieval.types import RankedChunk
from domain.retrieval.vector_retriever import PgVectorRetriever


def generate_chat_response(
    session: Session,
    *,
    request: ChatRespondRequest,
    settings: Settings | None = None,
) -> AssistantResponseEnvelope:
    """Build a deterministic chat response and enforce citation policy."""
    with observation_context(
        component="chat",
        operation="chat.respond",
        workspace_id=request.workspace_id,
    ), start_span(
        "chat.respond",
        component="chat",
        operation="chat.respond",
        workspace_id=request.workspace_id,
    ) as span:
        set_span_kind(span, SPAN_KIND_CHAIN)
        set_input_output(span, input_value=request.query)
        active_settings = settings or get_settings()
        grounding_mode = request.grounding_mode or active_settings.default_grounding_mode

        # ── Slice 13: Social intent fast-path ─────────────────────────
        if active_settings.social_intent_enabled and classify_social_intent(request.query):
            persona = get_persona(active_settings.tutor_persona)
            social_text = build_social_response(request.query, persona=persona)
            envelope = AssistantResponseEnvelope(
                kind=AssistantResponseKind.ANSWER,
                text=social_text,
                grounding_mode=grounding_mode,
                evidence=[],
                citations=[],
                response_mode="social",
                actions=[],
            )
            persist_turn(
                session,
                workspace_id=request.workspace_id,
                session_id=request.session_id,
                user_id=request.user_id,
                user_text=request.query,
                assistant_payload=envelope.model_dump(mode="json"),
            )
            set_input_output(span, output_value=envelope.text)
            return envelope

        # ── Standard grounded path ────────────────────────────────────
        history_text = load_history_text(session, session_id=request.session_id)

        # Slice 8: Load recent assessment context for tutor prompt
        assessment_context = load_assessment_context(
            session, session_id=request.session_id
        )

        concept_resolution = resolve_concept_for_turn(
            session,
            workspace_id=request.workspace_id,
            query=request.query,
            history_text=history_text,
            current_concept_id=request.concept_id,
            suggested_concept_id=request.suggested_concept_id,
            switch_decision=request.concept_switch_decision,
        )

        provider = build_embedding_provider(settings=active_settings)
        vector_retriever = PgVectorRetriever(
            session=session,
            embedding_provider=provider,
            retrieval_max_top_k=active_settings.retrieval_max_top_k,
        )
        fts_retriever = PgFtsRetriever(
            session=session,
            retrieval_max_top_k=active_settings.retrieval_max_top_k,
        )
        retriever = HybridRetriever(
            vector_retriever=vector_retriever,
            fts_retriever=fts_retriever,
            retrieval_max_top_k=active_settings.retrieval_max_top_k,
        )
        ranked_chunks = retriever.retrieve(
            query=request.query,
            workspace_id=request.workspace_id,
            top_k=request.top_k,
        )

        # ── Empty workspace fast-path: guide user to upload docs ──────
        if not ranked_chunks and _workspace_has_no_chunks(session, request.workspace_id):
            no_docs_text = (
                "It looks like your workspace doesn't have any documents yet! "
                "I'd love to help you learn, but I need some study material first.\n\n"
                "**Here's how to get started:**\n"
                "1. Head over to the **Knowledge Base** page\n"
                "2. Upload your notes, textbooks, or any study material (Markdown or text files)\n"
                "3. Come back here and ask me anything about them!\n\n"
                "Once you upload documents, I can provide Socratic guidance, "
                "generate quizzes, and help you master the material. 📚"
            )
            empty_ws_envelope = AssistantResponseEnvelope(
                kind=AssistantResponseKind.ANSWER,
                text=no_docs_text,
                grounding_mode=grounding_mode,
                evidence=[],
                citations=[],
                response_mode="onboarding",
                actions=[],
            )
            persist_turn(
                session,
                workspace_id=request.workspace_id,
                session_id=request.session_id,
                user_id=request.user_id,
                user_text=request.query,
                assistant_payload=empty_ws_envelope.model_dump(mode="json"),
            )
            set_input_output(span, output_value=empty_ws_envelope.text)
            return empty_ws_envelope

        if concept_resolution.resolved_concept is not None:
            ranked_chunks = _apply_concept_bias(
                session,
                workspace_id=request.workspace_id,
                concept_id=concept_resolution.resolved_concept.concept_id,
                chunks=ranked_chunks,
            )

        evidence = _build_workspace_evidence(
            session=session,
            workspace_id=request.workspace_id,
            chunks=ranked_chunks,
        )
        citations = _build_workspace_citations(evidence)
        tutor_llm_client = _build_tutor_llm_client(settings=active_settings)
        mastery_status = _resolve_mastery_status(
            session=session,
            request=request,
            resolved_concept_id=(
                concept_resolution.resolved_concept.concept_id
                if concept_resolution.resolved_concept is not None
                else None
            ),
        )

        assistant_text = (
            concept_resolution.clarification_prompt
            if concept_resolution.requires_clarification
            else _generate_tutor_text(
                query=request.query,
                evidence=evidence,
                mastery_status=mastery_status,
                llm_client=tutor_llm_client,
                history_text=history_text,
                assessment_context=assessment_context,
                document_summaries=_build_document_summaries_context(
                    session=session,
                    workspace_id=request.workspace_id,
                    chunks=ranked_chunks,
                ),
            )
        )

        draft = AssistantDraft(
            text=assistant_text,
            evidence=evidence,
            citations=citations,
        )
        envelope = verify_assistant_draft(draft=draft, grounding_mode=grounding_mode)

        meta = ConversationMeta(
            session_id=request.session_id,
            resolved_concept_id=(
                concept_resolution.resolved_concept.concept_id
                if concept_resolution.resolved_concept is not None
                else None
            ),
            resolved_concept_name=(
                concept_resolution.resolved_concept.canonical_name
                if concept_resolution.resolved_concept is not None
                else None
            ),
            concept_confidence=concept_resolution.confidence,
            requires_clarification=concept_resolution.requires_clarification,
            concept_switch_suggestion=(
                ConceptSwitchSuggestion(
                    from_concept_id=concept_resolution.switch_suggestion.from_concept_id,
                    from_concept_name=concept_resolution.switch_suggestion.from_concept_name,
                    to_concept_id=concept_resolution.switch_suggestion.to_concept_id,
                    to_concept_name=concept_resolution.switch_suggestion.to_concept_name,
                    reason=concept_resolution.switch_suggestion.reason,
                )
                if concept_resolution.switch_suggestion is not None
                else None
            ),
        )
        envelope = envelope.model_copy(update={"conversation_meta": meta})

        # ── Slice 9: Readiness CTA actions ────────────────────────────
        actions: list[dict[str, object]] = []
        if request.user_id is not None:
            try:
                actions = build_readiness_actions(
                    session,
                    workspace_id=request.workspace_id,
                    user_id=request.user_id,
                    limit=2,
                )
            except Exception:
                pass  # Non-critical: don't fail chat if readiness is unavailable
        envelope = envelope.model_copy(
            update={"actions": actions, "response_mode": "grounded"}
        )

        set_input_output(span, output_value=envelope.text)

        persist_turn(
            session,
            workspace_id=request.workspace_id,
            session_id=request.session_id,
            user_id=request.user_id,
            user_text=request.query,
            assistant_payload=envelope.model_dump(mode="json"),
        )
        return envelope


def _generate_tutor_text(
    *,
    query: str,
    evidence: list[EvidenceItem],
    mastery_status: str | None,
    llm_client: GraphLLMClient | None,
    history_text: str,
    assessment_context: str,
    document_summaries: str = "",
) -> str:
    """Build a rich tutor prompt via prompt_kit and call the LLM.

    Falls back to the simpler build_tutor_response_text when the full
    prompt fails or the LLM is unavailable.
    """
    style = resolve_tutor_style(mastery_status=mastery_status)
    persona = get_persona("openclaw")
    prompt = build_full_tutor_prompt(
        query=query,
        evidence=evidence,
        persona=persona,
        style=style,
        assessment_context=assessment_context,
        history_summary=history_text,
        document_summaries=document_summaries,
    )
    if llm_client is not None:
        try:
            text = llm_client.generate_tutor_text(prompt=prompt).strip()
        except (RuntimeError, ValueError):
            text = ""
        if text:
            return text
    # Fall back to the simpler pipeline
    return build_tutor_response_text(
        query=query,
        evidence=evidence,
        mastery_status=mastery_status,
        llm_client=None,
    )


def _build_workspace_evidence(
    *,
    session: Session,
    workspace_id: int,
    chunks: list[RankedChunk],
) -> list[EvidenceItem]:
    documents_by_id: dict[int, DocumentRow | None] = {}
    evidence_items: list[EvidenceItem] = []

    for index, chunk in enumerate(chunks, start=1):
        if chunk.document_id not in documents_by_id:
            documents_by_id[chunk.document_id] = get_document_by_id(
                session,
                workspace_id=workspace_id,
                document_id=chunk.document_id,
            )
        document = documents_by_id[chunk.document_id]
        content = chunk.text.strip() or chunk.text

        evidence_items.append(
            EvidenceItem(
                evidence_id=f"e{index}",
                source_type=EvidenceSourceType.WORKSPACE,
                content=content,
                document_id=chunk.document_id,
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                document_title=document.title if document is not None else None,
                source_uri=document.source_uri if document is not None else None,
                score=_clamp_score(chunk.score),
            )
        )

    return evidence_items


def _build_workspace_citations(evidence: list[EvidenceItem]) -> list[Citation]:
    citations: list[Citation] = []
    for index, item in enumerate(evidence, start=1):
        citations.append(
            Citation(
                citation_id=f"c{index}",
                evidence_id=item.evidence_id,
                label=CITATION_LABEL_FROM_NOTES,
                quote=_truncate(_single_line(item.content), limit=180),
            )
        )
    return citations


def _resolve_mastery_status(
    *,
    session: Session,
    request: ChatRespondRequest,
    resolved_concept_id: int | None,
) -> str | None:
    if request.user_id is None:
        return None
    concept_id = resolved_concept_id or request.concept_id
    if concept_id is None:
        return None
    return get_mastery_status(
        session,
        workspace_id=request.workspace_id,
        user_id=request.user_id,
        concept_id=concept_id,
    )


def _build_tutor_llm_client(*, settings: Settings):
    try:
        return build_graph_llm_client(settings=settings)
    except ValueError:
        return None


def _apply_concept_bias(
    session: Session,
    *,
    workspace_id: int,
    concept_id: int,
    chunks: list[RankedChunk],
) -> list[RankedChunk]:
    linked_chunk_ids = _linked_chunks_for_concept(
        session,
        workspace_id=workspace_id,
        concept_id=concept_id,
    )
    if not linked_chunk_ids:
        return chunks

    boosted = [
        (
            chunk.score + (0.15 if chunk.chunk_id in linked_chunk_ids else 0.0),
            index,
            chunk,
        )
        for index, chunk in enumerate(chunks)
    ]
    boosted.sort(key=lambda item: (-item[0], item[1], item[2].chunk_id))
    return [
        RankedChunk(
            workspace_id=item[2].workspace_id,
            document_id=item[2].document_id,
            chunk_id=item[2].chunk_id,
            chunk_index=item[2].chunk_index,
            text=item[2].text,
            score=item[0],
            retrieval_method=item[2].retrieval_method,
        )
        for item in boosted
    ]


def _linked_chunks_for_concept(
    session: Session,
    *,
    workspace_id: int,
    concept_id: int,
) -> set[int]:
    if not hasattr(session, "execute"):
        return set()
    rows = (
        session.execute(
            text(
                """
                SELECT chunk_id
                FROM provenance
                WHERE workspace_id = :workspace_id
                  AND target_type = 'concept'
                  AND target_id = :concept_id
                ORDER BY chunk_id ASC
                LIMIT 200
                """
            ),
            {"workspace_id": workspace_id, "concept_id": concept_id},
        )
        .mappings()
        .all()
    )
    return {int(row["chunk_id"]) for row in rows}


def _truncate(value: str, *, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def _single_line(value: str) -> str:
    return " ".join(value.split())


def _clamp_score(score: float) -> float:
    return max(0.0, min(1.0, score))


def _workspace_has_no_chunks(session: Session, workspace_id: int) -> bool:
    """Return True if the workspace has zero indexed chunks."""
    try:
        row = (
            session.execute(
                text("SELECT 1 FROM chunks WHERE workspace_id = :wid LIMIT 1"),
                {"wid": workspace_id},
            )
            .mappings()
            .first()
        )
        return row is None
    except Exception:
        return False


def _build_document_summaries_context(
    *,
    session: Session,
    workspace_id: int,
    chunks: list[RankedChunk],
) -> str:
    """Build a context string of document summaries referenced by retrieved chunks."""
    doc_ids = list(dict.fromkeys(c.document_id for c in chunks))[:5]
    if not doc_ids:
        return ""
    summaries: list[str] = []
    for doc_id in doc_ids:
        doc = get_document_by_id(session, workspace_id=workspace_id, document_id=doc_id)
        if doc and doc.summary:
            summaries.append(f"- {doc.title}: {doc.summary}")
    return "\n".join(summaries)


__all__ = ["generate_chat_response"]
