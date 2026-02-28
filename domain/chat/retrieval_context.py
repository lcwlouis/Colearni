"""Retrieval context: retriever construction, concept-bias, workspace checks."""

from __future__ import annotations

import json

from adapters.embeddings.factory import build_embedding_provider
from core.observability import (
    SPAN_KIND_RETRIEVER,
    set_span_kind,
    start_span,
)
from core.settings import Settings
from domain.retrieval.fts_retriever import PgFtsRetriever
from domain.retrieval.hybrid_retriever import HybridRetriever
from domain.retrieval.types import RankedChunk
from domain.retrieval.vector_retriever import PgVectorRetriever
from sqlalchemy import text
from sqlalchemy.orm import Session


def retrieve_ranked_chunks(
    session: Session,
    *,
    workspace_id: int,
    query: str,
    top_k: int,
    settings: Settings,
) -> list[RankedChunk]:
    """Build a hybrid retriever and return ranked chunks."""
    with start_span(
        "retrieval.hybrid",
        workspace_id=workspace_id,
        **{"retrieval.query": query[:256], "retrieval.top_k": top_k},
    ) as span:
        set_span_kind(span, SPAN_KIND_RETRIEVER)
        provider = build_embedding_provider(settings=settings)
        vector_retriever = PgVectorRetriever(
            session=session,
            embedding_provider=provider,
            retrieval_max_top_k=settings.retrieval_max_top_k,
        )
        fts_retriever = PgFtsRetriever(
            session=session,
            retrieval_max_top_k=settings.retrieval_max_top_k,
        )
        retriever = HybridRetriever(
            vector_retriever=vector_retriever,
            fts_retriever=fts_retriever,
            retrieval_max_top_k=settings.retrieval_max_top_k,
        )
        results = retriever.retrieve(
            query=query,
            workspace_id=workspace_id,
            top_k=top_k,
        )
        if span is not None:
            span.set_attribute("retrieval.results_count", len(results))
            if results:
                doc_summary = json.dumps(
                    [{"chunk_id": r.chunk_id, "score": round(r.score, 3)} for r in results[:5]],
                    default=str,
                )
                span.set_attribute("retrieval.documents", doc_summary[:1024])
        return results


def apply_concept_bias(
    session: Session,
    *,
    workspace_id: int,
    concept_id: int,
    chunks: list[RankedChunk],
) -> list[RankedChunk]:
    """Boost scores for chunks linked to the given concept via provenance."""
    with start_span(
        "retrieval.graph.bias",
        workspace_id=workspace_id,
        concept_id=concept_id,
        **{"retrieval.input_count": len(chunks)},
    ) as span:
        set_span_kind(span, SPAN_KIND_RETRIEVER)
        linked_chunk_ids = _linked_chunks_for_concept(
            session,
            workspace_id=workspace_id,
            concept_id=concept_id,
        )
        if not linked_chunk_ids:
            if span is not None:
                span.set_attribute("retrieval.graph.linked_count", 0)
                span.set_attribute("retrieval.graph.boosted_count", 0)
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
        boosted_count = sum(1 for item in boosted if item[2].chunk_id in linked_chunk_ids)
        if span is not None:
            span.set_attribute("retrieval.graph.linked_count", len(linked_chunk_ids))
            span.set_attribute("retrieval.graph.boosted_count", boosted_count)
            span.set_attribute(
                "retrieval.graph.linked_chunk_ids",
                json.dumps(sorted(linked_chunk_ids)[:20]),
            )
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


def workspace_has_no_chunks(session: Session, workspace_id: int) -> bool:
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
        if callable(getattr(session, "rollback", None)):
            session.rollback()
        return False
