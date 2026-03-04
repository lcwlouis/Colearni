"""Query helpers for chunk persistence and retrieval."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class ChunkRow:
    """Projected chunk row."""

    id: int
    document_id: int
    chunk_index: int
    text: str


def insert_chunks_bulk(
    db: Session,
    *,
    workspace_id: int,
    document_id: int,
    chunk_texts: list[str],
) -> int:
    """Insert a sequence of chunks for a document."""
    if not chunk_texts:
        return 0

    rows = [
        {
            "workspace_id": workspace_id,
            "document_id": document_id,
            "chunk_index": chunk_index,
            "text": chunk_text,
        }
        for chunk_index, chunk_text in enumerate(chunk_texts)
    ]

    db.execute(
        text(
            """
            INSERT INTO chunks (
                workspace_id,
                document_id,
                chunk_index,
                text,
                tsv,
                embedding
            )
            VALUES (
                :workspace_id,
                :document_id,
                :chunk_index,
                :text,
                to_tsvector('english', :text),
                NULL
            )
            """
        ),
        rows,
    )
    return len(rows)


def count_chunks_for_document(
    db: Session,
    *,
    workspace_id: int,
    document_id: int,
) -> int:
    """Count chunks for a workspace-scoped document."""
    return int(
        db.execute(
            text(
                """
                SELECT count(*) AS n
                FROM chunks
                WHERE workspace_id = :workspace_id AND document_id = :document_id
                """
            ),
            {"workspace_id": workspace_id, "document_id": document_id},
        ).scalar_one()
    )


def list_chunks_for_document(
    db: Session,
    *,
    workspace_id: int,
    document_id: int,
) -> list[ChunkRow]:
    """List chunks ordered by stable chunk index."""
    rows = (
        db.execute(
            text(
                """
                SELECT id, document_id, chunk_index, text
                FROM chunks
                WHERE workspace_id = :workspace_id AND document_id = :document_id
                ORDER BY chunk_index ASC
                """
            ),
            {"workspace_id": workspace_id, "document_id": document_id},
        )
        .mappings()
        .all()
    )
    return [
        ChunkRow(
            id=int(row["id"]),
            document_id=int(row["document_id"]),
            chunk_index=int(row["chunk_index"]),
            text=str(row["text"]),
        )
        for row in rows
    ]


def search_chunks_full_text(
    db: Session,
    *,
    workspace_id: int,
    query: str,
    limit: int = 10,
) -> list[ChunkRow]:
    """Search chunks using Postgres full-text search (tsvector)."""
    rows = (
        db.execute(
            text(
                """
                SELECT id, document_id, chunk_index, text
                FROM chunks
                WHERE workspace_id = :workspace_id
                  AND tsv @@ plainto_tsquery('english', :query)
                ORDER BY
                  ts_rank(tsv, plainto_tsquery('english', :query)) DESC,
                  chunk_index ASC
                LIMIT :limit
                """
            ),
            {"workspace_id": workspace_id, "query": query, "limit": limit},
        )
        .mappings()
        .all()
    )
    return [
        ChunkRow(
            id=int(row["id"]),
            document_id=int(row["document_id"]),
            chunk_index=int(row["chunk_index"]),
            text=str(row["text"]),
        )
        for row in rows
    ]
