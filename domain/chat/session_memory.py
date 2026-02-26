"""Chat session persistence and context compaction helpers."""

from __future__ import annotations

from typing import Any

from adapters.db.chat import (
    append_chat_message,
    assert_chat_session,
    count_chat_messages,
    latest_system_summary,
    list_recent_chat_messages,
    set_chat_session_title_if_missing,
)
from sqlalchemy.orm import Session

COMPACTION_THRESHOLD = 40
COMPACTION_KEEP_RECENT = 16
SUMMARY_SOURCE_LIMIT = 24


def load_history_text(
    session: Session,
    *,
    session_id: int | None,
) -> str:
    if session_id is None:
        return ""

    summary = latest_system_summary(session, session_id=session_id) or ""
    recent = list_recent_chat_messages(session, session_id=session_id, limit=10)
    snippets: list[str] = []
    if summary:
        snippets.append(summary)
    for message in recent:
        payload = message.get("payload") if isinstance(message, dict) else {}
        if not isinstance(payload, dict):
            continue
        text_value = str(payload.get("text", "")).strip()
        if text_value:
            snippets.append(text_value)
    return "\n".join(snippets)


def persist_turn(
    session: Session,
    *,
    workspace_id: int,
    session_id: int | None,
    user_id: int | None,
    user_text: str,
    assistant_payload: dict[str, Any],
) -> None:
    if session_id is None:
        return
    if user_id is None:
        return

    assert_chat_session(
        session,
        session_id=session_id,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    append_chat_message(
        session,
        session_id=session_id,
        workspace_id=workspace_id,
        user_id=user_id,
        message_type="user",
        payload={"text": user_text.strip()},
    )
    append_chat_message(
        session,
        session_id=session_id,
        workspace_id=workspace_id,
        user_id=user_id,
        message_type="assistant",
        payload=assistant_payload,
    )
    set_chat_session_title_if_missing(
        session,
        session_id=session_id,
        title=user_text,
    )
    maybe_compact_session_context(
        session,
        workspace_id=workspace_id,
        session_id=session_id,
        user_id=user_id,
    )
    session.commit()


def maybe_compact_session_context(
    session: Session,
    *,
    workspace_id: int,
    session_id: int,
    user_id: int,
    threshold: int = COMPACTION_THRESHOLD,
    keep_recent: int = COMPACTION_KEEP_RECENT,
) -> None:
    total = count_chat_messages(session, session_id=session_id)
    if total <= threshold:
        return

    recent = list_recent_chat_messages(session, session_id=session_id, limit=keep_recent)
    if len(recent) >= total:
        return

    source = list_recent_chat_messages(
        session,
        session_id=session_id,
        limit=min(SUMMARY_SOURCE_LIMIT, total - keep_recent),
    )
    lines: list[str] = []
    for item in source:
        payload = item.get("payload") if isinstance(item, dict) else {}
        if not isinstance(payload, dict):
            continue
        text_value = str(payload.get("text", "")).strip()
        if not text_value:
            continue
        role = str(item.get("type", ""))
        if role == "user":
            lines.append(f"User: {text_value}")
        elif role == "assistant":
            lines.append(f"Tutor: {text_value}")

    if not lines:
        return

    summary = " ".join(lines)
    if len(summary) > 1200:
        summary = summary[:1197] + "..."

    append_chat_message(
        session,
        session_id=session_id,
        workspace_id=workspace_id,
        user_id=user_id,
        message_type="system",
        payload={
            "summary": summary,
            "kind": "context_compaction",
            "source_count": len(lines),
        },
    )


__all__ = [
    "load_history_text",
    "maybe_compact_session_context",
    "persist_turn",
]
