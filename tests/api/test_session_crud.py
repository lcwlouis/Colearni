"""Tests for chat session CRUD API routes (S32).

Verifies create → list round-trip, delete → 404 on re-access, and
delete unlinking side-effects using dependency overrides.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Generator

import pytest
from adapters.db.chat import ChatNotFoundError
from adapters.db.dependencies import get_db_session
from apps.api.dependencies import WorkspaceContext, get_workspace_context
from apps.api.main import app
from fastapi import status
from fastapi.testclient import TestClient


_FAKE_USER = type(
    "FakeUser", (), {"id": 3, "public_id": "u-crud", "email": "crud@test.com", "display_name": None}
)()
_WS_CTX = WorkspaceContext(workspace_id=10, user=_FAKE_USER)
_WS_ID = "ws-crud-uuid"


# ────────────────────────────────────────────────────────────────────
# In-memory chat store used across CRUD tests
# ────────────────────────────────────────────────────────────────────

class _InMemoryDB:
    """Minimal in-memory stand-in for chat session DB operations."""

    def __init__(self) -> None:
        self._sessions: dict[int, dict[str, Any]] = {}
        self._messages: dict[int, list[dict[str, Any]]] = {}
        self._seq = 0
        self._msg_seq = 0

    def create(self, workspace_id: int, user_id: int, title: str | None) -> dict[str, Any]:
        self._seq += 1
        pub_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "session_id": self._seq,
            "public_id": pub_id,
            "workspace_id": workspace_id,
            "user_id": user_id,
            "title": title,
            "last_activity_at": now,
        }
        self._sessions[self._seq] = record
        self._messages[self._seq] = []
        return record

    def list_sessions(self, workspace_id: int, user_id: int, limit: int) -> list[dict[str, Any]]:
        result = [
            s for s in self._sessions.values()
            if s["workspace_id"] == workspace_id and s["user_id"] == user_id
        ]
        result.sort(key=lambda s: s["last_activity_at"], reverse=True)
        return result[:limit]

    def resolve(self, public_id: str, workspace_id: int, user_id: int) -> int:
        for s in self._sessions.values():
            if s["public_id"] == public_id and s["workspace_id"] == workspace_id and s["user_id"] == user_id:
                return s["session_id"]
        raise ChatNotFoundError("Session not found")

    def get_messages(self, session_id: int, workspace_id: int, user_id: int, limit: int) -> list[dict[str, Any]]:
        if session_id not in self._sessions:
            raise ChatNotFoundError("Session not found")
        s = self._sessions[session_id]
        if s["workspace_id"] != workspace_id or s["user_id"] != user_id:
            raise ChatNotFoundError("Session not found")
        return self._messages.get(session_id, [])[:limit]

    def delete(self, session_id: int, workspace_id: int, user_id: int) -> None:
        if session_id not in self._sessions:
            raise ChatNotFoundError("Session not found")
        s = self._sessions[session_id]
        if s["workspace_id"] != workspace_id or s["user_id"] != user_id:
            raise ChatNotFoundError("Session not found")
        del self._sessions[session_id]
        self._messages.pop(session_id, None)

    def append_message(self, session_id: int, msg_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._msg_seq += 1
        record = {
            "message_id": self._msg_seq,
            "session_id": session_id,
            "type": msg_type,
            "payload": payload,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._messages.setdefault(session_id, []).append(record)
        return record


@pytest.fixture()
def mem_db() -> _InMemoryDB:
    return _InMemoryDB()


@pytest.fixture()
def client(monkeypatch: Any, mem_db: _InMemoryDB) -> Generator[TestClient, None, None]:
    """TestClient with dependency overrides wiring the in-memory DB store."""

    def _override_db() -> Any:
        yield object()

    # Wire route-level imports to in-memory store
    monkeypatch.setattr(
        "apps.api.routes.chat.create_session",
        lambda _session, *, workspace_id, user_id, title, concept_id=None: mem_db.create(workspace_id, user_id, title),
    )
    monkeypatch.setattr(
        "apps.api.routes.chat.list_sessions",
        lambda _session, *, workspace_id, user_id, limit: {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "sessions": mem_db.list_sessions(workspace_id, user_id, limit),
        },
    )
    monkeypatch.setattr(
        "apps.api.routes.chat.get_messages",
        lambda _session, *, workspace_id, user_id, session_id, limit: {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "session_id": session_id,
            "messages": mem_db.get_messages(session_id, workspace_id, user_id, limit),
        },
    )
    monkeypatch.setattr(
        "apps.api.routes.chat.delete_session",
        lambda _session, *, workspace_id, user_id, session_id: mem_db.delete(session_id, workspace_id, user_id),
    )
    monkeypatch.setattr(
        "apps.api.routes.chat.resolve_session_by_public_id",
        lambda _session, *, public_id, workspace_id, user_id: mem_db.resolve(public_id, workspace_id, user_id),
    )

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_workspace_context] = lambda: _WS_CTX
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.clear()


# ────────────────────────────────────────────────────────────────────
# Tests
# ────────────────────────────────────────────────────────────────────


class TestSessionCreateListRoundTrip:
    """S32 – session create-then-list round trip."""

    def test_create_returns_201_with_public_id(self, client: TestClient) -> None:
        res = client.post(f"/workspaces/{_WS_ID}/chat/sessions", json={"title": "hello"})
        assert res.status_code == status.HTTP_201_CREATED
        body = res.json()
        assert "public_id" in body
        assert body["title"] == "hello"

    def test_create_without_title_returns_null_title(self, client: TestClient) -> None:
        res = client.post(f"/workspaces/{_WS_ID}/chat/sessions", json={})
        assert res.status_code == status.HTTP_201_CREATED
        assert res.json()["title"] is None

    def test_list_returns_created_sessions(self, client: TestClient, mem_db: _InMemoryDB) -> None:
        r1 = client.post(f"/workspaces/{_WS_ID}/chat/sessions", json={"title": "one"})
        r2 = client.post(f"/workspaces/{_WS_ID}/chat/sessions", json={"title": "two"})
        assert r1.status_code == status.HTTP_201_CREATED
        assert r2.status_code == status.HTTP_201_CREATED

        list_res = client.get(f"/workspaces/{_WS_ID}/chat/sessions")
        assert list_res.status_code == 200
        sessions = list_res.json()["sessions"]
        titles = [s["title"] for s in sessions]
        assert "one" in titles
        assert "two" in titles

    def test_list_respects_limit(self, client: TestClient) -> None:
        for i in range(5):
            client.post(f"/workspaces/{_WS_ID}/chat/sessions", json={"title": f"s{i}"})
        list_res = client.get(f"/workspaces/{_WS_ID}/chat/sessions?limit=2")
        assert list_res.status_code == 200
        assert len(list_res.json()["sessions"]) == 2


class TestSessionDelete:
    """S32 – session delete + 404 on re-access."""

    def test_delete_returns_204(self, client: TestClient) -> None:
        create_res = client.post(f"/workspaces/{_WS_ID}/chat/sessions", json={"title": "doomed"})
        pub_id = create_res.json()["public_id"]

        del_res = client.delete(f"/workspaces/{_WS_ID}/chat/sessions/{pub_id}")
        assert del_res.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_then_messages_returns_404(self, client: TestClient) -> None:
        create_res = client.post(f"/workspaces/{_WS_ID}/chat/sessions", json={"title": "gone"})
        pub_id = create_res.json()["public_id"]

        del_res = client.delete(f"/workspaces/{_WS_ID}/chat/sessions/{pub_id}")
        assert del_res.status_code == status.HTTP_204_NO_CONTENT

        msg_res = client.get(f"/workspaces/{_WS_ID}/chat/sessions/{pub_id}/messages")
        assert msg_res.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_nonexistent_returns_404(self, client: TestClient) -> None:
        fake_pub_id = str(uuid.uuid4())
        del_res = client.delete(f"/workspaces/{_WS_ID}/chat/sessions/{fake_pub_id}")
        assert del_res.status_code == status.HTTP_404_NOT_FOUND

    def test_deleted_session_disappears_from_list(self, client: TestClient) -> None:
        create_res = client.post(f"/workspaces/{_WS_ID}/chat/sessions", json={"title": "vanish"})
        pub_id = create_res.json()["public_id"]

        client.delete(f"/workspaces/{_WS_ID}/chat/sessions/{pub_id}")

        list_res = client.get(f"/workspaces/{_WS_ID}/chat/sessions")
        titles = [s["title"] for s in list_res.json()["sessions"]]
        assert "vanish" not in titles


class TestSessionMessages:
    """S32 – session messages endpoint."""

    def test_empty_session_returns_empty_messages(self, client: TestClient) -> None:
        create_res = client.post(f"/workspaces/{_WS_ID}/chat/sessions", json={"title": "empty"})
        pub_id = create_res.json()["public_id"]

        msg_res = client.get(f"/workspaces/{_WS_ID}/chat/sessions/{pub_id}/messages")
        assert msg_res.status_code == 200
        assert msg_res.json()["messages"] == []

    def test_messages_for_nonexistent_session_returns_404(self, client: TestClient) -> None:
        fake_id = str(uuid.uuid4())
        msg_res = client.get(f"/workspaces/{_WS_ID}/chat/sessions/{fake_id}/messages")
        assert msg_res.status_code == status.HTTP_404_NOT_FOUND
