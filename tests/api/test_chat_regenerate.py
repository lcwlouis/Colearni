"""Tests for the message regeneration API endpoint (L6.3)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from adapters.db.dependencies import get_db_session
from apps.api.dependencies import WorkspaceContext, get_workspace_context
from apps.api.main import app
from fastapi.testclient import TestClient

_FAKE_USER = type(
    "FakeUser", (),
    {"id": 42, "public_id": "u-fake", "email": "t@t.com", "display_name": None},
)()
_FAKE_WS_CTX = WorkspaceContext(workspace_id=1, user=_FAKE_USER)


def _override_db() -> Any:
    yield MagicMock()


class TestRegenerateEndpoint:
    """Test the POST .../messages/{msg_id}/regenerate endpoint."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        app.dependency_overrides[get_db_session] = _override_db
        app.dependency_overrides[get_workspace_context] = lambda: _FAKE_WS_CTX
        yield
        app.dependency_overrides.clear()

    @patch("apps.api.routes.chat.generate_chat_response_stream")
    @patch("apps.api.routes.chat.resolve_session_by_public_id", return_value=100)
    def test_regenerate_supersedes_and_streams(self, mock_resolve, mock_stream):
        from core.schemas.chat import ChatStreamDeltaEvent

        event = ChatStreamDeltaEvent(text="hello")
        mock_stream.return_value = iter([event])

        with patch(
            "domain.chat.session_memory.supersede_and_get_user_query",
            return_value="What is photosynthesis?",
        ):
            client = TestClient(app)
            response = client.post(
                "/workspaces/1/chat/sessions/sess-123/messages/11/regenerate",
            )
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]

    @patch("apps.api.routes.chat.resolve_session_by_public_id")
    def test_regenerate_session_not_found(self, mock_resolve):
        from adapters.db.chat import ChatNotFoundError

        mock_resolve.side_effect = ChatNotFoundError("not found")

        client = TestClient(app)
        response = client.post(
            "/workspaces/1/chat/sessions/bad-id/messages/11/regenerate",
        )
        assert response.status_code == 404

    @patch("apps.api.routes.chat.resolve_session_by_public_id", return_value=100)
    def test_regenerate_bad_message(self, mock_resolve):
        from domain.chat.session_memory import RegenerationError

        with patch(
            "domain.chat.session_memory.supersede_and_get_user_query",
            side_effect=RegenerationError("cannot regenerate"),
        ):
            client = TestClient(app)
            response = client.post(
                "/workspaces/1/chat/sessions/sess-123/messages/11/regenerate",
            )
            assert response.status_code == 400
            assert "cannot regenerate" in response.json()["detail"]
