"""Workspace CRUD routes and settings management."""

from __future__ import annotations

from adapters.db.dependencies import get_db_session
from apps.api.dependencies import WorkspaceContext, get_current_user, get_workspace_context
from domain.workspaces.service import WorkspaceNotFoundError
from domain.workspaces import service as ws_service
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


# ── Schemas ───────────────────────────────────────────────────────────


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None

class WorkspaceUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class WorkspaceSummary(BaseModel):
    workspace_id: int
    public_id: str
    name: str
    description: str | None = None


class WorkspaceListResponse(BaseModel):
    workspaces: list[WorkspaceSummary]


class WorkspaceDetail(WorkspaceSummary):
    settings: dict[str, object] = Field(default_factory=dict)


class WorkspaceSettingsUpdateRequest(BaseModel):
    settings: dict[str, object]


# ── Routes ────────────────────────────────────────────────────────────


@router.post("", response_model=WorkspaceSummary, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreateRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> WorkspaceSummary:
    """Create a workspace and add the current user as owner-member."""
    result = ws_service.create_workspace(
        db,
        name=payload.name,
        description=payload.description,
        owner_user_id=user.id,
    )
    return WorkspaceSummary(**result)


@router.get("", response_model=WorkspaceListResponse)
def list_workspaces(
    user=Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> WorkspaceListResponse:
    """List workspaces the current user is a member of."""
    items = ws_service.list_workspaces(db, user_id=user.id)
    return WorkspaceListResponse(workspaces=[WorkspaceSummary(**r) for r in items])


@router.get("/{ws_id}", response_model=WorkspaceDetail)
def get_workspace(
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> WorkspaceDetail:
    """Get workspace details (requires membership)."""
    try:
        result = ws_service.get_workspace(db, workspace_id=ws.workspace_id)
    except WorkspaceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    return WorkspaceDetail(**result)


@router.patch("/{ws_id}", response_model=WorkspaceDetail)
def update_workspace(
    payload: WorkspaceUpdateRequest,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> WorkspaceDetail:
    """Update workspace name and description."""
    try:
        result = ws_service.update_workspace(
            db,
            workspace_id=ws.workspace_id,
            name=payload.name,
            description=payload.description,
        )
    except WorkspaceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    return WorkspaceDetail(**result)


@router.delete("/{ws_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace_endpoint(
    ws: WorkspaceContext = Depends(get_workspace_context),
    user=Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> Response:
    """Delete a workspace (owner only). Cascades to all associated data."""
    try:
        ws_service.delete_workspace(db, workspace_id=ws.workspace_id, user_id=user.id)
    except WorkspaceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{ws_id}/settings", response_model=WorkspaceDetail)
def update_workspace_settings(
    payload: WorkspaceSettingsUpdateRequest,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> WorkspaceDetail:
    """Merge settings into the workspace JSONB column."""
    try:
        result = ws_service.update_workspace_settings(
            db,
            workspace_id=ws.workspace_id,
            new_settings=payload.settings,
        )
    except WorkspaceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    return WorkspaceDetail(**result)


__all__ = ["router"]
