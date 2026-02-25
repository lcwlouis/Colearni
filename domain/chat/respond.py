"""Chat response orchestration with evidence verification."""

from __future__ import annotations

from adapters.db.documents import DocumentRow, get_document_by_id
from adapters.db.mastery import get_mastery_status
from adapters.embeddings.factory import build_embedding_provider
from adapters.llm.factory import build_graph_llm_client
from core.observability import observation_context
from core.schemas import (
    CITATION_LABEL_FROM_NOTES,
    AssistantDraft,
    AssistantResponseEnvelope,
    ChatRespondRequest,
    Citation,
    EvidenceItem,
    EvidenceSourceType,
)
from core.settings import Settings, get_settings
from core.verifier import verify_assistant_draft
from sqlalchemy.orm import Session

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
    ):
        active_settings = settings or get_settings()
        grounding_mode = request.grounding_mode or active_settings.default_grounding_mode

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
        )

        draft = AssistantDraft(
            text=build_tutor_response_text(
                query=request.query,
                evidence=evidence,
                mastery_status=mastery_status,
                llm_client=tutor_llm_client,
            ),
            evidence=evidence,
            citations=citations,
        )
        return verify_assistant_draft(draft=draft, grounding_mode=grounding_mode)


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
) -> str | None:
    if request.user_id is None or request.concept_id is None:
        return None
    return get_mastery_status(
        session,
        workspace_id=request.workspace_id,
        user_id=request.user_id,
        concept_id=request.concept_id,
    )


def _build_tutor_llm_client(*, settings: Settings):
    try:
        return build_graph_llm_client(settings=settings)
    except ValueError:
        return None


def _truncate(value: str, *, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def _single_line(value: str) -> str:
    return " ".join(value.split())


def _clamp_score(score: float) -> float:
    return max(0.0, min(1.0, score))


__all__ = ["generate_chat_response"]
