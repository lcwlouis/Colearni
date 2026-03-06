"""Unit tests for L2.2 write-ahead persistence helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from domain.chat.session_memory import (
    create_assistant_placeholder,
    persist_turn,
    persist_user_message,
)


class _FakeSession:
    """Minimal stub standing in for sqlalchemy.orm.Session."""

    commit = MagicMock()


# ── persist_user_message ──────────────────────────────────────────────


@patch("domain.chat.session_memory.append_chat_message")
@patch("domain.chat.session_memory.assert_chat_session")
def test_persist_user_message_returns_id(mock_assert, mock_append):
    mock_append.return_value = {"message_id": 42}
    db = _FakeSession()
    msg_id = persist_user_message(
        db, session_id=1, workspace_id=10, user_id=5, text="hello"
    )
    assert msg_id == 42


@patch("domain.chat.session_memory.append_chat_message")
@patch("domain.chat.session_memory.assert_chat_session")
def test_persist_user_message_calls_assert(mock_assert, mock_append):
    mock_append.return_value = {"message_id": 1}
    db = _FakeSession()
    persist_user_message(db, session_id=1, workspace_id=10, user_id=5, text="hi")
    mock_assert.assert_called_once_with(
        db, session_id=1, workspace_id=10, user_id=5
    )


@patch("domain.chat.session_memory.append_chat_message")
@patch("domain.chat.session_memory.assert_chat_session")
def test_persist_user_message_strips_text(mock_assert, mock_append):
    mock_append.return_value = {"message_id": 1}
    db = _FakeSession()
    persist_user_message(db, session_id=1, workspace_id=10, user_id=5, text="  hi  ")
    _, kwargs = mock_append.call_args
    assert kwargs["payload"] == {"text": "hi"}


@patch("domain.chat.session_memory.append_chat_message")
@patch("domain.chat.session_memory.assert_chat_session")
def test_persist_user_message_status_complete(mock_assert, mock_append):
    mock_append.return_value = {"message_id": 1}
    db = _FakeSession()
    persist_user_message(db, session_id=1, workspace_id=10, user_id=5, text="q")
    _, kwargs = mock_append.call_args
    assert kwargs["status"] == "complete"
    assert kwargs["message_type"] == "user"


# ── create_assistant_placeholder ──────────────────────────────────────


@patch("domain.chat.session_memory.append_chat_message")
def test_create_assistant_placeholder_returns_id(mock_append):
    mock_append.return_value = {"message_id": 99}
    db = _FakeSession()
    msg_id = create_assistant_placeholder(
        db, session_id=1, workspace_id=10, user_id=5
    )
    assert msg_id == 99


@patch("domain.chat.session_memory.append_chat_message")
def test_create_assistant_placeholder_status_generating(mock_append):
    mock_append.return_value = {"message_id": 1}
    db = _FakeSession()
    create_assistant_placeholder(db, session_id=1, workspace_id=10, user_id=5)
    _, kwargs = mock_append.call_args
    assert kwargs["status"] == "generating"
    assert kwargs["message_type"] == "assistant"
    assert kwargs["payload"] == {"text": "", "status": "generating"}


# ── persist_turn backward compatibility ───────────────────────────────


@patch("domain.chat.session_memory.maybe_compact_session_context")
@patch("domain.chat.session_memory.set_chat_session_title_if_missing")
@patch("domain.chat.session_memory.generate_session_title", return_value="Title")
@patch("domain.chat.session_memory.append_chat_message")
@patch("domain.chat.session_memory.assert_chat_session")
def test_persist_turn_calls_user_then_assistant(
    mock_assert, mock_append, _title, _set_title, _compact
):
    mock_append.return_value = {"message_id": 1}
    db = MagicMock()
    persist_turn(
        db,
        workspace_id=10,
        session_id=1,
        user_id=5,
        user_text="question",
        assistant_payload={"text": "answer"},
    )
    # Two append calls: user then assistant
    assert mock_append.call_count == 2
    user_call = mock_append.call_args_list[0]
    asst_call = mock_append.call_args_list[1]
    assert user_call[1]["message_type"] == "user"
    assert user_call[1]["status"] == "complete"
    assert asst_call[1]["message_type"] == "assistant"
    assert asst_call[1]["status"] == "complete"


@patch("domain.chat.session_memory.maybe_compact_session_context")
@patch("domain.chat.session_memory.set_chat_session_title_if_missing")
@patch("domain.chat.session_memory.generate_session_title", return_value="T")
@patch("domain.chat.session_memory.append_chat_message")
@patch("domain.chat.session_memory.assert_chat_session")
def test_persist_turn_noop_when_ids_none(
    mock_assert, mock_append, _title, _set_title, _compact
):
    db = MagicMock()
    persist_turn(
        db,
        workspace_id=10,
        session_id=None,
        user_id=5,
        user_text="q",
        assistant_payload={"text": "a"},
    )
    mock_append.assert_not_called()
    persist_turn(
        db,
        workspace_id=10,
        session_id=1,
        user_id=None,
        user_text="q",
        assistant_payload={"text": "a"},
    )
    mock_append.assert_not_called()
