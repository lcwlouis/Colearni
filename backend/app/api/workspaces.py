import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import get_session
from backend.app.schemas.errors import ErrorBody, ErrorEnvelope
from backend.app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceListResponse,
    WorkspaceProgressResponse,
    WorkspaceQuizAttemptsResponse,
    WorkspaceQuizAttemptItem,
    WorkspaceRead,
    WorkspaceSourceItem,
    WorkspaceSourcesResponse,
)
from backend.app.services.source_ingestion import list_workspace_sources
from backend.app.services.workspace_aggregation import (
    get_workspace_progress,
    list_workspace_quiz_attempts,
)
from backend.app.services.workspaces import create_workspace, get_workspace, list_workspaces

router = APIRouter(prefix="/api/workspaces")


@router.post("", response_model=WorkspaceRead, status_code=201)
async def create_workspace_route(
    body: WorkspaceCreate,
    session: AsyncSession = Depends(get_session),
) -> WorkspaceRead:
    workspace = await create_workspace(session, name=body.name)
    return WorkspaceRead.model_validate(workspace)


@router.get("", response_model=WorkspaceListResponse)
async def list_workspaces_route(
    session: AsyncSession = Depends(get_session),
) -> WorkspaceListResponse:
    workspaces = await list_workspaces(session)
    return WorkspaceListResponse(
        workspaces=[WorkspaceRead.model_validate(workspace) for workspace in workspaces]
    )


@router.get("/{workspace_id}/quiz-attempts", response_model=WorkspaceQuizAttemptsResponse)
async def list_workspace_quiz_attempts_route(
    workspace_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> WorkspaceQuizAttemptsResponse | JSONResponse:
    try:
        attempts = await list_workspace_quiz_attempts(session, workspace_id=workspace_id)
    except LookupError as exc:
        return _not_found(str(exc))
    return WorkspaceQuizAttemptsResponse(attempts=attempts)


@router.get("/{workspace_id}/progress", response_model=WorkspaceProgressResponse)
async def get_workspace_progress_route(
    workspace_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> WorkspaceProgressResponse | JSONResponse:
    try:
        progress = await get_workspace_progress(session, workspace_id=workspace_id)
    except LookupError as exc:
        return _not_found(str(exc))
    return progress


@router.get("/{workspace_id}/sources", response_model=WorkspaceSourcesResponse)
async def list_workspace_sources_route(
    workspace_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> WorkspaceSourcesResponse | JSONResponse:
    try:
        sources = await list_workspace_sources(session, workspace_id=workspace_id)
    except LookupError as exc:
        return _not_found(str(exc))
    return WorkspaceSourcesResponse(sources=sources)


@router.get("/{workspace_id}", response_model=WorkspaceRead)
async def get_workspace_route(
    workspace_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> WorkspaceRead | JSONResponse:
    try:
        workspace = await get_workspace(session, workspace_id=workspace_id)
    except LookupError as exc:
        return _not_found(str(exc))
    return WorkspaceRead.model_validate(workspace)


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=ErrorEnvelope(error=ErrorBody(code="not_found", message=message)).model_dump(),
    )
