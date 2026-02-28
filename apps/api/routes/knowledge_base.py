"""Knowledge-base explorer routes (workspace-scoped)."""

from __future__ import annotations

import logging

from adapters.db.dependencies import get_db_session
from apps.api.dependencies import WorkspaceContext, get_workspace_context
from core.ingestion import IngestionRequest, IngestionValidationError
from core.schemas import KBDocumentListResponse
from domain.knowledge_base.service import (
    DocumentNotFoundError,
    delete_document,
    list_documents,
    reprocess_document,
)
from domain.knowledge_base.upload_flow import (
    execute_upload,
    resolve_settings,
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
    app_settings = resolve_settings(request.app.state)
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
        reprocess_document(
            db,
            background_tasks,
            document_id=document_id,
            workspace_id=ws.workspace_id,
            app_state=request.app.state,
        )
    except DocumentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in workspace.",
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

    try:
        result = execute_upload(
            db,
            background_tasks,
            request=IngestionRequest(
                workspace_id=ws.workspace_id,
                uploaded_by_user_id=ws.user.id,
                raw_bytes=raw_bytes,
                content_type=file.content_type,
                filename=file.filename,
                title=title,
                source_uri=None,
            ),
            app_state=request.app.state,
        )
    except IngestionValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return {
        "document_id": result.document_id,
        "workspace_id": result.workspace_id,
        "title": result.title,
        "chunk_count": result.chunk_count,
        "created": result.created,
    }


__all__ = ["router"]
