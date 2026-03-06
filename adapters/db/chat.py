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
    concept_id: int | None = None,
) -> dict[str, Any]:
    # If concept_id provided and no explicit title, derive from concept name
    effective_title = (title or "").strip() or None
    if concept_id and not effective_title and hasattr(session, "execute"):
        concept_row = (
            session.execute(
                text("SELECT canonical_name FROM concepts_canon WHERE id = :cid AND workspace_id = :wid"),
                {"cid": concept_id, "wid": workspace_id},
            )
            .mappings()
            .first()
        )
        if concept_row:
            effective_title = str(concept_row["canonical_name"]).strip()

    row = (
        session.execute(
            text(
                """
                INSERT INTO chat_sessions (workspace_id, user_id, title, concept_id)
                VALUES (:workspace_id, :user_id, :title, :concept_id)
                RETURNING id, public_id, workspace_id, user_id, title, concept_id, created_at, updated_at
                """
            ),
            {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "title": effective_title,
                "concept_id": concept_id,
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
        "concept_id": int(row["concept_id"]) if row["concept_id"] else None,
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
                    s.concept_id,
                    COALESCE(MAX(m.created_at), s.updated_at) AS last_activity_at
                FROM chat_sessions s
                LEFT JOIN chat_messages m
                  ON m.session_id = s.id
                WHERE s.workspace_id = :workspace_id
                  AND s.user_id = :user_id
                GROUP BY s.id, s.public_id, s.workspace_id, s.user_id, s.title, s.concept_id, s.updated_at
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
            "concept_id": int(row["concept_id"]) if row["concept_id"] else None,
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
    status: str = "complete",
) -> dict[str, Any]:
    row = (
        session.execute(
            text(
                """
                INSERT INTO chat_messages (session_id, workspace_id, user_id, type, payload, status)
                VALUES (
                    :session_id,
                    :workspace_id,
                    :user_id,
                    :message_type,
                    CAST(:payload AS jsonb),
                    :status
                )
                RETURNING id, session_id, type, payload, status, created_at
                """
            ),
            {
                "session_id": session_id,
                "workspace_id": workspace_id,
                "user_id": user_id,
                "message_type": message_type,
                "payload": _as_json(payload),
                "status": status,
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
        "status": str(row["status"]),
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
                SELECT id, session_id, type, payload, status, created_at
                FROM chat_messages
                WHERE session_id = :session_id
                  AND status != 'superseded'
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
            "status": str(row["status"]),
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
                  AND status NOT IN ('generating', 'failed', 'superseded')
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
                  AND status NOT IN ('generating', 'failed', 'superseded')
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


def update_unbound_session_title(
    session: Session,
    *,
    session_id: int,
    title: str,
) -> None:
    """Update title for unbound sessions (no concept_id) to reflect topic drift."""
    normalized = title.strip()
    if not normalized:
        return
    session.execute(
        text(
            """
            UPDATE chat_sessions
            SET title = :title, updated_at = now()
            WHERE id = :session_id
              AND concept_id IS NULL
            """
        ),
        {"session_id": session_id, "title": normalized[:120]},
    )


def get_chat_session_concept_name(session: Session, *, session_id: int) -> str | None:
    """Return the canonical name of the concept bound to a chat session, or None."""
    if not hasattr(session, "execute"):
        return None
    row = (
        session.execute(
            text(
                """
                SELECT c.canonical_name
                FROM chat_sessions s
                JOIN concepts_canon c ON c.id = s.concept_id
                WHERE s.id = :session_id
                  AND s.concept_id IS NOT NULL
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
    return str(row["canonical_name"])


def get_chat_session_concept_id(session: Session, *, session_id: int) -> int | None:
    """Return the concept_id bound to a chat session, or None."""
    if not hasattr(session, "execute"):
        return None
    row = (
        session.execute(
            text("SELECT concept_id FROM chat_sessions WHERE id = :sid AND concept_id IS NOT NULL LIMIT 1"),
            {"sid": session_id},
        )
        .mappings()
        .first()
    )
    return int(row["concept_id"]) if row else None


def finalize_assistant_message(
    session: Session,
    *,
    message_id: int,
    payload: dict[str, Any],
) -> bool:
    """Atomically mark a *generating* message as complete with its final payload.

    Returns True when a row was updated, False when the message was already
    finalized or in a non-generating state (idempotent).
    """
    result = session.execute(
        text(
            """
            UPDATE chat_messages
            SET status = 'complete', payload = CAST(:payload AS jsonb)
            WHERE id = :message_id
              AND status = 'generating'
            """
        ),
        {"message_id": message_id, "payload": _as_json(payload)},
    )
    return (result.rowcount or 0) > 0


def fail_assistant_message(
    session: Session,
    *,
    message_id: int,
    partial_text: str = "",
) -> bool:
    """Atomically mark a *generating* message as failed.

    Stores any partial text produced so far.  Returns True when a row was
    updated, False when already finalized (idempotent).
    """
    fail_payload: dict[str, Any] = {"text": partial_text, "error": True}
    result = session.execute(
        text(
            """
            UPDATE chat_messages
            SET status = 'failed', payload = CAST(:payload AS jsonb)
            WHERE id = :message_id
              AND status = 'generating'
            """
        ),
        {"message_id": message_id, "payload": _as_json(fail_payload)},
    )
    return (result.rowcount or 0) > 0


def cleanup_stale_generating_messages(db: Session) -> int:
    """Mark orphaned 'generating' messages as 'failed'.

    Called on app startup to clean up messages from interrupted streams.
    Returns the count of cleaned-up messages.
    """
    result = db.execute(
        text("UPDATE chat_messages SET status = 'failed' WHERE status = 'generating'")
    )
    db.commit()
    return result.rowcount


def _as_json(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=True)


def mark_message_superseded(
    session: Session,
    *,
    message_id: int,
) -> bool:
    """Mark a *complete* assistant message as superseded (for regeneration).

    Returns True when a row was updated, False when the message was not
    in a valid state for superseding (idempotent).
    """
    result = session.execute(
        text(
            """
            UPDATE chat_messages
            SET status = 'superseded'
            WHERE id = :message_id
              AND status = 'complete'
              AND role = 'assistant'
            """
        ),
        {"message_id": message_id},
    )
    return (result.rowcount or 0) > 0


def get_preceding_user_message(
    session: Session,
    *,
    message_id: int,
    session_id: int,
) -> dict[str, Any] | None:
    """Return the user message immediately before *message_id* in the session.

    Returns a dict with ``id``, ``content``, ``role`` or None if not found.
    """
    row = session.execute(
        text(
            """
            SELECT id, role, payload->>'text' AS content
            FROM chat_messages
            WHERE chat_session_id = :session_id
              AND id < :message_id
              AND role = 'user'
            ORDER BY id DESC
            LIMIT 1
            """
        ),
        {"session_id": session_id, "message_id": message_id},
    ).mappings().first()
    if row is None:
        return None
    return {"id": row["id"], "role": row["role"], "content": row["content"]}


__all__ = [
    "cleanup_stale_generating_messages",
    "ChatNotFoundError",
    "append_chat_message",
    "assert_chat_session",
    "count_chat_messages",
    "create_chat_session",
    "delete_chat_session",
    "fail_assistant_message",
    "finalize_assistant_message",
    "get_chat_session_concept_name",
    "get_preceding_user_message",
    "latest_system_summary",
    "list_chat_messages",
    "list_chat_sessions",
    "list_recent_chat_messages",
    "mark_message_superseded",
    "resolve_session_by_public_id",
    "set_chat_session_title_if_missing",
    "update_session_title",
    "update_unbound_session_title",
]
