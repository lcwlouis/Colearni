"""Workspace CRUD routes and settings management."""

from __future__ import annotations

from adapters.db.dependencies import get_db_session
from apps.api.dependencies import WorkspaceContext, get_current_user, get_workspace_context
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


# ── Schemas ───────────────────────────────────────────────────────────


class WorkspaceCreateRequest(BaseModel):
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
    row = (
        db.execute(
            text(
                """
                INSERT INTO workspaces (name, description, owner_user_id)
                VALUES (:name, :description, :owner_user_id)
                RETURNING id, public_id, name, description
                """
            ),
            {
                "name": payload.name.strip(),
                "description": (payload.description or "").strip() or None,
                "owner_user_id": user.id,
            },
        )
        .mappings()
        .one()
    )
    db.execute(
        text(
            """
            INSERT INTO workspace_members (workspace_id, user_id, role)
            VALUES (:workspace_id, :user_id, 'owner')
            """
        ),
        {"workspace_id": int(row["id"]), "user_id": user.id},
    )
    db.commit()
    return WorkspaceSummary(
        workspace_id=int(row["id"]),
        public_id=str(row["public_id"]),
        name=str(row["name"]),
        description=str(row["description"]) if row["description"] else None,
    )


@router.get("", response_model=WorkspaceListResponse)
def list_workspaces(
    user=Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> WorkspaceListResponse:
    """List workspaces the current user is a member of."""
    rows = (
        db.execute(
            text(
                """
                SELECT w.id, w.public_id, w.name, w.description
                FROM workspaces w
                JOIN workspace_members wm ON w.id = wm.workspace_id
                WHERE wm.user_id = :user_id
                ORDER BY w.name ASC
                """
            ),
            {"user_id": user.id},
        )
        .mappings()
        .all()
    )
    return WorkspaceListResponse(
        workspaces=[
            WorkspaceSummary(
                workspace_id=int(row["id"]),
                public_id=str(row["public_id"]),
                name=str(row["name"]),
                description=str(row["description"]) if row["description"] else None,
            )
            for row in rows
        ]
    )


@router.get("/{ws_id}", response_model=WorkspaceDetail)
def get_workspace(
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> WorkspaceDetail:
    """Get workspace details (requires membership)."""
    row = (
        db.execute(
            text(
                """
                SELECT id, public_id, name, description, settings
                FROM workspaces
                WHERE id = :workspace_id
                LIMIT 1
                """
            ),
            {"workspace_id": ws.workspace_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    return WorkspaceDetail(
        workspace_id=int(row["id"]),
        public_id=str(row["public_id"]),
        name=str(row["name"]),
        description=str(row["description"]) if row["description"] else None,
        settings=row["settings"] if row["settings"] else {},
    )


@router.patch("/{ws_id}/settings", response_model=WorkspaceDetail)
def update_workspace_settings(
    payload: WorkspaceSettingsUpdateRequest,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> WorkspaceDetail:
    """Merge settings into the workspace JSONB column."""
    row = (
        db.execute(
            text(
                """
                UPDATE workspaces
                SET settings = settings || :new_settings,
                    updated_at = now()
                WHERE id = :workspace_id
                RETURNING id, public_id, name, description, settings
                """
            ),
            {
                "workspace_id": ws.workspace_id,
                "new_settings": _jsonb_cast(payload.settings),
            },
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
    db.commit()
    return WorkspaceDetail(
        workspace_id=int(row["id"]),
        public_id=str(row["public_id"]),
        name=str(row["name"]),
        description=str(row["description"]) if row["description"] else None,
        settings=row["settings"] if row["settings"] else {},
    )


# ── Helpers ───────────────────────────────────────────────────────────


def _jsonb_cast(data: dict[str, object]) -> str:
    import json

    return json.dumps(data, default=str)


__all__ = ["router"]
