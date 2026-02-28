"""Workspace persistence layer – all SQL for workspace CRUD."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def insert_workspace(
    db: Session,
    *,
    name: str,
    description: str | None,
    owner_user_id: int,
) -> dict[str, Any]:
    """Insert a new workspace and add the owner as a member. Returns row dict."""
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
                "name": name,
                "description": description,
                "owner_user_id": owner_user_id,
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
        {"workspace_id": int(row["id"]), "user_id": owner_user_id},
    )
    return dict(row)


def list_workspaces_for_user(db: Session, *, user_id: int) -> list[dict[str, Any]]:
    """Return all workspaces the user is a member of."""
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
            {"user_id": user_id},
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


def get_workspace_by_id(db: Session, *, workspace_id: int) -> dict[str, Any] | None:
    """Fetch a single workspace with settings. Returns None if not found."""
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
            {"workspace_id": workspace_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row is not None else None


def update_workspace(
    db: Session,
    *,
    workspace_id: int,
    name: str,
    description: str | None,
) -> dict[str, Any] | None:
    """Update workspace name/description. Returns updated row or None."""
    row = (
        db.execute(
            text(
                """
                UPDATE workspaces
                SET name = :name,
                    description = :description,
                    updated_at = now()
                WHERE id = :workspace_id
                RETURNING id, public_id, name, description, settings
                """
            ),
            {
                "workspace_id": workspace_id,
                "name": name,
                "description": description,
            },
        )
        .mappings()
        .first()
    )
    return dict(row) if row is not None else None


def merge_workspace_settings(
    db: Session,
    *,
    workspace_id: int,
    new_settings: dict[str, object],
) -> dict[str, Any] | None:
    """Merge settings into the workspace JSONB column. Returns updated row or None."""
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
                "workspace_id": workspace_id,
                "new_settings": json.dumps(new_settings, default=str),
            },
        )
        .mappings()
        .first()
    )
    return dict(row) if row is not None else None
