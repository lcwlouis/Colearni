"""Tests for DB dependency lifecycle."""

import pytest
from adapters.db import dependencies


class DummySession:
    """Minimal session stub for dependency tests."""

    def __init__(self) -> None:
        self.closed = False
        self.rollback_called = False
        self.commit_called = False

    def commit(self) -> None:
        self.commit_called = True

    def rollback(self) -> None:
        self.rollback_called = True

    def close(self) -> None:
        self.closed = True


def test_get_db_session_closes_session_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dependency should close sessions after request completion."""
    session = DummySession()
    monkeypatch.setattr(dependencies, "new_session", lambda: session)

    generator = dependencies.get_db_session()
    yielded = next(generator)
    assert yielded is session

    with pytest.raises(StopIteration):
        next(generator)

    assert session.closed is True
    assert session.commit_called is True
    assert session.rollback_called is False


def test_get_db_session_rolls_back_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dependency should rollback and close session on unhandled errors."""
    session = DummySession()
    monkeypatch.setattr(dependencies, "new_session", lambda: session)

    generator = dependencies.get_db_session()
    yielded = next(generator)
    assert yielded is session

    with pytest.raises(RuntimeError):
        generator.throw(RuntimeError("boom"))

    assert session.rollback_called is True
    assert session.closed is True
