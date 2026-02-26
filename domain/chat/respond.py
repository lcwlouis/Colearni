"""Chat response orchestration with evidence verification."""

from __future__ import annotations

from adapters.db.documents import DocumentRow, get_document_by_id
from adapters.db.mastery import get_mastery_status
from adapters.embeddings.factory import build_embedding_provider
from adapters.llm.factory import build_graph_llm_client
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
    ChatRespondRequest,
    Citation,
    ConceptSwitchSuggestion,
    ConversationMeta,
    EvidenceItem,
    EvidenceSourceType,
)
from core.settings import Settings, get_settings
from core.verifier import verify_assistant_draft
from sqlalchemy import text
from sqlalchemy.orm import Session

from domain.chat.concept_resolver import resolve_concept_for_turn
from domain.chat.session_memory import load_history_text, persist_turn
from domain.chat.tutor_agent import build_tutor_response_text
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

        history_text = load_history_text(session, session_id=request.session_id)
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
            else build_tutor_response_text(
                query=request.query,
                evidence=evidence,
                mastery_status=mastery_status,
                llm_client=tutor_llm_client,
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


__all__ = ["generate_chat_response"]
