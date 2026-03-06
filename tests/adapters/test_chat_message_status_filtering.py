"""Tests for L2.5 – message loading filtered by status column.

Verifies:
- LLM context queries (list_recent_chat_messages, latest_system_summary)
  exclude generating, failed, and superseded messages.
- Frontend queries (list_chat_messages) include generating and failed
  but exclude superseded; response includes the status field.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from adapters.db.chat import (
    latest_system_summary,
    list_chat_messages,
    list_recent_chat_messages,
)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE chat_sessions (
                    id INTEGER PRIMARY KEY,
                    workspace_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    workspace_id INTEGER NOT NULL,
                    user_id INTEGER,
                    type TEXT NOT NULL,
                    payload TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'complete',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text("INSERT INTO chat_sessions (id, workspace_id, user_id) VALUES (1, 1, 1)")
        )
        conn.commit()
    LocalSession = sessionmaker(bind=engine)
    session = LocalSession()
    yield session
    session.close()


def _insert(session: Session, msg_type: str, status: str, payload: dict | None = None) -> None:
    session.execute(
        text(
            "INSERT INTO chat_messages (session_id, workspace_id, user_id, type, payload, status)"
            " VALUES (1, 1, 1, :t, :p, :s)"
        ),
        {"t": msg_type, "p": json.dumps(payload or {"text": f"{status} msg"}), "s": status},
    )
    session.flush()


# ── LLM context: list_recent_chat_messages ────────────────────────────


class TestListRecentExcludesNonComplete:
    def test_excludes_generating(self, db_session: Session) -> None:
        _insert(db_session, "assistant", "generating")
        _insert(db_session, "user", "complete")
        rows = list_recent_chat_messages(db_session, session_id=1, limit=50)
        assert len(rows) == 1
        assert rows[0]["type"] == "user"

    def test_excludes_failed(self, db_session: Session) -> None:
        _insert(db_session, "assistant", "failed")
        _insert(db_session, "user", "complete")
        rows = list_recent_chat_messages(db_session, session_id=1, limit=50)
        assert len(rows) == 1

    def test_excludes_superseded(self, db_session: Session) -> None:
        _insert(db_session, "assistant", "superseded")
        _insert(db_session, "user", "complete")
        rows = list_recent_chat_messages(db_session, session_id=1, limit=50)
        assert len(rows) == 1

    def test_includes_complete(self, db_session: Session) -> None:
        _insert(db_session, "user", "complete")
        _insert(db_session, "assistant", "complete")
        rows = list_recent_chat_messages(db_session, session_id=1, limit=50)
        assert len(rows) == 2


# ── LLM context: latest_system_summary ────────────────────────────────


class TestLatestSystemSummaryExcludesNonComplete:
    def test_excludes_failed_summary(self, db_session: Session) -> None:
        _insert(db_session, "system", "failed", {"summary": "bad"})
        assert latest_system_summary(db_session, session_id=1) is None

    def test_excludes_superseded_summary(self, db_session: Session) -> None:
        _insert(db_session, "system", "superseded", {"summary": "old"})
        assert latest_system_summary(db_session, session_id=1) is None

    def test_excludes_generating_summary(self, db_session: Session) -> None:
        _insert(db_session, "system", "generating", {"summary": "wip"})
        assert latest_system_summary(db_session, session_id=1) is None


# ── Frontend: list_chat_messages ──────────────────────────────────────


class TestListChatMessagesFrontendFiltering:
    def test_includes_generating(self, db_session: Session) -> None:
        _insert(db_session, "assistant", "generating")
        rows = list_chat_messages(
            db_session, session_id=1, workspace_id=1, user_id=1, limit=50
        )
        assert len(rows) == 1
        assert rows[0]["status"] == "generating"

    def test_includes_failed(self, db_session: Session) -> None:
        _insert(db_session, "assistant", "failed")
        rows = list_chat_messages(
            db_session, session_id=1, workspace_id=1, user_id=1, limit=50
        )
        assert len(rows) == 1
        assert rows[0]["status"] == "failed"

    def test_excludes_superseded(self, db_session: Session) -> None:
        _insert(db_session, "assistant", "superseded")
        _insert(db_session, "user", "complete")
        rows = list_chat_messages(
            db_session, session_id=1, workspace_id=1, user_id=1, limit=50
        )
        assert len(rows) == 1
        assert rows[0]["type"] == "user"

    def test_status_in_response(self, db_session: Session) -> None:
        _insert(db_session, "user", "complete")
        rows = list_chat_messages(
            db_session, session_id=1, workspace_id=1, user_id=1, limit=50
        )
        assert "status" in rows[0]
        assert rows[0]["status"] == "complete"
