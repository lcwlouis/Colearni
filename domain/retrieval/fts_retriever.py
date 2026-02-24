"""Postgres full-text chunk retriever."""

from __future__ import annotations

from adapters.db import chunks_repository
from core.contracts import ChunkRetriever
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
        rows = chunks_repository.full_text_top_k(self._session, query, workspace_id, bounded_top_k)
        return [
            RankedChunk(
                workspace_id=workspace_id,
                document_id=row.document_id,
                chunk_id=row.chunk_id,
                snippet=row.text,
                score=row.fts_rank,
                retrieval_method="fts",
            )
            for row in rows
        ]
