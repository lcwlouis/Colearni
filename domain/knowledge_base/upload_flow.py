"""Shared upload flow for document ingestion.

Centralizes settings resolution, fast-ingest invocation, provider resolution,
and background-task scheduling so that both the legacy ``/documents/upload``
route and the canonical workspace-scoped KB upload route share one implementation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from adapters.embeddings.factory import build_embedding_provider
from adapters.llm.factory import build_graph_llm_client
from core.ingestion import (
    IngestionRequest,
    IngestionResult,
    ingest_text_document_fast,
    run_post_ingest_tasks,
)
from core.settings import Settings
from sqlalchemy.orm import Session

_log = logging.getLogger("colearni.domain.knowledge_base.upload_flow")


@dataclass(frozen=True)
class PostIngestContext:
    """Resolved runtime dependencies for scheduling background post-ingest tasks."""

    workspace_id: int
    document_id: int
    graph_llm_client: Any
    graph_embedding_provider: Any
    chunk_embedding_provider: Any
    settings: Settings | None


def resolve_settings(app_state: Any) -> Settings | None:
    """Extract Settings from FastAPI app state."""
    settings = getattr(app_state, "settings", None)
    return settings if isinstance(settings, Settings) else None


def resolve_post_ingest_context(
    app_state: Any,
    *,
    workspace_id: int,
    document_id: int,
    settings: Settings | None = None,
) -> PostIngestContext:
    """Resolve graph/embedding providers from app state with fallback construction."""
    graph_llm = getattr(app_state, "graph_llm_client", None)
    if graph_llm is None:
        try:
            graph_llm = build_graph_llm_client(settings=settings)
        except (ValueError, RuntimeError):
            graph_llm = None

    graph_embed = getattr(app_state, "graph_embedding_provider", None)
    if graph_embed is None:
        try:
            graph_embed = build_embedding_provider(settings=settings)
        except (ValueError, RuntimeError):
            graph_embed = None

    chunk_embed = getattr(app_state, "chunk_embedding_provider", None)
    if chunk_embed is None:
        try:
            chunk_embed = build_embedding_provider(settings=settings)
        except (ValueError, RuntimeError):
            chunk_embed = None

    return PostIngestContext(
        workspace_id=workspace_id,
        document_id=document_id,
        graph_llm_client=graph_llm,
        graph_embedding_provider=graph_embed,
        chunk_embedding_provider=chunk_embed,
        settings=settings,
    )


def schedule_post_ingest(
    background_tasks: Any,
    context: PostIngestContext,
) -> None:
    """Schedule background post-ingest work (embeddings, summary, graph)."""
    background_tasks.add_task(
        run_post_ingest_tasks,
        workspace_id=context.workspace_id,
        document_id=context.document_id,
        graph_llm_client=context.graph_llm_client,
        graph_embedding_provider=context.graph_embedding_provider,
        chunk_embedding_provider=context.chunk_embedding_provider,
        settings=context.settings,
    )


def execute_upload(
    db: Session,
    background_tasks: Any,
    *,
    request: IngestionRequest,
    app_state: Any,
) -> IngestionResult:
    """Execute the shared upload flow: fast-ingest and background scheduling.

    Resolves settings and providers from *app_state*, runs fast-path
    ingestion, and schedules post-ingest background work when a new
    document is created.

    Raises ``IngestionValidationError`` or ``UnsupportedTextDocumentError``
    on ingestion failure — callers should translate these into HTTP errors.
    """
    settings = resolve_settings(app_state)
    result = ingest_text_document_fast(db, request=request, settings=settings)

    if result.created:
        _log.info(
            "fast-ingest done doc=%s chunks=%d, scheduling background tasks",
            result.document_id,
            result.chunk_count,
        )
        context = resolve_post_ingest_context(
            app_state,
            workspace_id=result.workspace_id,
            document_id=result.document_id,
            settings=settings,
        )
        schedule_post_ingest(background_tasks, context)

    return result
