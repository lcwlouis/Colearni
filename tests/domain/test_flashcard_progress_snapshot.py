"""Unit tests for flashcard progress snapshot context loader."""

from __future__ import annotations

from datetime import datetime, timezone

from domain.chat.session_memory import load_flashcard_progress


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
    result = load_flashcard_progress(
        _FakeSession(),
        workspace_id=1,
        user_id=None,
    )
    assert result == ""


def test_returns_empty_when_no_rows() -> None:
    result = load_flashcard_progress(
        _FakeSession([]),
        workspace_id=1,
        user_id=2,
    )
    assert result == ""


def test_formats_flashcard_with_front_text_and_date() -> None:
    rows = [
        {
            "concept_id": 10,
            "canonical_name": "useEffect",
            "front": "What does useEffect do in React?",
            "self_rating": "good",
            "passed": True,
            "updated_at": datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        },
    ]
    result = load_flashcard_progress(
        _FakeSession(rows),
        workspace_id=1,
        user_id=2,
    )
    assert "FLASHCARD PROGRESS SNAPSHOT:" in result
    assert 'useEffect: "What does useEffect do in React?"' in result
    assert "good (passed)" in result
    assert "reviewed 2025-06-15" in result


def test_truncates_long_front_text() -> None:
    long_front = "A" * 100
    rows = [
        {
            "concept_id": 10,
            "canonical_name": "Hooks",
            "front": long_front,
            "self_rating": "unrated",
            "passed": False,
            "updated_at": None,
        },
    ]
    result = load_flashcard_progress(
        _FakeSession(rows),
        workspace_id=1,
        user_id=2,
    )
    assert "FLASHCARD PROGRESS SNAPSHOT:" in result
    # Front text should be truncated to 77 + "..."
    assert "A" * 77 + "..." in result
    assert "unrated (in progress)" in result


def test_omits_date_when_updated_at_is_none() -> None:
    rows = [
        {
            "concept_id": 10,
            "canonical_name": "useState",
            "front": "How do you declare state?",
            "self_rating": None,
            "passed": False,
            "updated_at": None,
        },
    ]
    result = load_flashcard_progress(
        _FakeSession(rows),
        workspace_id=1,
        user_id=2,
    )
    assert "reviewed" not in result
    assert "unrated (in progress)" in result


def test_handles_missing_front_text() -> None:
    rows = [
        {
            "concept_id": 10,
            "canonical_name": "useRef",
            "front": None,
            "self_rating": "easy",
            "passed": True,
            "updated_at": None,
        },
    ]
    result = load_flashcard_progress(
        _FakeSession(rows),
        workspace_id=1,
        user_id=2,
    )
    # Should not include empty quotes
    assert "useRef:" in result
    assert '""' not in result
    assert "easy (passed)" in result


def test_returns_empty_on_query_exception_and_rolls_back() -> None:
    session = _FakeSession(raise_exc=RuntimeError("boom"))
    result = load_flashcard_progress(
        session,
        workspace_id=1,
        user_id=2,
    )
    assert result == ""
    assert session.rolled_back is True
