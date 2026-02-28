"""pgvector-based chunk retriever."""

from __future__ import annotations

import json

from adapters.db import chunks_repository
from core.contracts import ChunkRetriever, EmbeddingProvider
from core.observability import (
    SPAN_KIND_RETRIEVER,
    start_span,
)
from sqlalchemy.orm import Session

from domain.retrieval.types import RankedChunk


class PgVectorRetriever(ChunkRetriever):
    """Retriever implementation backed by chunks.embedding pgvector search."""

    def __init__(
        self,
        session: Session,
        embedding_provider: EmbeddingProvider,
        retrieval_max_top_k: int,
    ) -> None:
        if retrieval_max_top_k < 1:
            raise ValueError("retrieval_max_top_k must be >= 1")

        self._session = session
        self._embedding_provider = embedding_provider
        self._retrieval_max_top_k = retrieval_max_top_k

    def retrieve(self, query: str, workspace_id: int, top_k: int) -> list[RankedChunk]:
        """Return top-k chunk matches for one workspace."""
        bounded_top_k = max(1, min(top_k, self._retrieval_max_top_k))
        with start_span(
            "retrieval.vector.search",
            kind=SPAN_KIND_RETRIEVER,
            workspace_id=workspace_id,
            **{"retrieval.top_k": bounded_top_k},
        ) as span:
            query_embeddings = self._embedding_provider.embed_texts([query])
            if len(query_embeddings) != 1:
                raise ValueError(
                    "Embedding provider must return exactly one query embedding, "
                    f"got {len(query_embeddings)}"
                )

            rows = chunks_repository.vector_top_k(
                session=self._session,
                query_embedding=query_embeddings[0],
                workspace_id=workspace_id,
                top_k=bounded_top_k,
            )
            ranked_rows = sorted(
                rows,
                key=lambda row: (row.cosine_distance, row.chunk_id),
            )[:bounded_top_k]

            results = [
                RankedChunk(
                    workspace_id=workspace_id,
                    chunk_id=row.chunk_id,
                    document_id=row.document_id,
                    chunk_index=row.chunk_index,
                    text=row.text,
                    score=1.0 - row.cosine_distance,
                    retrieval_method="vector",
                )
                for row in ranked_rows
            ]
            if span is not None:
                span.set_attribute("retrieval.results_count", len(results))
                if results:
                    span.set_attribute(
                        "retrieval.documents",
                        json.dumps(
                            [{"chunk_id": r.chunk_id, "score": round(r.score, 3)} for r in results[:5]],
                            default=str,
                        )[:1024],
                    )
            return results
