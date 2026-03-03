"""Retrieval context: retriever construction, concept-bias, workspace checks."""

from __future__ import annotations

import json

from adapters.embeddings.factory import build_embedding_provider
from core.observability import (
    SPAN_KIND_RETRIEVER,
    record_content_enabled,
    start_span,
    content_preview,
)
from core.settings import Settings
from domain.retrieval.fts_retriever import PgFtsRetriever
from domain.retrieval.hybrid_retriever import HybridRetriever
from domain.retrieval.types import RankedChunk
from domain.retrieval.vector_retriever import PgVectorRetriever
from sqlalchemy import text
from sqlalchemy.orm import Session

_ANCESTOR_TIERS = frozenset({"subtopic", "granular"})


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
        kind=SPAN_KIND_RETRIEVER,
        workspace_id=workspace_id,
        **{"retrieval.query": content_preview(query), "retrieval.top_k": top_k},
    ) as span:
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
                include_preview = record_content_enabled()
                doc_summary = json.dumps(
                    [
                        {
                            "rank": i + 1,
                            "chunk_id": r.chunk_id,
                            "document_id": r.document_id,
                            "score": round(r.score, 3),
                            "method": r.retrieval_method,
                            **({"preview": content_preview(r.text)} if include_preview else {}),
                        }
                        for i, r in enumerate(results[:5])
                    ],
                    default=str,
                )
                span.set_attribute("retrieval.documents", doc_summary)
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
        kind=SPAN_KIND_RETRIEVER,
        workspace_id=workspace_id,
        concept_id=concept_id,
        **{"retrieval.input_count": len(chunks)},
    ) as span:
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
                json.dumps(sorted(linked_chunk_ids)),
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


def retrieve_chunks_by_ids(
    session: Session,
    *,
    workspace_id: int,
    chunk_ids: list[int],
    score: float = 0.30,
) -> list[RankedChunk]:
    """Retrieve specific chunks by their IDs for provenance expansion.

    Returns RankedChunk objects with a fixed provenance score.
    Filters by workspace_id for tenant isolation.
    """
    if not chunk_ids or not hasattr(session, "execute"):
        return []
    # Limit to avoid unbounded queries
    limited = chunk_ids[:50]
    rows = (
        session.execute(
            text(
                """
                SELECT id, workspace_id, document_id, chunk_index, text
                FROM chunks
                WHERE workspace_id = :workspace_id
                  AND id = ANY(:ids)
                ORDER BY id ASC
                """
            ),
            {"workspace_id": workspace_id, "ids": limited},
        )
        .mappings()
        .all()
    )
    return [
        RankedChunk(
            workspace_id=int(row["workspace_id"]),
            document_id=int(row["document_id"]),
            chunk_id=int(row["id"]),
            chunk_index=int(row["chunk_index"]),
            text=str(row["text"]),
            score=score,
            retrieval_method="provenance",
        )
        for row in rows
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


def _build_ancestor_context_line(ancestors: list[dict]) -> str:
    """Format ancestor chain into a compact context string."""
    if not ancestors:
        return ""
    parts = [a["canonical_name"] for a in ancestors]
    return "Concept hierarchy (from parent to root): " + " → ".join(parts)


def build_ancestor_context(
    session: Session,
    *,
    workspace_id: int,
    concept_id: int,
    tier: str | None,
) -> str:
    """Return ancestor context line for subtopic/granular concepts, else empty string.

    Calls get_ancestor_chain only when tier warrants it; never raises.
    """
    if tier not in _ANCESTOR_TIERS:
        return ""
    try:
        from domain.graph.explore import get_ancestor_chain  # avoid circular at module level

        ancestors = get_ancestor_chain(session, workspace_id=workspace_id, concept_id=concept_id)
        return _build_ancestor_context_line(ancestors)
    except Exception:
        return ""
