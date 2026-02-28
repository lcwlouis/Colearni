"""Ingestion service – request validation, dedup, document+chunk insert orchestration."""

from __future__ import annotations

import hashlib
from pathlib import Path

from adapters.db.chunks import (
    count_chunks_for_document,
    insert_chunks_bulk,
    list_chunks_for_document,
)
from adapters.db.documents import (
    get_document_by_content_hash,
    insert_document,
    update_document_status,
)
from adapters.embeddings.factory import build_embedding_provider
from adapters.parsers.chunker import chunk_text_deterministic
from adapters.parsers.text import parse_text_payload
from domain.embeddings.pipeline import NewChunkInput, populate_new_chunk_embeddings
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from adapters.db.documents import update_document_summary
from domain.graph.pipeline import build_graph_for_chunks
from domain.ingestion.post_ingest import generate_document_summary

from core.contracts import EmbeddingProvider, GraphLLMClient
from core.settings import Settings, get_settings


class IngestionValidationError(ValueError):
    """Raised when ingestion input is syntactically valid but semantically invalid."""


class IngestionEmbeddingUnavailableError(RuntimeError):
    """Raised when ingestion embedding writes are enabled but provider cannot be built."""


class IngestionGraphUnavailableError(RuntimeError):
    """Raised when graph building is enabled but graph dependencies are unavailable."""


class IngestionGraphProviderError(RuntimeError):
    """Raised when graph LLM provider returns an error during ingestion."""


from dataclasses import dataclass


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


def _resolve_title(*, title: str | None, filename: str | None) -> str:
    if title and title.strip():
        return title.strip()
    if filename and filename.strip():
        return Path(filename).stem or "untitled"
    return "untitled"


def _parse_and_hash(request: IngestionRequest):
    """Parse the payload and compute the content hash. Returns (parsed, content_hash)."""
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
    return parsed, content_hash


def _dedup_or_insert(
    db: Session,
    *,
    request: IngestionRequest,
    parsed,
    content_hash: str,
    chunks: list[str],
):
    """Dedup check → insert document. Returns (document, is_existing, IngestionResult|None)."""
    existing_document = get_document_by_content_hash(
        db,
        workspace_id=request.workspace_id,
        content_hash=content_hash,
    )
    if existing_document is not None:
        return None, IngestionResult(
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
        return None, IngestionResult(
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

    return document, None


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
    parsed, content_hash = _parse_and_hash(request)

    chunks = chunk_text_deterministic(parsed.normalized_text)
    if not chunks:
        raise IngestionValidationError("Document produced no chunks after normalization.")

    document, existing_result = _dedup_or_insert(
        db,
        request=request,
        parsed=parsed,
        content_hash=content_hash,
        chunks=chunks,
    )
    if existing_result is not None:
        return existing_result

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
        summary = generate_document_summary(
            chunks=chunks,
            llm_client=graph_llm_client,
        )
        if summary:
            update_document_summary(
                db,
                workspace_id=request.workspace_id,
                document_id=document.id,
                summary=summary,
            )
        effective_graph_embedding_provider = graph_embedding_provider or chunk_embedding_provider
        try:
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
        except RuntimeError as exc:
            raise IngestionGraphProviderError(
                f"Graph extraction failed: {exc}"
            ) from exc

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


def ingest_text_document_fast(
    db: Session,
    *,
    request: IngestionRequest,
    settings: Settings | None = None,
) -> IngestionResult:
    """Fast-path ingest: parse, hash, insert document + chunks, return immediately.

    Skips embeddings, summary, and graph extraction so the caller can run them
    in a background task via :func:`run_post_ingest_tasks`.
    """
    active_settings = settings or get_settings()
    parsed, content_hash = _parse_and_hash(request)

    chunks = chunk_text_deterministic(parsed.normalized_text)
    if not chunks:
        raise IngestionValidationError("Document produced no chunks after normalization.")

    document, existing_result = _dedup_or_insert(
        db,
        request=request,
        parsed=parsed,
        content_hash=content_hash,
        chunks=chunks,
    )
    if existing_result is not None:
        return existing_result

    chunk_count = insert_chunks_bulk(
        db,
        workspace_id=request.workspace_id,
        document_id=document.id,
        chunk_texts=chunks,
    )
    update_document_status(
        db,
        workspace_id=request.workspace_id,
        document_id=document.id,
        ingestion_status="ingested",
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
