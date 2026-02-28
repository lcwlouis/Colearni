"""Chat session/message query helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class ChatNotFoundError(ValueError):
    """Raised when chat session cannot be found in workspace/user scope."""


def create_chat_session(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    title: str | None,
) -> dict[str, Any]:
    row = (
        session.execute(
            text(
                """
                INSERT INTO chat_sessions (workspace_id, user_id, title)
                VALUES (:workspace_id, :user_id, :title)
                RETURNING id, public_id, workspace_id, user_id, title, created_at, updated_at
                """
            ),
            {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "title": (title or "").strip() or None,
            },
        )
        .mappings()
        .one()
    )
    session.commit()
    return {
        "session_id": int(row["id"]),
        "public_id": str(row["public_id"]),
        "workspace_id": int(row["workspace_id"]),
        "user_id": int(row["user_id"]),
        "title": str(row["title"] or "").strip() or None,
        "last_activity_at": row["updated_at"],
    }


def list_chat_sessions(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    limit: int,
) -> list[dict[str, Any]]:
    rows = (
        session.execute(
            text(
                """
                SELECT
                    s.id AS session_id,
                    s.public_id,
                    s.workspace_id,
                    s.user_id,
                    s.title,
                    COALESCE(MAX(m.created_at), s.updated_at) AS last_activity_at
                FROM chat_sessions s
                LEFT JOIN chat_messages m
                  ON m.session_id = s.id
                WHERE s.workspace_id = :workspace_id
                  AND s.user_id = :user_id
                GROUP BY s.id, s.public_id, s.workspace_id, s.user_id, s.title, s.updated_at
                ORDER BY COALESCE(MAX(m.created_at), s.updated_at) DESC, s.id DESC
                LIMIT :limit
                """
            ),
            {"workspace_id": workspace_id, "user_id": user_id, "limit": limit},
        )
        .mappings()
        .all()
    )
    return [
        {
            "session_id": int(row["session_id"]),
            "public_id": str(row["public_id"]),
            "workspace_id": int(row["workspace_id"]),
            "user_id": int(row["user_id"]),
            "title": str(row["title"] or "").strip() or None,
            "last_activity_at": row["last_activity_at"],
        }
        for row in rows
    ]


def assert_chat_session(
    session: Session,
    *,
    session_id: int,
    workspace_id: int,
    user_id: int,
) -> None:
    row = (
        session.execute(
            text(
                """
                SELECT id
                FROM chat_sessions
                WHERE id = :session_id
                  AND workspace_id = :workspace_id
                  AND user_id = :user_id
                LIMIT 1
                """
            ),
            {"session_id": session_id, "workspace_id": workspace_id, "user_id": user_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ChatNotFoundError("Chat session not found in workspace for user.")


def resolve_session_by_public_id(
    session: Session,
    *,
    public_id: str,
    workspace_id: int,
    user_id: int,
) -> int:
    """Resolve a session UUID public_id to the internal integer ID.

    Raises ChatNotFoundError when no matching session exists.
    """
    row = (
        session.execute(
            text(
                """
                SELECT id
                FROM chat_sessions
                WHERE public_id = CAST(:public_id AS uuid)
                  AND workspace_id = :workspace_id
                  AND user_id = :user_id
                LIMIT 1
                """
            ),
            {"public_id": public_id, "workspace_id": workspace_id, "user_id": user_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ChatNotFoundError("Chat session not found in workspace for user.")
    return int(row["id"])


def append_chat_message(
    session: Session,
    *,
    session_id: int,
    workspace_id: int,
    user_id: int | None,
    message_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    row = (
        session.execute(
            text(
                """
                INSERT INTO chat_messages (session_id, workspace_id, user_id, type, payload)
                VALUES (
                    :session_id,
                    :workspace_id,
                    :user_id,
                    :message_type,
                    CAST(:payload AS jsonb)
                )
                RETURNING id, session_id, type, payload, created_at
                """
            ),
            {
                "session_id": session_id,
                "workspace_id": workspace_id,
                "user_id": user_id,
                "message_type": message_type,
                "payload": _as_json(payload),
            },
        )
        .mappings()
        .one()
    )
    session.execute(
        text(
            """
            UPDATE chat_sessions
            SET updated_at = now()
            WHERE id = :session_id
            """
        ),
        {"session_id": session_id},
    )
    return {
        "message_id": int(row["id"]),
        "session_id": int(row["session_id"]),
        "type": str(row["type"]),
        "payload": row["payload"] if isinstance(row["payload"], dict) else {},
        "created_at": row["created_at"],
    }


def list_chat_messages(
    session: Session,
    *,
    session_id: int,
    workspace_id: int,
    user_id: int,
    limit: int,
) -> list[dict[str, Any]]:
    assert_chat_session(
        session,
        session_id=session_id,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    rows = (
        session.execute(
            text(
                """
                SELECT id, session_id, type, payload, created_at
                FROM chat_messages
                WHERE session_id = :session_id
                ORDER BY created_at ASC, id ASC
                LIMIT :limit
                """
            ),
            {"session_id": session_id, "limit": limit},
        )
        .mappings()
        .all()
    )
    return [
        {
            "message_id": int(row["id"]),
            "session_id": int(row["session_id"]),
            "type": str(row["type"]),
            "payload": row["payload"] if isinstance(row["payload"], dict) else {},
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def delete_chat_session(
    session: Session,
    *,
    session_id: int,
    workspace_id: int,
    user_id: int,
) -> None:
    assert_chat_session(
        session,
        session_id=session_id,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    session.execute(
        text(
            """
            UPDATE quizzes
            SET session_id = NULL, updated_at = now()
            WHERE session_id = :session_id
            """
        ),
        {"session_id": session_id},
    )
    session.execute(
        text(
            """
            DELETE FROM chat_messages
            WHERE session_id = :session_id
            """
        ),
        {"session_id": session_id},
    )
    session.execute(
        text(
            """
            DELETE FROM chat_sessions
            WHERE id = :session_id
            """
        ),
        {"session_id": session_id},
    )
    session.commit()


def list_recent_chat_messages(
    session: Session,
    *,
    session_id: int,
    limit: int,
) -> list[dict[str, Any]]:
    rows = (
        session.execute(
            text(
                """
                SELECT id, type, payload, created_at
                FROM chat_messages
                WHERE session_id = :session_id
                ORDER BY created_at DESC, id DESC
                LIMIT :limit
                """
            ),
            {"session_id": session_id, "limit": limit},
        )
        .mappings()
        .all()
    )
    items = [
        {
            "message_id": int(row["id"]),
            "type": str(row["type"]),
            "payload": row["payload"] if isinstance(row["payload"], dict) else {},
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    items.reverse()
    return items


def count_chat_messages(session: Session, *, session_id: int) -> int:
    count = session.execute(
        text(
            """
            SELECT count(*)
            FROM chat_messages
            WHERE session_id = :session_id
            """
        ),
        {"session_id": session_id},
    ).scalar_one()
    return int(count)


def latest_system_summary(session: Session, *, session_id: int) -> str | None:
    row = (
        session.execute(
            text(
                """
                SELECT payload
                FROM chat_messages
                WHERE session_id = :session_id
                  AND type = 'system'
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """
            ),
            {"session_id": session_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    payload = row["payload"] if isinstance(row["payload"], dict) else {}
    summary = str(payload.get("summary", "")).strip()
    return summary or None


def set_chat_session_title_if_missing(
    session: Session,
    *,
    session_id: int,
    title: str,
) -> None:
    normalized = title.strip()
    if not normalized:
        return
    session.execute(
        text(
            """
            UPDATE chat_sessions
            SET title = :title, updated_at = now()
            WHERE id = :session_id
              AND (title IS NULL OR btrim(title) = '')
            """
        ),
        {"session_id": session_id, "title": normalized[:120]},
    )


def update_session_title(
    session: Session,
    *,
    session_id: int,
    workspace_id: int,
    user_id: int,
    title: str,
) -> dict[str, Any]:
    """Unconditionally update session title (user rename)."""
    assert_chat_session(
        session,
        session_id=session_id,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    normalized = (title or "").strip()[:120] or None
    row = (
        session.execute(
            text(
                """
                UPDATE chat_sessions
                SET title = :title, updated_at = now()
                WHERE id = :session_id
                RETURNING id, public_id, workspace_id, user_id, title, updated_at
                """
            ),
            {"session_id": session_id, "title": normalized},
        )
        .mappings()
        .one()
    )
    session.commit()
    return {
        "session_id": int(row["id"]),
        "public_id": str(row["public_id"]),
        "workspace_id": int(row["workspace_id"]),
        "user_id": int(row["user_id"]),
        "title": str(row["title"] or "").strip() or None,
        "last_activity_at": row["updated_at"],
    }


def _as_json(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=True)


__all__ = [
    "ChatNotFoundError",
    "append_chat_message",
    "assert_chat_session",
    "count_chat_messages",
    "create_chat_session",
    "delete_chat_session",
    "latest_system_summary",
    "list_chat_messages",
    "list_chat_sessions",
    "list_recent_chat_messages",
    "resolve_session_by_public_id",
    "set_chat_session_title_if_missing",
    "update_session_title",
]
