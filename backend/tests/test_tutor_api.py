"""Route-level tests for tutor chat and conversation history endpoints.

Uses fake tutor agents; no live LLM calls are made.
"""

from __future__ import annotations

import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.api.tutor import get_tutor_agent
from backend.app.db import get_session
from backend.app.main import app
from backend.app.models.base import Base
from backend.app.models.concept import ConceptNode  # noqa: F401
from backend.app.models.conversation import Conversation, ConversationTurn  # noqa: F401
from backend.app.models.mastery import MasteryRecord
from backend.app.models.source import ConceptSourceLink, SourceRecord  # noqa: F401
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.schemas.tutor import TutorMode
from backend.app.services.conversations import TutorContext

# ---------------------------------------------------------------------------
# Fake implementations
# ---------------------------------------------------------------------------


class _FakeAgent:
    def __init__(self, mode: TutorMode = "socratic", tokens: list[str] | None = None) -> None:
        self.mode: TutorMode = mode
        self.tokens = tokens or ["Hello", " learner"]

    async def respond_stream(self, context: TutorContext):
        yield ("mode", self.mode)
        for token in self.tokens:
            yield ("text", token)


class _ThinkingAgent:
    async def respond_stream(self, context: TutorContext):
        yield ("mode", "socratic")
        yield ("status", "thinking")
        yield ("thinking", "Reasoning trace")
        yield ("text", "Visible answer")


class _ToolAgent:
    async def respond_stream(self, context: TutorContext):
        yield ("status", "calling_tool")
        yield ("tool_call", '<tool name="get_tutor_instructions" mode="direct" />')
        yield ("status", "tool_called")
        yield (
            "tool_result",
            '<tool_result name="get_tutor_instructions" mode="direct">'
            "Use direct mode.</tool_result>",
        )
        yield ("status", "tool_complete")
        yield ("mode", "direct")
        yield ("text", "Direct answer")


class _ReasoningToolAgent:
    async def respond_stream(self, context: TutorContext):
        yield ("mode", "direct")
        yield ("thinking", "Plan first.\n")
        yield ("tool_call", '<tool name="get_tutor_instructions" mode="direct" />')
        yield (
            "tool_result",
            '<tool_result name="get_tutor_instructions" mode="direct">'
            "Use direct mode.</tool_result>",
        )
        yield ("thinking", "Now answer.\n")
        yield ("text", "Direct answer")


class _InvalidToolAgent:
    async def respond_stream(self, context: TutorContext):
        yield ("status", "calling_tool")
        yield ("tool_call", '<tool name="get_tutor_instructions" mode="lecture" />')
        yield ("status", "tool_called")
        yield (
            "tool_result",
            '<tool_result name="get_tutor_instructions" mode="lecture">'
            "raw secret instructions</tool_result>",
        )
        yield ("status", "tool_complete")
        yield ("mode", "socratic")
        yield ("text", "Safe fallback question?")


class _FailingAgent:
    """Agent that raises immediately (no tokens before the error)."""

    async def respond_stream(self, context: TutorContext):
        raise RuntimeError("LLM generation failed")
        yield  # marks this as an async generator


class _StreamingTwoPhaseAgent:
    """Two-phase agent that streams first-pass reasoning live via prepare_mode_stream."""

    def _prep(self):
        from backend.app.services.tutor import _ModePreparation

        return _ModePreparation(
            mode="socratic",
            locked_socratic=False,
            messages_after_mode=[{"role": "system", "content": "final"}],
            buffered_events=(("mode", "socratic"),),
        )

    async def prepare_mode(self, context: TutorContext):
        return self._prep()

    async def prepare_mode_stream(self, context: TutorContext):
        yield ("status", "thinking")
        yield ("thinking", "first-pass reasoning")
        yield ("__prep__", self._prep())

    async def stream_text(self, context: TutorContext, prep, *, messages=None):
        yield ("text", "Visible answer")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def api_client(db_engine):
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_session():
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_tutor_agent] = lambda: _FakeAgent()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _seed(db_engine) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Seed a workspace, trail, and concept node. Return their IDs."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        ws = Workspace(name="Test Workspace")
        session.add(ws)
        await session.flush()

        trail = Trail(
            workspace_id=ws.id,
            title="ML Basics",
            topic="Machine Learning",
            goal="Understand ML fundamentals",
            target_depth="understand",
        )
        session.add(trail)
        await session.flush()

        concept = ConceptNode(
            trail_id=trail.id,
            slug="linear-regression",
            title="Linear Regression",
            node_type="concept",
            concept_level="topic",
            difficulty="beginner",
            bloom_level="understand",
            mastery_check_labels=["define_lr", "apply_lr"],
            metadata_json={},
        )
        session.add(concept)
        await session.commit()
        return ws.id, trail.id, concept.id


def _parse_sse(body: str) -> list[dict]:
    """Parse SSE response body into a list of {event, data} dicts."""
    events: list[dict] = []
    current: dict = {}
    for line in body.splitlines():
        if line.startswith("event:"):
            current["event"] = line[6:].strip()
        elif line.startswith("data:"):
            current["data"] = json.loads(line[5:].strip())
        elif not line and current:
            events.append(current.copy())
            current = {}
    if current:
        events.append(current)
    return events


# ---------------------------------------------------------------------------
# Route tests — happy path
# ---------------------------------------------------------------------------


async def test_chat_returns_sse_events_in_order(api_client, db_engine):
    ws_id, trail_id, concept_id = await _seed(db_engine)

    resp = await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "What is linear regression?"},
    )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    events = _parse_sse(resp.text)
    event_types = [e["data"]["type"] for e in events]
    assert event_types[0] == "mode", "first event must be 'mode'"
    assert "token" in event_types, "must have at least one 'token' event"
    assert event_types[-1] == "done", "last event must be 'done'"

    # mode event before any token
    mode_pos = event_types.index("mode")
    first_token_pos = event_types.index("token")
    assert mode_pos < first_token_pos


async def test_chat_done_event_includes_conversation_id_and_message(api_client, db_engine):
    ws_id, trail_id, concept_id = await _seed(db_engine)

    resp = await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "Explain the concept."},
    )

    events = _parse_sse(resp.text)
    done_event = next(e for e in events if e["data"]["type"] == "done")
    data = done_event["data"]

    assert "conversation_id" in data
    uuid.UUID(data["conversation_id"])  # must be a valid UUID
    assert "message" in data
    msg = data["message"]
    assert msg["role"] == "assistant"
    assert msg["content"] == "Hello learner"  # FakeAgent tokens joined
    assert msg["reasoning"] is None
    assert msg["mode"] == "socratic"  # FakeAgent default mode
    assert "id" in msg
    assert "created_at" in msg


async def test_first_chat_turn_sets_mastery_to_learning(api_client, db_engine):
    ws_id, trail_id, concept_id = await _seed(db_engine)

    resp = await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "Let's start."},
    )

    assert resp.status_code == 200

    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        record = await session.scalar(
            select(MasteryRecord).where(MasteryRecord.concept_id == concept_id)
        )

    assert record is not None
    assert record.status == "learning"


async def test_chat_from_needs_review_resets_mastery_to_learning(api_client, db_engine):
    ws_id, trail_id, concept_id = await _seed(db_engine)
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        session.add(
            MasteryRecord(
                workspace_id=ws_id,
                concept_id=concept_id,
                status="needs_review",
                bloom_level="understand",
                score=0.5,
            )
        )
        await session.commit()

    resp = await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "I want to try again."},
    )

    assert resp.status_code == 200

    async with async_session() as session:
        record = await session.scalar(
            select(MasteryRecord).where(MasteryRecord.concept_id == concept_id)
        )

    assert record is not None
    assert record.status == "learning"


async def test_chat_mode_event_carries_mode_field(api_client, db_engine):
    ws_id, trail_id, concept_id = await _seed(db_engine)

    resp = await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "Hello"},
    )

    events = _parse_sse(resp.text)
    mode_event = next(e for e in events if e["data"]["type"] == "mode")
    assert mode_event["data"]["mode"] == "socratic"


async def test_chat_can_emit_thinking_event_before_tokens(api_client, db_engine):
    ws_id, trail_id, concept_id = await _seed(db_engine)
    app.dependency_overrides[get_tutor_agent] = lambda: _ThinkingAgent()

    resp = await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "Think out loud"},
    )

    events = _parse_sse(resp.text)
    event_types = [e["data"]["type"] for e in events]

    assert "thinking" in event_types
    assert event_types.index("thinking") < event_types.index("token")


async def test_chat_streams_first_pass_reasoning_before_mode(api_client, db_engine):
    """Two-phase agents stream first-pass (mode-selection) reasoning live, before mode."""
    ws_id, trail_id, concept_id = await _seed(db_engine)
    app.dependency_overrides[get_tutor_agent] = lambda: _StreamingTwoPhaseAgent()

    resp = await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "Think out loud"},
    )

    events = _parse_sse(resp.text)
    event_types = [e["data"]["type"] for e in events]

    # First-pass thinking is streamed before the mode event and the visible answer.
    assert "thinking" in event_types
    assert event_types.index("thinking") < event_types.index("mode")
    assert event_types.index("thinking") < event_types.index("token")

    thinking_event = next(e for e in events if e["data"]["type"] == "thinking")
    assert thinking_event["data"]["content"] == "first-pass reasoning"

    done_event = next(e for e in events if e["data"]["type"] == "done")
    assert done_event["data"]["message"]["content"] == "Visible answer"
    # The streamed first-pass reasoning is persisted exactly once.
    assert done_event["data"]["message"]["reasoning"] == "first-pass reasoning"


async def test_chat_can_emit_status_events(api_client, db_engine):
    ws_id, trail_id, concept_id = await _seed(db_engine)
    app.dependency_overrides[get_tutor_agent] = lambda: _ToolAgent()

    resp = await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "Explain directly."},
    )

    events = _parse_sse(resp.text)
    status_values = [
        event["data"]["status"] for event in events if event["data"]["type"] == "status"
    ]
    assert status_values == ["calling_tool", "tool_called", "tool_complete", "responding"]


async def test_chat_emits_tool_events_for_reasoning_ui(api_client, db_engine):
    ws_id, trail_id, concept_id = await _seed(db_engine)
    app.dependency_overrides[get_tutor_agent] = lambda: _ToolAgent()

    resp = await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "Explain directly."},
    )

    events = _parse_sse(resp.text)
    tool_call = next(event for event in events if event["data"]["type"] == "tool_call")
    tool_result = next(event for event in events if event["data"]["type"] == "tool_result")

    assert tool_call["data"] == {
        "type": "tool_call",
        "name": "get_tutor_instructions",
        "mode": "direct",
    }
    assert tool_result["data"]["type"] == "tool_result"
    assert tool_result["data"]["name"] == "get_tutor_instructions"
    assert tool_result["data"]["mode"] == "direct"
    assert json.loads(tool_result["data"]["result"]) == {"status": "received", "mode": "direct"}


async def test_chat_done_event_includes_persisted_reasoning_when_available(api_client, db_engine):
    ws_id, trail_id, concept_id = await _seed(db_engine)
    app.dependency_overrides[get_tutor_agent] = lambda: _ThinkingAgent()

    resp = await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "Think out loud"},
    )

    events = _parse_sse(resp.text)
    done_event = next(e for e in events if e["data"]["type"] == "done")
    assert done_event["data"]["message"]["reasoning"] == "Reasoning trace"


async def test_chat_done_event_includes_structured_reasoning_parts(api_client, db_engine):
    ws_id, trail_id, concept_id = await _seed(db_engine)
    app.dependency_overrides[get_tutor_agent] = lambda: _ReasoningToolAgent()

    resp = await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "Explain directly."},
    )

    events = _parse_sse(resp.text)
    done_event = next(e for e in events if e["data"]["type"] == "done")
    reasoning_parts = done_event["data"]["message"]["reasoning_parts"]

    assert [part["kind"] for part in reasoning_parts] == [
        "thinking",
        "tool_call",
        "tool_result",
        "thinking",
    ]
    assert reasoning_parts[0]["text"] == "Plan first.\n"
    assert reasoning_parts[1]["name"] == "get_tutor_instructions"
    assert reasoning_parts[2]["result"] == '{"status": "received", "mode": "direct"}'
    assert reasoning_parts[3]["text"] == "Now answer.\n"


async def test_invalid_tool_arguments_are_sanitized_in_public_sse(api_client, db_engine):
    ws_id, trail_id, concept_id = await _seed(db_engine)
    app.dependency_overrides[get_tutor_agent] = lambda: _InvalidToolAgent()

    resp = await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "Try invalid tool."},
    )

    events = _parse_sse(resp.text)
    event_types = [event["data"]["type"] for event in events]
    assert event_types == [
        "status",
        "tool_call",
        "status",
        "tool_result",
        "status",
        "mode",
        "status",
        "token",
        "done",
    ]
    tool_call = next(event for event in events if event["data"]["type"] == "tool_call")
    tool_result = next(event for event in events if event["data"]["type"] == "tool_result")

    assert tool_call["data"] == {
        "type": "tool_call",
        "name": "get_tutor_instructions",
        "mode": None,
    }
    assert json.loads(tool_result["data"]["result"]) == {
        "status": "received",
        "mode": "unknown",
    }
    assert "raw secret instructions" not in resp.text


# ---------------------------------------------------------------------------
# 404 scope validation tests
# ---------------------------------------------------------------------------


async def test_chat_missing_workspace_returns_404(api_client, db_engine):
    _, trail_id, concept_id = await _seed(db_engine)

    resp = await api_client.post(
        f"/api/workspaces/{uuid.uuid4()}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "Hello"},
    )

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_chat_missing_trail_returns_404(api_client, db_engine):
    ws_id, _, concept_id = await _seed(db_engine)

    resp = await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{uuid.uuid4()}/concepts/{concept_id}/chat",
        json={"message": "Hello"},
    )

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_chat_missing_concept_returns_404(api_client, db_engine):
    ws_id, trail_id, _ = await _seed(db_engine)

    resp = await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{uuid.uuid4()}/chat",
        json={"message": "Hello"},
    )

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


async def test_chat_empty_message_rejected(api_client, db_engine):
    ws_id, trail_id, concept_id = await _seed(db_engine)

    resp = await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": ""},
    )

    assert resp.status_code == 422


async def test_chat_whitespace_only_message_rejected(api_client, db_engine):
    ws_id, trail_id, concept_id = await _seed(db_engine)

    resp = await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "   "},
    )

    assert resp.status_code == 422


async def test_chat_extra_fields_rejected(api_client, db_engine):
    ws_id, trail_id, concept_id = await _seed(db_engine)

    resp = await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "Hello", "unknown_field": "value"},
    )

    assert resp.status_code == 422


async def test_chat_wrong_conversation_id_scope_returns_404(api_client, db_engine):
    """A conversation_id from a different concept should be rejected."""
    ws_id, trail_id, concept_id = await _seed(db_engine)
    random_conv_id = uuid.uuid4()

    resp = await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "Hello", "conversation_id": str(random_conv_id)},
    )

    # The pre-validation passes (workspace/trail/concept exist), but
    # stream_chat_response fails to find the conversation → SSE error event.
    # This is delivered as an SSE stream (200 with error event), not a 404.
    # Both the pre-check 404 and SSE error are acceptable here; test for either.
    if resp.status_code == 200:
        events = _parse_sse(resp.text)
        event_types = [e["data"]["type"] for e in events]
        assert "error" in event_types
    else:
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Error path tests
# ---------------------------------------------------------------------------


async def test_chat_generator_failure_emits_sse_error_event(db_engine):
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_session():
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_tutor_agent] = lambda: _FailingAgent()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        ws_id, trail_id, concept_id = await _seed(db_engine)

        resp = await ac.post(
            f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
            json={"message": "Hello"},
        )

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    event_types = [e["data"]["type"] for e in events]

    assert "error" in event_types
    assert "done" not in event_types

    error_event = next(e for e in events if e["data"]["type"] == "error")
    assert error_event["data"]["code"] == "llm_error"


async def test_chat_generator_failure_does_not_persist_partial_assistant_turn(db_engine):
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_session():
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_tutor_agent] = lambda: _FailingAgent()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        ws_id, trail_id, concept_id = await _seed(db_engine)

        await ac.post(
            f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
            json={"message": "Hello"},
        )

    app.dependency_overrides.clear()

    # After failure, no turns should be persisted (transaction rolled back).
    async with async_session() as session:
        from sqlalchemy import select

        turns = list(await session.scalars(select(ConversationTurn)))
        assert turns == [], "no turns should be persisted after generator failure"


async def test_tool_turns_do_not_leak_into_public_history(api_client, db_engine):
    ws_id, trail_id, concept_id = await _seed(db_engine)
    app.dependency_overrides[get_tutor_agent] = lambda: _ToolAgent()

    await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "Explain directly."},
    )

    history = await api_client.get(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/conversation"
    )

    assert history.status_code == 200
    payload = history.json()
    assert [message["role"] for message in payload["messages"]] == ["user", "assistant"]
    assert payload["messages"][1]["content"] == "Direct answer"


async def test_history_includes_structured_reasoning_parts(api_client, db_engine):
    ws_id, trail_id, concept_id = await _seed(db_engine)
    app.dependency_overrides[get_tutor_agent] = lambda: _ReasoningToolAgent()

    await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "Explain directly."},
    )

    history = await api_client.get(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/conversation"
    )

    assert history.status_code == 200
    assistant_message = next(
        message for message in history.json()["messages"] if message["role"] == "assistant"
    )
    assert [part["kind"] for part in assistant_message["reasoning_parts"]] == [
        "thinking",
        "tool_call",
        "tool_result",
        "thinking",
    ]
