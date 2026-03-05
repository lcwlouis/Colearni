"""Postgres full-text chunk retriever."""

from __future__ import annotations

from adapters.db import chunks_repository
from core.contracts import ChunkRetriever
from core.observability import (
    SPAN_KIND_RETRIEVER,
    set_retrieval_documents,
    start_span,
)
from sqlalchemy.orm import Session

from domain.retrieval.types import RankedChunk


class PgFtsRetriever(ChunkRetriever):
    def __init__(self, session: Session, retrieval_max_top_k: int) -> None:
        if retrieval_max_top_k < 1:
            raise ValueError("retrieval_max_top_k must be >= 1")
        self._session = session
        self._retrieval_max_top_k = retrieval_max_top_k

    def retrieve(self, query: str, workspace_id: int, top_k: int) -> list[RankedChunk]:
        bounded_top_k = max(1, min(top_k, self._retrieval_max_top_k))
        with start_span(
            "retrieval.fts.search",
            kind=SPAN_KIND_RETRIEVER,
            workspace_id=workspace_id,
            **{"retrieval.top_k": bounded_top_k},
        ) as span:
            rows = chunks_repository.full_text_top_k(self._session, query, workspace_id, bounded_top_k)
            results = [
                RankedChunk(
                    workspace_id=workspace_id,
                    document_id=row.document_id,
                    chunk_id=row.chunk_id,
                    chunk_index=row.chunk_index,
                    text=row.text,
                    score=row.fts_rank,
                    retrieval_method="fts",
                )
                for row in rows
            ]
            if span is not None:
                span.set_attribute("retrieval.results_count", len(results))
                set_retrieval_documents(
                    span,
                    query=query,
                    documents=[
                        {"chunk_id": r.chunk_id, "document_id": r.document_id, "score": round(r.score, 3), "text": r.text, "retrieval_method": r.retrieval_method, "rank": i + 1}
                        for i, r in enumerate(results[:5])
                    ],
                )
            return results
