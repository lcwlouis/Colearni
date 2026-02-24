"""Core ingestion orchestration for text documents."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from adapters.db.chunks import (
    count_chunks_for_document,
    insert_chunks_bulk,
    list_chunks_for_document,
)
from adapters.db.documents import get_document_by_content_hash, insert_document
from adapters.parsers.chunker import chunk_text_deterministic
from adapters.parsers.text import UnsupportedTextDocumentError, parse_text_payload
from domain.graph.pipeline import build_graph_for_chunks
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.contracts import EmbeddingProvider, GraphLLMClient
from core.settings import get_settings


class IngestionValidationError(ValueError):
    """Raised when ingestion input is syntactically valid but semantically invalid."""


@dataclass(frozen=True)
class IngestionRequest:
    """Inputs required to ingest a text or markdown payload."""

    workspace_id: int
    uploaded_by_user_id: int
    raw_bytes: bytes
    content_type: str | None
    filename: str | None
    title: str | None
    source_uri: str | None


@dataclass(frozen=True)
class IngestionResult:
    """Materialized ingestion result payload."""

    document_id: int
    workspace_id: int
    title: str
    mime_type: str
    content_hash: str
    chunk_count: int
    created: bool


def ingest_text_document(
    db: Session,
    *,
    request: IngestionRequest,
    graph_llm_client: GraphLLMClient | None = None,
    graph_embedding_provider: EmbeddingProvider | None = None,
) -> IngestionResult:
    """Ingest a .md/.txt payload and persist document/chunks rows."""
    parsed = parse_text_payload(
        raw_bytes=request.raw_bytes,
        filename=request.filename,
        content_type=request.content_type,
    )
    if not parsed.normalized_text:
        raise IngestionValidationError("Document content is empty after normalization.")

    content_hash = hashlib.sha256(parsed.normalized_text.encode("utf-8")).hexdigest()
    existing_document = get_document_by_content_hash(
        db,
        workspace_id=request.workspace_id,
        content_hash=content_hash,
    )
    if existing_document is not None:
        return IngestionResult(
            document_id=existing_document.id,
            workspace_id=existing_document.workspace_id,
            title=existing_document.title,
            mime_type=existing_document.mime_type or parsed.mime_type,
            content_hash=existing_document.content_hash,
            chunk_count=count_chunks_for_document(
                db,
                workspace_id=request.workspace_id,
                document_id=existing_document.id,
            ),
            created=False,
        )

    chunks = chunk_text_deterministic(parsed.normalized_text)
    if not chunks:
        raise IngestionValidationError("Document produced no chunks after normalization.")

    resolved_title = _resolve_title(title=request.title, filename=request.filename)
    try:
        document = insert_document(
            db,
            workspace_id=request.workspace_id,
            uploaded_by_user_id=request.uploaded_by_user_id,
            title=resolved_title,
            source_uri=request.source_uri,
            mime_type=parsed.mime_type,
            content_hash=content_hash,
        )
    except IntegrityError:
        db.rollback()
        existing_document = get_document_by_content_hash(
            db,
            workspace_id=request.workspace_id,
            content_hash=content_hash,
        )
        if existing_document is None:
            raise
        return IngestionResult(
            document_id=existing_document.id,
            workspace_id=existing_document.workspace_id,
            title=existing_document.title,
            mime_type=existing_document.mime_type or parsed.mime_type,
            content_hash=existing_document.content_hash,
            chunk_count=count_chunks_for_document(
                db,
                workspace_id=request.workspace_id,
                document_id=existing_document.id,
            ),
            created=False,
        )

    chunk_count = insert_chunks_bulk(
        db,
        workspace_id=request.workspace_id,
        document_id=document.id,
        chunk_texts=chunks,
    )
    if graph_llm_client is not None:
        build_graph_for_chunks(
            db,
            workspace_id=request.workspace_id,
            chunks=list_chunks_for_document(
                db,
                workspace_id=request.workspace_id,
                document_id=document.id,
            ),
            llm_client=graph_llm_client,
            settings=get_settings(),
            embedding_provider=graph_embedding_provider,
        )

    db.commit()
    return IngestionResult(
        document_id=document.id,
        workspace_id=document.workspace_id,
        title=document.title,
        mime_type=document.mime_type or parsed.mime_type,
        content_hash=document.content_hash,
        chunk_count=chunk_count,
        created=True,
    )


def _resolve_title(*, title: str | None, filename: str | None) -> str:
    if title and title.strip():
        return title.strip()
    if filename and filename.strip():
        return Path(filename).stem or "untitled"
    return "untitled"


__all__ = [
    "IngestionRequest",
    "IngestionResult",
    "IngestionValidationError",
    "UnsupportedTextDocumentError",
    "ingest_text_document",
]
