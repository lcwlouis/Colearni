"""Workspace domain service – orchestration for workspace CRUD operations."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from adapters.db import workspaces as ws_db


class WorkspaceNotFoundError(Exception):
    """Raised when a workspace lookup fails."""


def _row_to_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "workspace_id": int(row["id"]),
        "public_id": str(row["public_id"]),
        "name": str(row["name"]),
        "description": str(row["description"]) if row.get("description") else None,
    }


def _row_to_detail(row: dict[str, Any]) -> dict[str, Any]:
    result = _row_to_summary(row)
    result["settings"] = row["settings"] if row.get("settings") else {}
    return result


def create_workspace(
    db: Session,
    *,
    name: str,
    description: str | None,
    owner_user_id: int,
) -> dict[str, Any]:
    """Create a workspace and commit. Returns summary dict."""
    clean_name = name.strip()
    clean_desc = (description or "").strip() or None
    row = ws_db.insert_workspace(
        db,
        name=clean_name,
        description=clean_desc,
        owner_user_id=owner_user_id,
    )
    db.commit()
    return _row_to_summary(row)


def list_workspaces(db: Session, *, user_id: int) -> list[dict[str, Any]]:
    """List all workspaces for a user. Returns list of summary dicts."""
    rows = ws_db.list_workspaces_for_user(db, user_id=user_id)
    return [_row_to_summary(r) for r in rows]


def get_workspace(db: Session, *, workspace_id: int) -> dict[str, Any]:
    """Get workspace detail. Raises WorkspaceNotFoundError if missing."""
    row = ws_db.get_workspace_by_id(db, workspace_id=workspace_id)
    if row is None:
        raise WorkspaceNotFoundError
    return _row_to_detail(row)


def update_workspace(
    db: Session,
    *,
    workspace_id: int,
    name: str,
    description: str | None,
) -> dict[str, Any]:
    """Update workspace name/description. Raises WorkspaceNotFoundError if missing."""
    clean_name = name.strip()
    clean_desc = (description or "").strip() or None
    row = ws_db.update_workspace(
        db,
        workspace_id=workspace_id,
        name=clean_name,
        description=clean_desc,
    )
    if row is None:
        raise WorkspaceNotFoundError
    db.commit()
    return _row_to_detail(row)


def update_workspace_settings(
    db: Session,
    *,
    workspace_id: int,
    new_settings: dict[str, object],
) -> dict[str, Any]:
    """Merge settings into workspace. Raises WorkspaceNotFoundError if missing."""
    row = ws_db.merge_workspace_settings(
        db,
        workspace_id=workspace_id,
        new_settings=new_settings,
    )
    if row is None:
        raise WorkspaceNotFoundError
    db.commit()
    return _row_to_detail(row)
