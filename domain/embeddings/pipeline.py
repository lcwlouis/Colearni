"""Embedding pipeline services for chunk ingestion and backfill."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from adapters.db.chunks_repository import (
    ChunkEmbeddingUpdate,
    ChunkInsertRow,
    insert_chunks_with_embeddings,
    list_chunks_missing_embeddings,
    update_chunk_embeddings,
)
from core.contracts import EmbeddingProvider
from sqlalchemy.orm import Session


@dataclass(frozen=True, slots=True)
class NewChunkInput:
    """Input payload for creating a chunk with an embedding."""

    workspace_id: int
    document_id: int
    chunk_index: int
    text: str


@dataclass(frozen=True, slots=True)
class BackfillResult:
    """Summary from one bounded backfill invocation."""

    requested_limit: int
    effective_limit: int
    candidate_chunks: int
    updated_chunks: int


def embed_texts_batched(
    provider: EmbeddingProvider,
    texts: Sequence[str],
    batch_size: int,
) -> list[list[float]]:
    """Embed text in fixed-size batches and validate output cardinality."""
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")

    embeddings: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = list(texts[start : start + batch_size])
        batch_embeddings = provider.embed_texts(batch)
        if len(batch_embeddings) != len(batch):
            raise ValueError(
                "Embedding provider returned incorrect result count for batch: "
                f"expected {len(batch)}, got {len(batch_embeddings)}"
            )
        embeddings.extend(batch_embeddings)

    return embeddings


def populate_new_chunk_embeddings(
    session: Session,
    provider: EmbeddingProvider,
    chunks: Sequence[NewChunkInput],
    batch_size: int,
) -> list[int]:
    """Populate embeddings for newly ingested chunks and persist them."""
    if not chunks:
        return []

    texts = [chunk.text for chunk in chunks]
    embeddings = embed_texts_batched(provider=provider, texts=texts, batch_size=batch_size)

    rows = [
        ChunkInsertRow(
            workspace_id=chunk.workspace_id,
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            embedding=embedding,
        )
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    ]
    return insert_chunks_with_embeddings(session=session, rows=rows)


def backfill_missing_chunk_embeddings(
    session: Session,
    provider: EmbeddingProvider,
    workspace_id: int | None,
    requested_limit: int | None,
    max_chunks: int,
    batch_size: int,
) -> BackfillResult:
    """Backfill missing chunk embeddings in one bounded pass."""
    if max_chunks < 1:
        raise ValueError("max_chunks must be >= 1")

    requested = max_chunks if requested_limit is None else requested_limit
    if requested < 1:
        raise ValueError("requested_limit must be >= 1")

    effective_limit = min(requested, max_chunks)
    missing_rows = list_chunks_missing_embeddings(
        session=session,
        workspace_id=workspace_id,
        limit=effective_limit,
    )
    if not missing_rows:
        return BackfillResult(
            requested_limit=requested,
            effective_limit=effective_limit,
            candidate_chunks=0,
            updated_chunks=0,
        )

    embeddings = embed_texts_batched(
        provider=provider,
        texts=[row.text for row in missing_rows],
        batch_size=batch_size,
    )
    updates = [
        ChunkEmbeddingUpdate(chunk_id=row.chunk_id, embedding=embedding)
        for row, embedding in zip(missing_rows, embeddings, strict=True)
    ]
    updated_rows = update_chunk_embeddings(session=session, updates=updates)

    return BackfillResult(
        requested_limit=requested,
        effective_limit=effective_limit,
        candidate_chunks=len(missing_rows),
        updated_chunks=updated_rows,
    )
