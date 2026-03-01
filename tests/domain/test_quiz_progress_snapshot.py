"""Unit tests for quiz progress snapshot context loader."""

from __future__ import annotations

from datetime import datetime, timezone

from domain.chat.session_memory import load_quiz_progress_snapshot


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows=None, *, raise_exc: Exception | None = None):
        self._rows = rows or []
        self._raise_exc = raise_exc
        self.rolled_back = False

    def execute(self, *args, **kwargs):  # noqa: ARG002
        if self._raise_exc is not None:
            raise self._raise_exc
        return _FakeResult(self._rows)

    def rollback(self):
        self.rolled_back = True


def test_returns_empty_when_user_missing() -> None:
    result = load_quiz_progress_snapshot(
        _FakeSession(),
        workspace_id=1,
        user_id=None,
        concept_id=1,
    )
    assert result == ""


def test_formats_level_up_and_practice_rows() -> None:
    rows = [
        {
            "quiz_type": "level_up",
            "status": "graded",
            "concept_name": "Linear Map",
            "created_at": None,
            "score": 0.8,
            "passed": True,
            "graded_at": None,
            "item_count": 5,
        },
        {
            "quiz_type": "practice",
            "status": "ready",
            "concept_name": "Linear Map",
            "created_at": None,
            "score": None,
            "passed": None,
            "graded_at": None,
            "item_count": 0,
        },
    ]
    result = load_quiz_progress_snapshot(
        _FakeSession(rows),
        workspace_id=1,
        user_id=2,
        concept_id=3,
    )
    assert "QUIZ PROGRESS SNAPSHOT:" in result
    assert "- level_up Linear Map: score 80%, passed, 5 questions" in result
    assert "- practice Linear Map: status ready" in result


def test_returns_empty_on_query_exception_and_rolls_back() -> None:
    session = _FakeSession(raise_exc=RuntimeError("boom"))
    result = load_quiz_progress_snapshot(
        session,
        workspace_id=1,
        user_id=2,
        concept_id=3,
    )
    assert result == ""
    assert session.rolled_back is True


def test_includes_date_and_item_count() -> None:
    rows = [
        {
            "quiz_type": "practice",
            "status": "graded",
            "concept_name": "useEffect",
            "created_at": datetime(2025, 6, 10, 8, 0, 0, tzinfo=timezone.utc),
            "score": 0.6,
            "passed": False,
            "graded_at": datetime(2025, 6, 10, 8, 30, 0, tzinfo=timezone.utc),
            "item_count": 3,
        },
    ]
    result = load_quiz_progress_snapshot(
        _FakeSession(rows),
        workspace_id=1,
        user_id=2,
    )
    assert "score 60%, not passed" in result
    assert "3 questions" in result
    assert "2025-06-10" in result
