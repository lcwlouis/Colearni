"""Tests for the retrieval tool calling loop and read_document_section service.

Covers:
- Parallel tool execution and budget tracking
- Budget cap (4 calls requested, budget=3 → only 3 executed)
- Deduplication (same tool+args → cached result)
- No-op exit when no tool calls in response
- Error result on malformed args (loop continues)
- Tool offer condition (empty sources → RETRIEVAL_TOOLS not passed)
- read_document_section line window correctness
- read_document_section cross-workspace rejection
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.agents.provider_tools import (
    NormalizedStreamEvent,
    NormalizedToolCall,
    NormalizedToolResult,
)
from backend.app.agents.retrieval_tools import RETRIEVAL_TOOLS
from backend.app.models.base import Base
from backend.app.models.source import SourceRecord, SourceRevision
from backend.app.models.workspace import Workspace
from backend.app.services.conversations import (
    _TOOL_CALL_BUDGET,
    _run_retrieval_loop,
    execute_retrieval_tool,
)
from backend.app.services.retrieval import read_document_section

# ---------------------------------------------------------------------------
# DB fixtures (in-memory SQLite)
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tool_call(name: str, arguments: dict, call_id: str | None = None) -> NormalizedToolCall:
    return NormalizedToolCall(
        call_id=call_id or f"{name}:test",
        name=name,
        arguments=arguments,
    )


def _make_tool_call_event(
    name: str,
    arguments: dict,
    call_id: str | None = None,
) -> NormalizedStreamEvent:
    return NormalizedStreamEvent.tool_call_event(
        _make_tool_call(name, arguments, call_id)
    )


def _text_only_stream() -> AsyncIterator[NormalizedStreamEvent]:
    async def _gen():
        yield NormalizedStreamEvent.text_delta("Hello, world!")
        yield NormalizedStreamEvent.done_event()
    return _gen()


def _tool_call_stream(*tool_calls: NormalizedToolCall) -> AsyncIterator[NormalizedStreamEvent]:
    async def _gen():
        for tc in tool_calls:
            yield NormalizedStreamEvent.tool_call_event(tc)
        yield NormalizedStreamEvent.done_event()
    return _gen()


class _FakeLLMClient:
    """Fake LLM client that returns a sequence of stream responses."""

    def __init__(self, responses: list[list[NormalizedStreamEvent]]) -> None:
        self._responses = list(responses)
        self._call_count = 0

    async def chat_stream_events(
        self,
        messages: list[dict],
        tools: list | None = None,
    ) -> AsyncIterator[NormalizedStreamEvent]:
        idx = min(self._call_count, len(self._responses) - 1)
        events = self._responses[idx]
        self._call_count += 1
        for e in events:
            yield e


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_tool_loop_parallel_calls(db_session: AsyncSession):
    """Two tool calls in one response → both executed, budget decremented by 2."""
    workspace_id = uuid.uuid4()
    concept_id = uuid.uuid4()

    tc1 = _make_tool_call("search_sources", {"query": "test"}, "call_1")
    tc2 = _make_tool_call("search_sources", {"query": "other"}, "call_2")

    # First response: two tool calls; second response: text only (exit)
    fake_llm = _FakeLLMClient(
        responses=[
            [
                NormalizedStreamEvent.tool_call_event(tc1),
                NormalizedStreamEvent.tool_call_event(tc2),
            ],
            [NormalizedStreamEvent.text_delta("done"), NormalizedStreamEvent.done_event()],
        ]
    )

    executed_calls: list[str] = []

    async def fake_execute(tc, *, session, workspace_id, concept_id):
        executed_calls.append(tc.call_id)
        return NormalizedToolResult(
            call_id=tc.call_id,
            name=tc.name,
            content="result",
            public_preview={"preview": "result"},
        )

    with patch(
        "backend.app.services.conversations.execute_retrieval_tool",
        side_effect=fake_execute,
    ):
        messages = [{"role": "user", "content": "hello"}]
        _final_msgs, all_results = await _run_retrieval_loop(
            messages,
            RETRIEVAL_TOOLS,
            session=db_session,
            workspace_id=workspace_id,
            concept_id=concept_id,
            llm_client=fake_llm,
        )

    assert len(executed_calls) == 2
    assert "call_1" in executed_calls
    assert "call_2" in executed_calls
    # Budget was decremented by 2 in the first iteration; second iteration returns text
    assert len(all_results) == 2


async def test_tool_loop_budget_cap(db_session: AsyncSession):
    """4 tool calls with budget=3 → only 3 executed; 4th is dropped."""
    workspace_id = uuid.uuid4()
    concept_id = uuid.uuid4()

    calls = [
        _make_tool_call("search_sources", {"query": f"q{i}"}, f"call_{i}")
        for i in range(4)
    ]

    # Return all 4 tool calls in one LLM response
    fake_llm = _FakeLLMClient(
        responses=[
            [NormalizedStreamEvent.tool_call_event(tc) for tc in calls],
            [NormalizedStreamEvent.text_delta("done"), NormalizedStreamEvent.done_event()],
        ]
    )

    executed_calls: list[str] = []

    async def fake_execute(tc, *, session, workspace_id, concept_id):
        executed_calls.append(tc.call_id)
        return NormalizedToolResult(
            call_id=tc.call_id,
            name=tc.name,
            content="result",
            public_preview={"preview": "result"},
        )

    with patch(
        "backend.app.services.conversations.execute_retrieval_tool",
        side_effect=fake_execute,
    ):
        messages = [{"role": "user", "content": "hello"}]
        _final_msgs, all_results = await _run_retrieval_loop(
            messages,
            RETRIEVAL_TOOLS,
            session=db_session,
            workspace_id=workspace_id,
            concept_id=concept_id,
            llm_client=fake_llm,
        )

    # Budget = 3, so only 3 of 4 calls should be executed
    assert len(executed_calls) == _TOOL_CALL_BUDGET
    assert len(all_results) == _TOOL_CALL_BUDGET


async def test_tool_loop_dedup(db_session: AsyncSession):
    """Same tool+args twice → execute_retrieval_tool called once, second uses cache."""
    workspace_id = uuid.uuid4()
    concept_id = uuid.uuid4()

    # Same name and same arguments → same cache key
    tc_a = _make_tool_call("search_sources", {"query": "same"}, "call_a")
    tc_b = _make_tool_call("search_sources", {"query": "same"}, "call_b")

    fake_llm = _FakeLLMClient(
        responses=[
            [
                NormalizedStreamEvent.tool_call_event(tc_a),
                NormalizedStreamEvent.tool_call_event(tc_b),
            ],
            [NormalizedStreamEvent.text_delta("done"), NormalizedStreamEvent.done_event()],
        ]
    )

    execution_count = 0

    async def fake_execute(tc, *, session, workspace_id, concept_id):
        nonlocal execution_count
        execution_count += 1
        return NormalizedToolResult(
            call_id=tc.call_id,
            name=tc.name,
            content="cached result",
            public_preview={"preview": "cached result"},
        )

    with patch(
        "backend.app.services.conversations.execute_retrieval_tool",
        side_effect=fake_execute,
    ):
        messages = [{"role": "user", "content": "hello"}]
        _final_msgs, all_results = await _run_retrieval_loop(
            messages,
            RETRIEVAL_TOOLS,
            session=db_session,
            workspace_id=workspace_id,
            concept_id=concept_id,
            llm_client=fake_llm,
        )

    # Only one unique execution — the second was a cache hit
    assert execution_count == 1
    # Both results are present (first executed, second from cache)
    assert len(all_results) == 2


async def test_tool_loop_no_calls(db_session: AsyncSession):
    """Only text event → loop exits immediately (budget unused)."""
    workspace_id = uuid.uuid4()
    concept_id = uuid.uuid4()

    fake_llm = _FakeLLMClient(
        responses=[
            [NormalizedStreamEvent.text_delta("Just text."), NormalizedStreamEvent.done_event()],
        ]
    )

    execution_count = 0

    async def fake_execute(tc, *, session, workspace_id, concept_id):
        nonlocal execution_count
        execution_count += 1
        return NormalizedToolResult(call_id=tc.call_id, name=tc.name, content="x")

    with patch(
        "backend.app.services.conversations.execute_retrieval_tool",
        side_effect=fake_execute,
    ):
        messages = [{"role": "user", "content": "hello"}]
        retrieval_loop = await _run_retrieval_loop(
            messages,
            RETRIEVAL_TOOLS,
            session=db_session,
            workspace_id=workspace_id,
            concept_id=concept_id,
            llm_client=fake_llm,
        )
        _final_msgs, all_results = retrieval_loop

    assert execution_count == 0
    assert all_results == []
    assert _final_msgs == messages
    assert retrieval_loop.text == "Just text."


async def test_tool_loop_cached_duplicates_count_against_budget(db_session: AsyncSession):
    workspace_id = uuid.uuid4()
    concept_id = uuid.uuid4()
    first_call = _make_tool_call("search_sources", {"query": "same"}, "call_first")
    cached_call = _make_tool_call("search_sources", {"query": "same"}, "call_cached")
    extra_call = _make_tool_call("search_sources", {"query": "extra"}, "call_extra")

    fake_llm = _FakeLLMClient(
        responses=[
            [NormalizedStreamEvent.tool_call_event(first_call)],
            [NormalizedStreamEvent.tool_call_event(cached_call)],
            [NormalizedStreamEvent.tool_call_event(extra_call)],
        ]
    )

    execution_count = 0

    async def fake_execute(tc, *, session, workspace_id, concept_id):
        nonlocal execution_count
        execution_count += 1
        return NormalizedToolResult(
            call_id=tc.call_id,
            name=tc.name,
            content=f"result for {tc.call_id}",
            public_preview={"preview": f"result for {tc.call_id}"},
        )

    with patch(
        "backend.app.services.conversations.execute_retrieval_tool",
        side_effect=fake_execute,
    ):
        retrieval_loop = await _run_retrieval_loop(
            [{"role": "user", "content": "hello"}],
            RETRIEVAL_TOOLS,
            session=db_session,
            workspace_id=workspace_id,
            concept_id=concept_id,
            llm_client=fake_llm,
        )

    assert fake_llm._call_count == _TOOL_CALL_BUDGET
    assert execution_count == 2
    assert [result.call_id for result in retrieval_loop.tool_results] == [
        "call_first",
        "call_cached",
        "call_extra",
    ]
    assert any(
        message.get("role") == "tool" and message.get("tool_call_id") == "call_cached"
        for message in retrieval_loop.messages
    )


async def test_tool_loop_stops_after_successful_document_read(db_session: AsyncSession):
    workspace_id = uuid.uuid4()
    concept_id = uuid.uuid4()
    read_call = _make_tool_call(
        "read_document_section",
        {
            "source_revision_id": str(uuid.uuid4()),
            "line_start": 1,
            "window_lines": 20,
        },
        "call_read",
    )

    fake_llm = _FakeLLMClient(
        responses=[
            [NormalizedStreamEvent.tool_call_event(read_call)],
            [
                NormalizedStreamEvent.tool_call_event(
                    _make_tool_call("search_sources", {"query": "extra"})
                )
            ],
        ]
    )

    async def fake_execute(tc, *, session, workspace_id, concept_id):
        return NormalizedToolResult(
            call_id=tc.call_id,
            name=tc.name,
            content="Document section content",
            public_preview={"preview": "Document section content"},
        )

    with patch(
        "backend.app.services.conversations.execute_retrieval_tool",
        side_effect=fake_execute,
    ):
        messages = [{"role": "user", "content": "hello"}]
        _final_msgs, all_results = await _run_retrieval_loop(
            messages,
            RETRIEVAL_TOOLS,
            session=db_session,
            workspace_id=workspace_id,
            concept_id=concept_id,
            llm_client=fake_llm,
        )

    assert fake_llm._call_count == 1
    assert [result.name for result in all_results] == ["read_document_section"]


async def test_tool_loop_bad_args(db_session: AsyncSession):
    """Malformed args → is_error==True, loop continues (does not raise)."""
    workspace_id = uuid.uuid4()
    concept_id = uuid.uuid4()

    # read_document_section requires source_revision_id and line_start
    # Passing wrong type for line_start to trigger an error
    bad_tc = _make_tool_call(
        "read_document_section",
        {"source_revision_id": "not-a-uuid", "line_start": 1},
        "bad_call",
    )

    fake_llm = _FakeLLMClient(
        responses=[
            [NormalizedStreamEvent.tool_call_event(bad_tc)],
            [NormalizedStreamEvent.text_delta("done"), NormalizedStreamEvent.done_event()],
        ]
    )

    messages = [{"role": "user", "content": "hello"}]
    _final_msgs, all_results = await _run_retrieval_loop(
        messages,
        RETRIEVAL_TOOLS,
        session=db_session,
        workspace_id=workspace_id,
        concept_id=concept_id,
        llm_client=fake_llm,
    )

    # The loop must not raise; we get an error result
    assert len(all_results) == 1
    assert all_results[0].is_error is True


async def test_get_concept_sources_invalid_concept_id_defaults_to_current(db_session: AsyncSession):
    current_concept_id = uuid.uuid4()
    tool_call = _make_tool_call(
        "get_concept_sources",
        {"concept_id": "moon-music-album-lyrics"},
        "call_sources",
    )

    async def fake_sources(*, session, workspace_id, concept_id, limit=5):
        assert concept_id == current_concept_id
        return []

    with patch(
        "backend.app.services.conversations.get_concept_sources_for_tutor",
        side_effect=fake_sources,
    ):
        result = await execute_retrieval_tool(
            tool_call,
            session=db_session,
            workspace_id=uuid.uuid4(),
            concept_id=current_concept_id,
        )

    assert result.is_error is False


async def test_get_graph_neighbourhood_missing_concept_id_defaults_to_current(
    db_session: AsyncSession,
):
    current_concept_id = uuid.uuid4()
    tool_call = _make_tool_call("get_graph_neighbourhood", {}, "call_graph")

    async def fake_neighbourhood(session, workspace_id, concept_id):
        assert concept_id == current_concept_id
        return "No neighbours found."

    with patch(
        "backend.app.services.conversations._get_neighbourhood_for_concept",
        side_effect=fake_neighbourhood,
    ):
        result = await execute_retrieval_tool(
            tool_call,
            session=db_session,
            workspace_id=uuid.uuid4(),
            concept_id=current_concept_id,
        )

    assert result.is_error is False


async def test_tool_offer_condition_empty_sources():
    """context.sources=[] → RETRIEVAL_TOOLS not passed to llm_client."""
    workspace_id = uuid.uuid4()
    concept_id = uuid.uuid4()

    received_tools: list = []

    class _CaptureLLMClient:
        async def chat_stream_events(self, messages, tools=None):
            received_tools.extend(tools or [])
            yield NormalizedStreamEvent.text_delta("hi")
            yield NormalizedStreamEvent.done_event()

    # Pass empty tools list (simulating context.sources == [])
    fake_llm = _CaptureLLMClient()
    messages = [{"role": "user", "content": "hello"}]

    # When tools=[] is passed, _run_retrieval_loop returns immediately
    final_msgs, all_results = await _run_retrieval_loop(
        messages,
        [],  # empty tools — simulates condition len(context.sources) == 0
        session=AsyncMock(),
        workspace_id=workspace_id,
        concept_id=concept_id,
        llm_client=fake_llm,
    )

    assert all_results == []
    assert final_msgs == messages
    # No tools were offered to the LLM since we passed empty list
    assert received_tools == []


async def test_read_document_section_lines(db_session: AsyncSession):
    """Insert revision with raw_text, verify line window is returned correctly."""
    workspace = Workspace(name="Test WS")
    db_session.add(workspace)
    await db_session.flush()

    source = SourceRecord(
        workspace_id=workspace.id,
        origin="manual",
        access="public",
        title="Test Source",
    )
    db_session.add(source)
    await db_session.flush()

    revision = SourceRevision(
        workspace_id=workspace.id,
        source_id=source.id,
        revision_number=1,
        object_key=f"test/{uuid.uuid4()}.txt",
        content_hash="abc123",
        file_size_bytes=100,
        parser_name="text",
        parser_version="1.0",
        status="parsed",
        raw_text="line1\nline2\nline3\nline4\nline5",
    )
    db_session.add(revision)
    await db_session.flush()

    result = await read_document_section(
        db_session,
        workspace_id=workspace.id,
        source_revision_id=revision.id,
        line_start=2,
        window_lines=3,
    )

    assert result == "line2\nline3\nline4"


async def test_read_document_section_wrong_workspace(db_session: AsyncSession):
    """Revision belongs to workspace A; request with workspace B → LookupError."""
    workspace_a = Workspace(name="Workspace A")
    db_session.add(workspace_a)
    await db_session.flush()

    source = SourceRecord(
        workspace_id=workspace_a.id,
        origin="manual",
        access="public",
        title="Test Source",
    )
    db_session.add(source)
    await db_session.flush()

    revision = SourceRevision(
        workspace_id=workspace_a.id,
        source_id=source.id,
        revision_number=1,
        object_key=f"test/{uuid.uuid4()}.txt",
        content_hash="def456",
        file_size_bytes=50,
        parser_name="text",
        parser_version="1.0",
        status="parsed",
        raw_text="some content",
    )
    db_session.add(revision)
    await db_session.flush()

    workspace_b_id = uuid.uuid4()

    with pytest.raises(LookupError, match="not found"):
        await read_document_section(
            db_session,
            workspace_id=workspace_b_id,
            source_revision_id=revision.id,
            line_start=1,
        )
