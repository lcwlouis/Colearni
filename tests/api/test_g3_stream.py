"""Tests for G3: streaming route and SSE contract."""

from __future__ import annotations

import json
from typing import Any

import pytest
from adapters.db.dependencies import get_db_session
from apps.api.dependencies import WorkspaceContext, get_workspace_context
from apps.api.main import app
from core.schemas import AssistantResponseEnvelope, AssistantResponseKind, GroundingMode
from core.settings import Settings
from fastapi.testclient import TestClient

_FAKE_USER = type(
    "FakeUser", (),
    {"id": 5, "public_id": "u-fake", "email": "t@t.com", "display_name": None},
)()
_FAKE_WS_CTX = WorkspaceContext(workspace_id=7, user=_FAKE_USER)
_TEST_WS = "test-ws-uuid"


def _override_db() -> Any:
    yield object()


class TestStreamRouteFeatureGate:
    def test_returns_404_when_streaming_disabled(self, monkeypatch) -> None:
        # Ensure the flag is explicitly False regardless of env
        disabled_settings = Settings(_env_file=None)
        object.__setattr__(disabled_settings, "chat_streaming_enabled", False)
        original = getattr(app.state, "settings", None)
        app.state.settings = disabled_settings
        app.dependency_overrides[get_db_session] = _override_db
        app.dependency_overrides[get_workspace_context] = lambda: _FAKE_WS_CTX
        try:
            client = TestClient(app)
            response = client.post(
                f"/workspaces/{_TEST_WS}/chat/respond/stream",
                json={"query": "hello"},
            )
        finally:
            app.dependency_overrides.clear()
            if original is not None:
                app.state.settings = original
            elif hasattr(app.state, "settings"):
                del app.state.settings

        assert response.status_code == 404
        assert "not enabled" in response.json()["detail"].lower()


class TestStreamRouteSSE:
    def _enable_streaming(self, monkeypatch: Any) -> None:
        if not hasattr(app.state, "settings"):
            app.state.settings = Settings(_env_file=None)
        monkeypatch.setattr(app.state.settings, "chat_streaming_enabled", True)

    def test_social_path_yields_status_and_final(self, monkeypatch: Any) -> None:
        self._enable_streaming(monkeypatch)
        social_env = AssistantResponseEnvelope(
            kind=AssistantResponseKind.ANSWER,
            text="Hey!",
            grounding_mode=GroundingMode.HYBRID,
            response_mode="social",
        )
        monkeypatch.setattr(
            "domain.chat.stream.try_social_response",
            lambda **kwargs: social_env,
        )
        monkeypatch.setattr(
            "domain.chat.stream.build_tutor_llm_client",
            lambda settings: None,
        )
        monkeypatch.setattr(
            "domain.chat.stream.persist_turn",
            lambda *args, **kwargs: None,
        )

        app.dependency_overrides[get_db_session] = _override_db
        app.dependency_overrides[get_workspace_context] = lambda: _FAKE_WS_CTX
        try:
            client = TestClient(app)
            response = client.post(
                f"/workspaces/{_TEST_WS}/chat/respond/stream",
                json={"query": "hi there"},
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        events = _parse_sse(response.text)
        event_types = [e["event"] for e in events]
        assert "status" in event_types
        assert "final" in event_types
        assert event_types[-1] == "final"

        # Verify final envelope
        final_event = next(e for e in events if e["event"] == "final")
        assert final_event["envelope"]["text"] == "Hey!"

    def test_error_yields_error_event(self, monkeypatch: Any) -> None:
        self._enable_streaming(monkeypatch)
        monkeypatch.setattr(
            "domain.chat.stream.try_social_response",
            lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        monkeypatch.setattr(
            "domain.chat.stream.build_tutor_llm_client",
            lambda settings: None,
        )

        app.dependency_overrides[get_db_session] = _override_db
        app.dependency_overrides[get_workspace_context] = lambda: _FAKE_WS_CTX
        try:
            client = TestClient(app)
            response = client.post(
                f"/workspaces/{_TEST_WS}/chat/respond/stream",
                json={"query": "fail"},
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        events = _parse_sse(response.text)
        event_types = [e["event"] for e in events]
        # Should have at least one status then an error
        assert "status" in event_types
        assert "error" in event_types

    def test_onboarding_path_yields_correct_sequence(self, monkeypatch: Any) -> None:
        self._enable_streaming(monkeypatch)
        monkeypatch.setattr(
            "domain.chat.stream.try_social_response",
            lambda **kwargs: None,
        )
        monkeypatch.setattr(
            "domain.chat.stream.build_tutor_llm_client",
            lambda settings: None,
        )
        monkeypatch.setattr(
            "domain.chat.stream.load_history_text",
            lambda session, session_id: "",
        )
        monkeypatch.setattr(
            "domain.chat.stream.load_assessment_context",
            lambda session, session_id: "",
        )
        monkeypatch.setattr(
            "domain.chat.stream.resolve_concept_for_turn",
            lambda session, **kwargs: type(
                "R", (), {
                    "resolved_concept": None,
                    "confidence": 0.0,
                    "requires_clarification": False,
                    "switch_suggestion": None,
                    "clarification_prompt": None,
                }
            )(),
        )
        monkeypatch.setattr(
            "domain.chat.stream.retrieve_ranked_chunks",
            lambda session, **kwargs: [],
        )
        monkeypatch.setattr(
            "domain.chat.stream.workspace_has_no_chunks",
            lambda session, workspace_id: True,
        )
        monkeypatch.setattr(
            "domain.chat.stream.persist_turn",
            lambda *args, **kwargs: None,
        )

        app.dependency_overrides[get_db_session] = _override_db
        app.dependency_overrides[get_workspace_context] = lambda: _FAKE_WS_CTX
        try:
            client = TestClient(app)
            response = client.post(
                f"/workspaces/{_TEST_WS}/chat/respond/stream",
                json={"query": "test"},
            )
        finally:
            app.dependency_overrides.clear()

        events = _parse_sse(response.text)
        phases = [e.get("phase") for e in events if e["event"] == "status"]
        assert phases == ["thinking", "searching", "finalizing"]
        assert events[-1]["event"] == "final"

    def test_blocking_respond_still_works(self, monkeypatch: Any) -> None:
        """Confirm the original blocking route is unaffected."""
        self._enable_streaming(monkeypatch)
        social_env = AssistantResponseEnvelope(
            kind=AssistantResponseKind.ANSWER,
            text="blocking!",
            grounding_mode=GroundingMode.HYBRID,
            response_mode="social",
        )
        monkeypatch.setattr(
            "domain.chat.respond.try_social_response",
            lambda **kwargs: social_env,
        )
        monkeypatch.setattr(
            "domain.chat.respond.build_tutor_llm_client",
            lambda settings: None,
        )
        monkeypatch.setattr(
            "domain.chat.respond.persist_turn",
            lambda *args, **kwargs: None,
        )

        app.dependency_overrides[get_db_session] = _override_db
        app.dependency_overrides[get_workspace_context] = lambda: _FAKE_WS_CTX
        try:
            client = TestClient(app)
            response = client.post(
                f"/workspaces/{_TEST_WS}/chat/respond",
                json={"query": "hello"},
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["text"] == "blocking!"


def _parse_sse(raw: str) -> list[dict[str, Any]]:
    """Parse SSE text into list of event dicts."""
    events: list[dict[str, Any]] = []
    for block in raw.strip().split("\n\n"):
        data_line = ""
        for line in block.strip().split("\n"):
            if line.startswith("data: "):
                data_line += line[6:]
        if data_line:
            try:
                events.append(json.loads(data_line))
            except json.JSONDecodeError:
                pass
    return events
