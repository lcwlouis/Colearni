"""Chat session domain services."""

from __future__ import annotations

from adapters.db.chat import (
    ChatNotFoundError,
    create_chat_session,
    delete_chat_session,
    list_chat_messages,
    list_chat_sessions,
)
from sqlalchemy.orm import Session


class ChatSessionNotFoundError(ValueError):
    pass


def create_session(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    title: str | None,
) -> dict[str, object]:
    return create_chat_session(
        session,
        workspace_id=workspace_id,
        user_id=user_id,
        title=title,
    )


def list_sessions(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    limit: int,
) -> dict[str, object]:
    return {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "sessions": list_chat_sessions(
            session,
            workspace_id=workspace_id,
            user_id=user_id,
            limit=limit,
        ),
    }


def get_messages(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    session_id: int,
    limit: int,
) -> dict[str, object]:
    try:
        messages = list_chat_messages(
            session,
            session_id=session_id,
            workspace_id=workspace_id,
            user_id=user_id,
            limit=limit,
        )
    except ChatNotFoundError as exc:
        raise ChatSessionNotFoundError(str(exc)) from exc
    return {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "session_id": session_id,
        "messages": messages,
    }


def delete_session(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    session_id: int,
) -> None:
    try:
        delete_chat_session(
            session,
            session_id=session_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )
    except ChatNotFoundError as exc:
        raise ChatSessionNotFoundError(str(exc)) from exc


__all__ = [
    "ChatSessionNotFoundError",
    "create_session",
    "delete_session",
    "get_messages",
    "list_sessions",
]
