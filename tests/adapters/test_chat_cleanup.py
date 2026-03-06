"""Tests for cleanup_stale_generating_messages."""

from __future__ import annotations

from unittest.mock import MagicMock

from adapters.db.chat import cleanup_stale_generating_messages


class _FakeResult:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


def _make_session(rowcount: int = 0) -> MagicMock:
    session = MagicMock()
    session.execute.return_value = _FakeResult(rowcount)
    return session


def test_cleanup_returns_rowcount() -> None:
    db = _make_session(rowcount=3)
    assert cleanup_stale_generating_messages(db) == 3
    db.execute.assert_called_once()
    db.commit.assert_called_once()


def test_cleanup_returns_zero_when_no_stale() -> None:
    db = _make_session(rowcount=0)
    assert cleanup_stale_generating_messages(db) == 0


def test_cleanup_executes_correct_sql() -> None:
    db = _make_session()
    cleanup_stale_generating_messages(db)
    sql_arg = db.execute.call_args[0][0]
    rendered = str(sql_arg)
    assert "UPDATE chat_messages" in rendered
    assert "status = 'failed'" in rendered
    assert "status = 'generating'" in rendered
