"""Tests for L2.3 — finalize_assistant_message / fail_assistant_message."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from adapters.db.chat import fail_assistant_message, finalize_assistant_message


class _FakeResult:
    """Minimal stand-in for a SQLAlchemy CursorResult."""

    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


def _make_session(rowcount: int = 1) -> MagicMock:
    session = MagicMock()
    session.execute.return_value = _FakeResult(rowcount)
    return session


# ── finalize_assistant_message ────────────────────────────────────────


class TestFinalizeAssistantMessage:
    def test_returns_true_when_row_updated(self) -> None:
        db = _make_session(rowcount=1)
        result = finalize_assistant_message(
            db, message_id=42, payload={"text": "hello"}
        )
        assert result is True
        db.execute.assert_called_once()

    def test_returns_false_when_no_row_updated(self) -> None:
        db = _make_session(rowcount=0)
        result = finalize_assistant_message(
            db, message_id=42, payload={"text": "hello"}
        )
        assert result is False

    def test_idempotent_already_complete(self) -> None:
        """Calling finalize on an already-complete message is a no-op."""
        db = _make_session(rowcount=0)
        assert finalize_assistant_message(
            db, message_id=99, payload={"text": "done"}
        ) is False

    def test_payload_passed_as_json(self) -> None:
        db = _make_session(rowcount=1)
        payload: dict[str, Any] = {"text": "answer", "citations": [1, 2]}
        finalize_assistant_message(db, message_id=1, payload=payload)
        call_params = db.execute.call_args[0][1]
        assert '"text": "answer"' in call_params["payload"]
        assert call_params["message_id"] == 1


# ── fail_assistant_message ────────────────────────────────────────────


class TestFailAssistantMessage:
    def test_returns_true_when_row_updated(self) -> None:
        db = _make_session(rowcount=1)
        result = fail_assistant_message(db, message_id=7)
        assert result is True
        db.execute.assert_called_once()

    def test_returns_false_when_no_row_updated(self) -> None:
        db = _make_session(rowcount=0)
        result = fail_assistant_message(db, message_id=7)
        assert result is False

    def test_idempotent_already_failed(self) -> None:
        db = _make_session(rowcount=0)
        assert fail_assistant_message(db, message_id=7) is False

    def test_partial_text_included_in_payload(self) -> None:
        db = _make_session(rowcount=1)
        fail_assistant_message(db, message_id=5, partial_text="partial answer")
        call_params = db.execute.call_args[0][1]
        assert '"text": "partial answer"' in call_params["payload"]
        assert '"error": true' in call_params["payload"]

    def test_default_partial_text_is_empty(self) -> None:
        db = _make_session(rowcount=1)
        fail_assistant_message(db, message_id=5)
        call_params = db.execute.call_args[0][1]
        assert '"text": ""' in call_params["payload"]


# ── Domain wrappers delegate correctly ────────────────────────────────


class TestDomainWrappers:
    def test_domain_finalize_delegates(self) -> None:
        from domain.chat.session_memory import (
            finalize_assistant_message as domain_finalize,
        )

        db = _make_session(rowcount=1)
        assert domain_finalize(db, message_id=1, payload={"text": "ok"}) is True

    def test_domain_fail_delegates(self) -> None:
        from domain.chat.session_memory import (
            fail_assistant_message as domain_fail,
        )

        db = _make_session(rowcount=1)
        assert domain_fail(db, message_id=1, partial_text="oops") is True
