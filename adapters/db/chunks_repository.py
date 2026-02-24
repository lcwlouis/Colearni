"""Chunk persistence and vector retrieval queries."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True, slots=True)
class ChunkInsertRow:
    """Chunk payload for insert operations."""

    workspace_id: int
    document_id: int
    chunk_index: int
    text: str
    embedding: list[float]


@dataclass(frozen=True, slots=True)
class MissingChunkRow:
    """Chunk row with a missing embedding value."""

    chunk_id: int
    workspace_id: int
    text: str


@dataclass(frozen=True, slots=True)
class ChunkEmbeddingUpdate:
    """Embedding update payload for one chunk."""

    chunk_id: int
    embedding: list[float]


@dataclass(frozen=True, slots=True)
class VectorSearchRow:
    """Raw row returned from vector similarity search."""

    chunk_id: int
    document_id: int
    chunk_index: int
    text: str
    cosine_distance: float


def _vector_literal(values: Sequence[float]) -> str:
    """Serialize an embedding vector to pgvector text format."""
    if not values:
        raise ValueError("Embedding vector cannot be empty")
    return "[" + ",".join(f"{float(value):.12g}" for value in values) + "]"


def insert_chunks_with_embeddings(session: Session, rows: Sequence[ChunkInsertRow]) -> list[int]:
    """Insert new chunks with embeddings and return inserted chunk ids."""
    if not rows:
        return []

    statement = text(
        "INSERT INTO chunks (workspace_id, document_id, chunk_index, text, tsv, embedding) "
        "VALUES (:workspace_id, :document_id, :chunk_index, :text, "
        "to_tsvector('english', :text), CAST(:embedding AS vector)) "
        "RETURNING id"
    )

    inserted_ids: list[int] = []
    for row in rows:
        result = session.execute(
            statement,
            {
                "workspace_id": row.workspace_id,
                "document_id": row.document_id,
                "chunk_index": row.chunk_index,
                "text": row.text,
                "embedding": _vector_literal(row.embedding),
            },
        )
        inserted_ids.append(int(result.scalar_one()))

    return inserted_ids


def list_chunks_missing_embeddings(
    session: Session,
    workspace_id: int | None,
    limit: int,
) -> list[MissingChunkRow]:
    """Return chunks that do not yet have embeddings, bounded by limit."""
    if limit < 1:
        raise ValueError("limit must be >= 1")

    if workspace_id is None:
        statement = text(
            "SELECT id, workspace_id, text "
            "FROM chunks "
            "WHERE embedding IS NULL "
            "ORDER BY id ASC "
            "LIMIT :limit"
        )
        params = {"limit": limit}
    else:
        statement = text(
            "SELECT id, workspace_id, text "
            "FROM chunks "
            "WHERE workspace_id = :workspace_id AND embedding IS NULL "
            "ORDER BY id ASC "
            "LIMIT :limit"
        )
        params = {"workspace_id": workspace_id, "limit": limit}

    rows = session.execute(statement, params).mappings().all()
    return [
        MissingChunkRow(
            chunk_id=int(row["id"]),
            workspace_id=int(row["workspace_id"]),
            text=str(row["text"]),
        )
        for row in rows
    ]


def update_chunk_embeddings(session: Session, updates: Sequence[ChunkEmbeddingUpdate]) -> int:
    """Update chunk embeddings and return the number of affected rows."""
    if not updates:
        return 0

    statement = text(
        "UPDATE chunks "
        "SET embedding = CAST(:embedding AS vector) "
        "WHERE id = :chunk_id"
    )

    updated_rows = 0
    for update in updates:
        result = session.execute(
            statement,
            {
                "chunk_id": update.chunk_id,
                "embedding": _vector_literal(update.embedding),
            },
        )
        updated_rows += int(result.rowcount or 0)

    return updated_rows


def vector_top_k(
    session: Session,
    query_embedding: Sequence[float],
    workspace_id: int,
    top_k: int,
) -> list[VectorSearchRow]:
    """Return top-k nearest chunk rows in one workspace by cosine distance."""
    if top_k < 1:
        raise ValueError("top_k must be >= 1")

    statement = text(
        "SELECT "
        "id AS chunk_id, "
        "document_id, "
        "chunk_index, "
        "text, "
        "(embedding <=> CAST(:query_embedding AS vector)) AS cosine_distance "
        "FROM chunks "
        "WHERE workspace_id = :workspace_id AND embedding IS NOT NULL "
        "ORDER BY cosine_distance ASC, id ASC "
        "LIMIT :top_k"
    )

    rows = session.execute(
        statement,
        {
            "query_embedding": _vector_literal(query_embedding),
            "workspace_id": workspace_id,
            "top_k": top_k,
        },
    ).mappings()

    return [
        VectorSearchRow(
            chunk_id=int(row["chunk_id"]),
            document_id=int(row["document_id"]),
            chunk_index=int(row["chunk_index"]),
            text=str(row["text"]),
            cosine_distance=float(row["cosine_distance"]),
        )
        for row in rows
    ]
