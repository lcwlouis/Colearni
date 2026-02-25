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
from adapters.embeddings.factory import build_embedding_provider
from adapters.parsers.chunker import chunk_text_deterministic
from adapters.parsers.text import UnsupportedTextDocumentError, parse_text_payload
from domain.embeddings.pipeline import NewChunkInput, populate_new_chunk_embeddings
from domain.graph.pipeline import build_graph_for_chunks
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.contracts import EmbeddingProvider, GraphLLMClient
from core.settings import Settings, get_settings


class IngestionValidationError(ValueError):
    """Raised when ingestion input is syntactically valid but semantically invalid."""


class IngestionEmbeddingUnavailableError(RuntimeError):
    """Raised when ingestion embedding writes are enabled but provider cannot be built."""


class IngestionGraphUnavailableError(RuntimeError):
    """Raised when graph building is enabled but graph dependencies are unavailable."""


@dataclass(frozen=True)
class IngestionRequest:
    """Inputs required to ingest a markdown/text/PDF payload."""

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
    chunk_embedding_provider: EmbeddingProvider | None = None,
    settings: Settings | None = None,
) -> IngestionResult:
    """Ingest a .md/.txt/.pdf payload and persist document/chunks rows."""
    active_settings = settings or get_settings()
    parsed = parse_text_payload(
        raw_bytes=request.raw_bytes,
        filename=request.filename,
        content_type=request.content_type,
    )
    if not parsed.normalized_text:
        if parsed.mime_type == "application/pdf":
            raise IngestionValidationError(
                "PDF has no extractable text layer. Only text-extractable PDFs are supported."
            )
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

    if active_settings.ingest_populate_embeddings:
        provider = chunk_embedding_provider
        if provider is None:
            try:
                provider = build_embedding_provider(settings=active_settings)
            except ValueError as exc:
                raise IngestionEmbeddingUnavailableError(
                    "Chunk embedding provider is unavailable while "
                    "APP_INGEST_POPULATE_EMBEDDINGS=true."
                ) from exc
        inserted_chunk_ids = populate_new_chunk_embeddings(
            session=db,
            provider=provider,
            chunks=[
                NewChunkInput(
                    workspace_id=request.workspace_id,
                    document_id=document.id,
                    chunk_index=chunk_index,
                    text=chunk_text,
                )
                for chunk_index, chunk_text in enumerate(chunks)
            ],
            batch_size=active_settings.embedding_batch_size,
        )
        chunk_count = len(inserted_chunk_ids)
    else:
        chunk_count = insert_chunks_bulk(
            db,
            workspace_id=request.workspace_id,
            document_id=document.id,
            chunk_texts=chunks,
        )

    if active_settings.ingest_build_graph:
        if graph_llm_client is None:
            raise IngestionGraphUnavailableError(
                "Graph builder is unavailable while APP_INGEST_BUILD_GRAPH=true."
            )
        effective_graph_embedding_provider = graph_embedding_provider or chunk_embedding_provider
        build_graph_for_chunks(
            db,
            workspace_id=request.workspace_id,
            chunks=list_chunks_for_document(
                db,
                workspace_id=request.workspace_id,
                document_id=document.id,
            ),
            llm_client=graph_llm_client,
            settings=active_settings,
            embedding_provider=effective_graph_embedding_provider,
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
    "IngestionEmbeddingUnavailableError",
    "IngestionGraphUnavailableError",
    "IngestionValidationError",
    "UnsupportedTextDocumentError",
    "ingest_text_document",
]
