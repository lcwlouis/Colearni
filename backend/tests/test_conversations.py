"""Conversation persistence tests.

Tests for get-or-create conversation, turn persistence, turn index sequencing,
conversation reuse, and the history endpoint.
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
from backend.app.models.source import ConceptSourceLink, SourceRecord  # noqa: F401
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.services.conversations import (
    TutorContext,
    get_conversation_history,
    get_or_create_conversation,
)

# ---------------------------------------------------------------------------
# Fake helpers (same pattern as test_tutor_api)
# ---------------------------------------------------------------------------


class _FakeAgent:
    async def respond_stream(self, context: TutorContext):
        yield ("mode", "socratic")
        yield ("text", "Response text")


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
async def db_session(db_engine):
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


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
    """Seed workspace + trail + concept; return (ws_id, trail_id, concept_id)."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        ws = Workspace(name="Persist WS")
        session.add(ws)
        await session.flush()

        trail = Trail(
            workspace_id=ws.id,
            title="Physics 101",
            topic="Physics",
            goal="Understand Newton's laws",
            target_depth="apply",
        )
        session.add(trail)
        await session.flush()

        concept = ConceptNode(
            trail_id=trail.id,
            slug="newtons-first-law",
            title="Newton's First Law",
            node_type="concept",
            concept_level="topic",
            difficulty="beginner",
            bloom_level="understand",
            mastery_check_labels=["inertia_definition"],
            metadata_json={},
        )
        session.add(concept)
        await session.commit()
        return ws.id, trail.id, concept.id


def _parse_sse(body: str) -> list[dict]:
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
# get_or_create_conversation tests
# ---------------------------------------------------------------------------


async def test_first_chat_creates_conversation(db_engine, db_session):
    ws_id, trail_id, concept_id = await _seed(db_engine)

    conv = await get_or_create_conversation(
        db_session,
        workspace_id=ws_id,
        trail_id=trail_id,
        concept_id=concept_id,
    )

    assert conv.id is not None
    assert conv.workspace_id == ws_id
    assert conv.trail_id == trail_id
    assert conv.concept_id == concept_id


async def test_second_call_reuses_conversation(db_engine, db_session):
    ws_id, trail_id, concept_id = await _seed(db_engine)

    conv1 = await get_or_create_conversation(
        db_session,
        workspace_id=ws_id,
        trail_id=trail_id,
        concept_id=concept_id,
    )
    await db_session.commit()

    conv2 = await get_or_create_conversation(
        db_session,
        workspace_id=ws_id,
        trail_id=trail_id,
        concept_id=concept_id,
    )

    assert conv1.id == conv2.id, "second call must reuse existing conversation"


# ---------------------------------------------------------------------------
# Persistence tests via the route
# ---------------------------------------------------------------------------


async def test_user_turn_is_stored_after_successful_chat(api_client, db_engine):
    ws_id, trail_id, concept_id = await _seed(db_engine)

    await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "What is inertia?"},
    )

    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        turns = list(
            await session.scalars(select(ConversationTurn).order_by(ConversationTurn.turn_index))
        )

    user_turns = [t for t in turns if t.role == "user"]
    assert len(user_turns) == 1
    assert user_turns[0].content == "What is inertia?"
    assert user_turns[0].mode is None


async def test_assistant_turn_is_stored_after_successful_chat(api_client, db_engine):
    ws_id, trail_id, concept_id = await _seed(db_engine)

    await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "Tell me about Newton."},
    )

    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        turns = list(
            await session.scalars(select(ConversationTurn).order_by(ConversationTurn.turn_index))
        )

    assistant_turns = [t for t in turns if t.role == "assistant"]
    assert len(assistant_turns) == 1
    assert assistant_turns[0].content == "Response text"  # _FakeAgent
    assert assistant_turns[0].reasoning is None
    assert assistant_turns[0].mode == "socratic"  # _FakeAgent


async def test_assistant_reasoning_is_stored_when_provider_exposes_it(db_engine):
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_session():
        async with async_session() as session:
            yield session

    class _ThinkingAgent:
        async def respond_stream(self, context: TutorContext):
            yield ("mode", "socratic")
            yield ("thinking", "Reasoning trace")
            yield ("text", "Visible answer")

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_tutor_agent] = lambda: _ThinkingAgent()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        ws_id, trail_id, concept_id = await _seed(db_engine)
        await ac.post(
            f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
            json={"message": "What is inertia?"},
        )

    app.dependency_overrides.clear()

    async with async_session() as session:
        assistant_turns = list(
            await session.scalars(
                select(ConversationTurn)
                .where(ConversationTurn.role == "assistant")
                .order_by(ConversationTurn.turn_index)
            )
        )

    assert len(assistant_turns) == 1
    assert assistant_turns[0].content == "Visible answer"
    assert assistant_turns[0].reasoning == "Reasoning trace"
    assert assistant_turns[0].reasoning_parts == [
        {"kind": "thinking", "text": "Reasoning trace"}
    ]


async def test_turn_indexes_increment_correctly(api_client, db_engine):
    ws_id, trail_id, concept_id = await _seed(db_engine)

    await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "First message"},
    )
    await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "Second message"},
    )

    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        turns = list(
            await session.scalars(select(ConversationTurn).order_by(ConversationTurn.turn_index))
        )

    indexes = [t.turn_index for t in turns]
    assert indexes == list(range(len(indexes))), "turn indexes must be 0, 1, 2, 3, ..."


async def test_second_chat_reuses_conversation(api_client, db_engine):
    ws_id, trail_id, concept_id = await _seed(db_engine)

    resp1 = await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "First"},
    )
    resp2 = await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "Second"},
    )

    def _conv_id(resp):
        events = _parse_sse(resp.text)
        done = next(e for e in events if e["data"]["type"] == "done")
        return done["data"]["conversation_id"]

    assert _conv_id(resp1) == _conv_id(resp2), "both chats must share the same conversation"


# ---------------------------------------------------------------------------
# Conversation history endpoint tests
# ---------------------------------------------------------------------------


async def test_history_endpoint_returns_empty_when_no_conversation(api_client, db_engine):
    ws_id, trail_id, concept_id = await _seed(db_engine)

    resp = await api_client.get(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/conversation"
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["conversation_id"] is None
    assert data["messages"] == []


async def test_history_endpoint_returns_messages_in_chronological_order(api_client, db_engine):
    ws_id, trail_id, concept_id = await _seed(db_engine)

    # Send two chat messages to create turns.
    await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "Message A"},
    )
    await api_client.post(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
        json={"message": "Message B"},
    )

    resp = await api_client.get(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/conversation"
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["conversation_id"] is not None
    msgs = data["messages"]
    assert len(msgs) == 4  # 2 user + 2 assistant turns

    roles = [m["role"] for m in msgs]
    assert roles == ["user", "assistant", "user", "assistant"]

    contents = [m["content"] for m in msgs if m["role"] == "user"]
    assert contents == ["Message A", "Message B"]


async def test_history_endpoint_returns_reasoning_for_assistant_turns(db_engine):
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_session():
        async with async_session() as session:
            yield session

    class _ThinkingAgent:
        async def respond_stream(self, context: TutorContext):
            yield ("mode", "socratic")
            yield ("thinking", "Stored reasoning")
            yield ("text", "Stored answer")

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_tutor_agent] = lambda: _ThinkingAgent()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        ws_id, trail_id, concept_id = await _seed(db_engine)
        await ac.post(
            f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
            json={"message": "What is inertia?"},
        )
        resp = await ac.get(
            f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/conversation"
        )

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    messages = resp.json()["messages"]
    assistant_message = next(message for message in messages if message["role"] == "assistant")
    assert assistant_message["content"] == "Stored answer"
    assert assistant_message["reasoning"] == "Stored reasoning"


async def test_hidden_tool_turns_persist_but_history_returns_rehydrated_assistant_trace(
    db_engine,
):
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_session():
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_tutor_agent] = lambda: _ToolAgent()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        ws_id, trail_id, concept_id = await _seed(db_engine)
        await ac.post(
            f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
            json={"message": "Explain directly."},
        )
        history = await ac.get(
            f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/conversation"
        )

    app.dependency_overrides.clear()

    async with async_session() as session:
        rows = list(
            await session.scalars(select(ConversationTurn).order_by(ConversationTurn.turn_index))
        )

    assert [row.kind for row in rows] == ["visible", "tool_call", "tool_result", "visible"]
    payload = history.json()
    assert [message["role"] for message in payload["messages"]] == ["user", "assistant"]
    assistant = payload["messages"][1]
    assert assistant["content"] == "Direct answer"
    assert [part["kind"] for part in assistant["reasoning_parts"]] == [
        "status",
        "tool_call",
        "status",
        "tool_result",
        "status",
    ]
    assert assistant["reasoning_parts"][1]["name"] == "get_tutor_instructions"
    assert assistant["reasoning_parts"][3]["result"] == '{"status": "received", "mode": "direct"}'


async def test_history_endpoint_limit_param_returns_most_recent_turns_chronologically(
    api_client, db_engine
):
    ws_id, trail_id, concept_id = await _seed(db_engine)

    # Create 6 turns (3 exchanges).
    for msg in ["First", "Second", "Third"]:
        await api_client.post(
            f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/chat",
            json={"message": msg},
        )

    resp = await api_client.get(
        f"/api/workspaces/{ws_id}/trails/{trail_id}/concepts/{concept_id}/conversation",
        params={"limit": 2},
    )

    assert resp.status_code == 200
    messages = resp.json()["messages"]
    assert len(messages) == 2
    assert [message["content"] for message in messages] == ["Third", "Response text"]


async def test_history_endpoint_missing_workspace_returns_404(api_client, db_engine):
    _, trail_id, concept_id = await _seed(db_engine)

    resp = await api_client.get(
        f"/api/workspaces/{uuid.uuid4()}/trails/{trail_id}/concepts/{concept_id}/conversation"
    )

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


# ---------------------------------------------------------------------------
# get_conversation_history service tests
# ---------------------------------------------------------------------------


async def test_get_conversation_history_missing_workspace_raises(db_engine, db_session):
    _, trail_id, concept_id = await _seed(db_engine)

    with pytest.raises(LookupError, match="not found"):
        await get_conversation_history(
            db_session,
            workspace_id=uuid.uuid4(),
            trail_id=trail_id,
            concept_id=concept_id,
        )
