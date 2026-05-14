import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import get_session
from backend.app.schemas.errors import ErrorBody, ErrorEnvelope
from backend.app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceListResponse,
    WorkspaceRead,
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
    return WorkspaceListResponse(workspaces=workspaces)


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
