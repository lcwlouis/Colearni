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
from adapters.db.documents import get_document_by_content_hash, insert_document, update_document_summary, update_document_status
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


class IngestionGraphProviderError(RuntimeError):
    """Raised when graph LLM provider returns an error during ingestion."""


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
        # Generate document summary using the LLM (best-effort, non-blocking)
        summary = _generate_document_summary(
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

    chunk_count = insert_chunks_bulk(
        db,
        workspace_id=request.workspace_id,
        document_id=document.id,
        chunk_texts=chunks,
    )
    # Mark document as ingested now that chunks are persisted
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


def run_post_ingest_tasks(
    *,
    workspace_id: int,
    document_id: int,
    graph_llm_client: GraphLLMClient | None = None,
    graph_embedding_provider: EmbeddingProvider | None = None,
    chunk_embedding_provider: EmbeddingProvider | None = None,
    settings: Settings | None = None,
) -> None:
    """Background task: populate embeddings, generate summary, build graph.

    Creates its own DB session so it can run outside the request lifecycle.
    """
    import logging

    from adapters.db.session import new_session

    log = logging.getLogger(__name__)
    log.info("post_ingest_tasks START ws=%s doc=%s", workspace_id, document_id)
    active_settings = settings or get_settings()
    db = new_session()
    try:
        # Mark graph as extracting
        if active_settings.ingest_build_graph and graph_llm_client is not None:
            update_document_status(
                db, workspace_id=workspace_id, document_id=document_id,
                graph_status="extracting",
            )
            db.commit()

        chunks_rows = list_chunks_for_document(
            db,
            workspace_id=workspace_id,
            document_id=document_id,
        )
        chunk_texts = [c.text for c in chunks_rows]
        log.info("post_ingest loaded %d chunks for doc=%s", len(chunk_texts), document_id)

        # 1) Populate embeddings
        if active_settings.ingest_populate_embeddings:
            provider = chunk_embedding_provider
            if provider is None:
                try:
                    provider = build_embedding_provider(settings=active_settings)
                except ValueError:
                    log.warning("Chunk embedding provider unavailable for background task")
                    provider = None
            if provider is not None:
                log.info("post_ingest embedding START doc=%s chunks=%d", document_id, len(chunk_texts))
                try:
                    populate_new_chunk_embeddings(
                        session=db,
                        provider=provider,
                        chunks=[
                            NewChunkInput(
                                workspace_id=workspace_id,
                                document_id=document_id,
                                chunk_index=i,
                                text=chunk_texts[i],
                            )
                            for i in range(len(chunk_texts))
                        ],
                        batch_size=active_settings.embedding_batch_size,
                    )
                    log.info("post_ingest embedding DONE doc=%s", document_id)
                except Exception:
                    log.exception("Background embedding population failed doc=%s", document_id)
                    # Rollback to keep the session usable for subsequent operations
                    db.rollback()

        # 2) Summary + graph
        if active_settings.ingest_build_graph and graph_llm_client is not None:
            log.info("post_ingest summary+graph START doc=%s", document_id)
            summary = _generate_document_summary(
                chunks=chunk_texts,
                llm_client=graph_llm_client,
            )
            if summary:
                log.info("post_ingest summary generated doc=%s len=%d", document_id, len(summary))
                update_document_summary(
                    db,
                    workspace_id=workspace_id,
                    document_id=document_id,
                    summary=summary,
                )
            effective_graph_embedding_provider = (
                graph_embedding_provider or chunk_embedding_provider
            )
            try:
                build_graph_for_chunks(
                    db,
                    workspace_id=workspace_id,
                    chunks=chunks_rows,
                    llm_client=graph_llm_client,
                    settings=active_settings,
                    embedding_provider=effective_graph_embedding_provider,
                )
                update_document_status(
                    db, workspace_id=workspace_id, document_id=document_id,
                    graph_status="extracted",
                )
                log.info("post_ingest graph DONE doc=%s", document_id)
            except Exception as exc:
                log.exception("Background graph extraction failed doc=%s", document_id)
                update_document_status(
                    db, workspace_id=workspace_id, document_id=document_id,
                    graph_status="failed",
                    error_message=f"Graph extraction failed: {exc}",
                )

        db.commit()
        log.info("post_ingest_tasks DONE ws=%s doc=%s", workspace_id, document_id)
    except Exception as exc:
        log.exception("Post-ingest background task failed ws=%s doc=%s", workspace_id, document_id)
        db.rollback()
        # Attempt to record failure status
        try:
            db2 = new_session()
            update_document_status(
                db2, workspace_id=workspace_id, document_id=document_id,
                graph_status="failed",
                error_message=f"Post-ingest task failed: {exc}",
            )
            db2.commit()
            db2.close()
        except Exception:
            log.exception("Failed to record error status doc=%s", document_id)
    finally:
        db.close()


def _resolve_title(*, title: str | None, filename: str | None) -> str:
    if title and title.strip():
        return title.strip()
    if filename and filename.strip():
        return Path(filename).stem or "untitled"
    return "untitled"


def _generate_document_summary(
    *,
    chunks: list[str],
    llm_client: GraphLLMClient,
    max_chunks: int = 5,
    max_chars: int = 3000,
) -> str | None:
    """Generate a short 2-3 sentence summary from the first few chunks."""
    if not chunks:
        return None
    sample_text = ""
    for chunk in chunks[:max_chunks]:
        if len(sample_text) + len(chunk) > max_chars:
            remaining = max_chars - len(sample_text)
            if remaining > 100:
                sample_text += chunk[:remaining]
            break
        sample_text += chunk + "\n\n"
    if not sample_text.strip():
        return None
    prompt = (
        "Summarize the following document excerpt in 2-3 concise sentences. "
        "Focus on the main topics and key concepts covered.\n\n"
        f"DOCUMENT EXCERPT:\n{sample_text.strip()}\n\n"
        "SUMMARY:"
    )
    try:
        summary = llm_client.generate_tutor_text(prompt=prompt).strip()
        if summary and len(summary) > 10:
            return summary[:500]
    except (RuntimeError, ValueError):
        pass
    return None


__all__ = [
    "IngestionRequest",
    "IngestionResult",
    "IngestionEmbeddingUnavailableError",
    "IngestionGraphProviderError",
    "IngestionGraphUnavailableError",
    "IngestionValidationError",
    "UnsupportedTextDocumentError",
    "ingest_text_document",
    "ingest_text_document_fast",
    "run_post_ingest_tasks",
]
