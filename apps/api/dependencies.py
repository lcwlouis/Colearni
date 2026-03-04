"""FastAPI dependencies for auth and workspace membership."""

from __future__ import annotations

from dataclasses import dataclass

from adapters.db.auth import UserRow, get_user_for_auth_token
from adapters.db.dependencies import get_db_session
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session


def _extract_bearer_token(request: Request) -> str | None:
    """Extract bearer token from Authorization header or cookie."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip() or None
    return request.cookies.get("session_token")


def get_current_user(
    request: Request,
    db: Session = Depends(get_db_session),
) -> UserRow:
    """Resolve authenticated user from bearer token. Raises 401 if invalid."""
    token = _extract_bearer_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    user = get_user_for_auth_token(db, raw_token=token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session.",
        )
    return user


def get_optional_user(
    request: Request,
    db: Session = Depends(get_db_session),
) -> UserRow | None:
    """Resolve user if token present; returns None for unauthenticated."""
    token = _extract_bearer_token(request)
    if not token:
        return None
    return get_user_for_auth_token(db, raw_token=token)


# ── Workspace context (S3+S4) ─────────────────────────────────────────


@dataclass(frozen=True)
class WorkspaceContext:
    """Resolved workspace + authenticated user for workspace-scoped routes."""

    workspace_id: int
    user: UserRow


def get_workspace_context(
    ws_id: str,
    user: UserRow = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> WorkspaceContext:
    """Resolve workspace UUID from path, verify membership, return context."""
    row = (
        db.execute(
            text("SELECT id FROM workspaces WHERE public_id::text = :pid LIMIT 1"),
            {"pid": ws_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found.",
        )
    wid = int(row["id"])
    member = (
        db.execute(
            text(
                "SELECT 1 FROM workspace_members "
                "WHERE workspace_id = :wid AND user_id = :uid LIMIT 1"
            ),
            {"wid": wid, "uid": user.id},
        )
        .mappings()
        .first()
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this workspace.",
        )
    return WorkspaceContext(workspace_id=wid, user=user)


def require_workspace_member(
    workspace_id: int,
    user: UserRow = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> UserRow:
    """Verify user is a member of the workspace. Raises 403 if not."""
    row = (
        db.execute(
            text(
                """
                SELECT 1
                FROM workspace_members
                WHERE workspace_id = :workspace_id AND user_id = :user_id
                LIMIT 1
                """
            ),
            {"workspace_id": workspace_id, "user_id": user.id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this workspace.",
        )
    return user


__all__ = [
    "WorkspaceContext",
    "get_current_user",
    "get_optional_user",
    "get_workspace_context",
    "require_workspace_member",
]
