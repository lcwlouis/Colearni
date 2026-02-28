"""Knowledge-base explorer routes (workspace-scoped)."""

from __future__ import annotations

import logging

from adapters.db.dependencies import get_db_session
from adapters.llm.factory import build_graph_llm_client
from adapters.embeddings.factory import build_embedding_provider
from apps.api.dependencies import WorkspaceContext, get_workspace_context
from core.ingestion import (
    IngestionRequest,
    IngestionValidationError,
    ingest_text_document_fast,
    run_post_ingest_tasks,
)
from core.schemas import KBDocumentListResponse
from core.settings import Settings
from domain.knowledge_base.service import (
    DocumentNotFoundError,
    delete_document,
    list_documents,
    reset_document_for_reprocess,
)
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, UploadFile, File, Form, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/workspaces/{ws_id}/knowledge-base", tags=["knowledge-base"])

_log = logging.getLogger("colearni.api.knowledge_base")


@router.get("/documents", response_model=KBDocumentListResponse)
def list_kb_documents(
    request: Request,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> KBDocumentListResponse:
    """List documents in the workspace knowledge base with chunk counts."""
    app_settings: Settings | None = getattr(request.app.state, "settings", None)
    graph_enabled = bool(app_settings.ingest_build_graph) if app_settings else False
    return list_documents(db, workspace_id=ws.workspace_id, graph_enabled=graph_enabled)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_kb_document(
    document_id: int,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
    prune_orphan_graph: bool = Query(
        default=False,
        description="Remove canonical graph nodes/edges with no remaining provenance after deletion.",
    ),
) -> Response:
    """Delete a document and its chunks from the knowledge base."""
    try:
        delete_document(
            db,
            document_id=document_id,
            workspace_id=ws.workspace_id,
            prune_orphan_graph=prune_orphan_graph,
        )
    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in workspace.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/documents/{document_id}/reprocess", status_code=status.HTTP_202_ACCEPTED)
def reprocess_kb_document(
    document_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    """Re-run post-ingest tasks (embeddings, summary, graph) for a document."""
    try:
        reset_document_for_reprocess(
            db,
            document_id=document_id,
            workspace_id=ws.workspace_id,
        )
    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in workspace.",
        )

    # Schedule background re-processing
    app_state = getattr(request.app, "state", None)
    settings: Settings | None = getattr(app_state, "settings", None) if app_state else None
    graph_llm = getattr(app_state, "graph_llm_client", None) if app_state else None
    if graph_llm is None:
        try:
            graph_llm = build_graph_llm_client(settings=settings)
        except (ValueError, RuntimeError):
            graph_llm = None
    graph_embed = getattr(app_state, "graph_embedding_provider", None) if app_state else None
    if graph_embed is None:
        try:
            graph_embed = build_embedding_provider(settings=settings)
        except (ValueError, RuntimeError):
            graph_embed = None
    chunk_embed = getattr(app_state, "chunk_embedding_provider", None) if app_state else None
    if chunk_embed is None:
        try:
            chunk_embed = build_embedding_provider(settings=settings)
        except (ValueError, RuntimeError):
            chunk_embed = None

    background_tasks.add_task(
        run_post_ingest_tasks,
        workspace_id=ws.workspace_id,
        document_id=document_id,
        graph_llm_client=graph_llm,
        graph_embedding_provider=graph_embed,
        chunk_embedding_provider=chunk_embed,
        settings=settings,
    )

    return {
        "document_id": document_id,
        "workspace_id": ws.workspace_id,
        "status": "queued",
        "message": "Document reprocessing has been queued.",
    }


@router.post("/documents/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_kb_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> dict[str, object]:
    """Upload a document (txt, md, pdf) to the workspace knowledge base.

    Uses the fast-path ingest (parse + chunks only) and returns immediately.
    Embeddings, summary, and graph extraction run in a background task.
    """
    raw_bytes = await file.read()
    _log.info("upload received ws=%s file=%s size=%d", ws.workspace_id, file.filename, len(raw_bytes))
    if len(raw_bytes) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")
    if len(raw_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds 20 MB limit.")

    app_state = getattr(request.app, "state", None)
    settings: Settings | None = getattr(app_state, "settings", None) if app_state else None

    try:
        result = ingest_text_document_fast(
            db,
            request=IngestionRequest(
                workspace_id=ws.workspace_id,
                uploaded_by_user_id=ws.user.id,
                raw_bytes=raw_bytes,
                content_type=file.content_type,
                filename=file.filename,
                title=title,
                source_uri=None,
            ),
            settings=settings,
        )
    except IngestionValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    # Schedule heavy processing (embeddings, summary, graph) in background
    if result.created:
        _log.info("upload fast-ingest done doc=%s chunks=%d, scheduling background tasks", result.document_id, result.chunk_count)
        graph_llm = getattr(app_state, "graph_llm_client", None) if app_state else None
        if graph_llm is None:
            try:
                graph_llm = build_graph_llm_client(settings=settings)
            except (ValueError, RuntimeError):
                graph_llm = None
        graph_embed = getattr(app_state, "graph_embedding_provider", None) if app_state else None
        if graph_embed is None:
            try:
                graph_embed = build_embedding_provider(settings=settings)
            except (ValueError, RuntimeError):
                graph_embed = None
        chunk_embed = getattr(app_state, "chunk_embedding_provider", None) if app_state else None
        if chunk_embed is None:
            try:
                chunk_embed = build_embedding_provider(settings=settings)
            except (ValueError, RuntimeError):
                chunk_embed = None

        background_tasks.add_task(
            run_post_ingest_tasks,
            workspace_id=ws.workspace_id,
            document_id=result.document_id,
            graph_llm_client=graph_llm,
            graph_embedding_provider=graph_embed,
            chunk_embedding_provider=chunk_embed,
            settings=settings,
        )

    return {
        "document_id": result.document_id,
        "workspace_id": result.workspace_id,
        "title": result.title,
        "chunk_count": result.chunk_count,
        "created": result.created,
    }


__all__ = ["router"]
