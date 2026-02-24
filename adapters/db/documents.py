"""Query helpers for document persistence."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class DocumentRow:
    """Projected document row used by ingestion helpers."""

    id: int
    workspace_id: int
    title: str
    source_uri: str | None
    mime_type: str | None
    content_hash: str


def get_document_by_content_hash(
    db: Session,
    *,
    workspace_id: int,
    content_hash: str,
) -> DocumentRow | None:
    """Fetch an existing document by workspace + content hash."""
    row = db.execute(
        text(
            """
            SELECT id, workspace_id, title, source_uri, mime_type, content_hash
            FROM documents
            WHERE workspace_id = :workspace_id AND content_hash = :content_hash
            """
        ),
        {"workspace_id": workspace_id, "content_hash": content_hash},
    ).mappings().first()
    return _to_document_row(row)


def get_document_by_id(
    db: Session,
    *,
    workspace_id: int,
    document_id: int,
) -> DocumentRow | None:
    """Fetch a document by id, scoped to workspace."""
    row = db.execute(
        text(
            """
            SELECT id, workspace_id, title, source_uri, mime_type, content_hash
            FROM documents
            WHERE workspace_id = :workspace_id AND id = :document_id
            """
        ),
        {"workspace_id": workspace_id, "document_id": document_id},
    ).mappings().first()
    return _to_document_row(row)


def insert_document(
    db: Session,
    *,
    workspace_id: int,
    uploaded_by_user_id: int,
    title: str,
    source_uri: str | None,
    mime_type: str,
    content_hash: str,
) -> DocumentRow:
    """Insert and return a new document row."""
    row = db.execute(
        text(
            """
            INSERT INTO documents (
                workspace_id,
                uploaded_by_user_id,
                title,
                source_uri,
                mime_type,
                content_hash
            )
            VALUES (
                :workspace_id,
                :uploaded_by_user_id,
                :title,
                :source_uri,
                :mime_type,
                :content_hash
            )
            RETURNING id, workspace_id, title, source_uri, mime_type, content_hash
            """
        ),
        {
            "workspace_id": workspace_id,
            "uploaded_by_user_id": uploaded_by_user_id,
            "title": title,
            "source_uri": source_uri,
            "mime_type": mime_type,
            "content_hash": content_hash,
        },
    ).mappings().one()
    return _to_document_row(row)


def _to_document_row(row: dict[str, object] | None) -> DocumentRow | None:
    if row is None:
        return None
    return DocumentRow(
        id=int(row["id"]),
        workspace_id=int(row["workspace_id"]),
        title=str(row["title"]),
        source_uri=row["source_uri"] if row["source_uri"] is None else str(row["source_uri"]),
        mime_type=row["mime_type"] if row["mime_type"] is None else str(row["mime_type"]),
        content_hash=str(row["content_hash"]),
    )
