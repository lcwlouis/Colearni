"""Hybrid chunk retriever combining vector and full-text candidates."""

from __future__ import annotations

import json
from typing import Literal

from core.contracts import ChunkRetriever
from core.observability import (
    SPAN_KIND_RETRIEVER,
    set_retrieval_documents,
    start_span,
)

from domain.retrieval.types import RankedChunk

RetrievalMethod = Literal["vector", "fts", "hybrid"]


class HybridRetriever(ChunkRetriever):
    """Merge vector and FTS candidates with deterministic weighted RRF reranking."""

    def __init__(
        self,
        vector_retriever: ChunkRetriever,
        fts_retriever: ChunkRetriever,
        retrieval_max_top_k: int,
        *,
        rrf_k: int = 60,
        vector_weight: float = 0.6,
        fts_weight: float = 0.4,
    ) -> None:
        if retrieval_max_top_k < 1:
            raise ValueError("retrieval_max_top_k must be >= 1")
        if rrf_k < 1:
            raise ValueError("rrf_k must be >= 1")
        if vector_weight <= 0 or fts_weight <= 0:
            raise ValueError("weights must be > 0")

        self._vector_retriever = vector_retriever
        self._fts_retriever = fts_retriever
        self._retrieval_max_top_k = retrieval_max_top_k
        self._rrf_k = rrf_k
        self._vector_weight = vector_weight
        self._fts_weight = fts_weight

    def retrieve(self, query: str, workspace_id: int, top_k: int) -> list[RankedChunk]:
        """Return top-k merged candidates ranked by weighted reciprocal rank fusion."""
        bounded_top_k = max(1, min(top_k, self._retrieval_max_top_k))
        vector_rows = self._vector_retriever.retrieve(query, workspace_id, bounded_top_k)
        fts_rows = self._fts_retriever.retrieve(query, workspace_id, bounded_top_k)

        with start_span(
            "retrieval.hybrid.fuse",
            kind=SPAN_KIND_RETRIEVER,
            **{
                "retrieval.vector_count": len(vector_rows),
                "retrieval.fts_count": len(fts_rows),
                "retrieval.rrf_k": self._rrf_k,
                "retrieval.vector_weight": self._vector_weight,
                "retrieval.fts_weight": self._fts_weight,
            },
        ) as span:
            vector_ranks = {row.chunk_id: rank for rank, row in enumerate(vector_rows, start=1)}
            fts_ranks = {row.chunk_id: rank for rank, row in enumerate(fts_rows, start=1)}
            by_chunk_id = {row.chunk_id: row for row in vector_rows}
            for row in fts_rows:
                by_chunk_id.setdefault(row.chunk_id, row)

            inf = float("inf")
            fused: list[tuple[float, int, float, float, int, RankedChunk, RetrievalMethod]] = []
            for chunk_id, row in by_chunk_id.items():
                vector_rank = vector_ranks.get(chunk_id)
                fts_rank = fts_ranks.get(chunk_id)
                score = (
                    (self._vector_weight / (self._rrf_k + vector_rank) if vector_rank else 0.0)
                    + (self._fts_weight / (self._rrf_k + fts_rank) if fts_rank else 0.0)
                )
                method: RetrievalMethod = (
                    "hybrid" if vector_rank and fts_rank else ("vector" if vector_rank else "fts")
                )
                fused.append(
                    (
                        score,
                        2 if method == "hybrid" else 1,
                        float(vector_rank or inf),
                        float(fts_rank or inf),
                        chunk_id,
                        row,
                        method,
                    )
                )

            fused.sort(key=lambda item: (-item[0], -item[1], item[2], item[3], item[4]))
            results = [
                RankedChunk(
                    workspace_id=item[5].workspace_id,
                    document_id=item[5].document_id,
                    chunk_id=item[5].chunk_id,
                    chunk_index=item[5].chunk_index,
                    text=item[5].text,
                    score=item[0],
                    retrieval_method=item[6],
                )
                for item in fused[:bounded_top_k]
            ]
            if span is not None:
                method_counts = {"vector": 0, "fts": 0, "hybrid": 0}
                for r in results:
                    method_counts[r.retrieval_method] = method_counts.get(r.retrieval_method, 0) + 1
                span.set_attribute("retrieval.results_count", len(results))
                span.set_attribute("retrieval.method_distribution", json.dumps(method_counts))
                set_retrieval_documents(
                    span,
                    query=query,
                    documents=[
                        {"chunk_id": r.chunk_id, "document_id": r.document_id, "score": round(r.score, 4), "text": r.text, "retrieval_method": r.retrieval_method, "rank": i + 1}
                        for i, r in enumerate(results[:5])
                    ],
                )
            return results
