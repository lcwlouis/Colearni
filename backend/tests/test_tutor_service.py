"""Tutor service unit tests.

Tests for:
  - TutorContext assembly (build_tutor_context)
  - FallbackTutorModeClassifier keyword rules
  - _parse_mode_json safe fallbacks
  - _context_to_prompt_vars compatibility coverage
  - _build_chat_messages tool-history replay

No live LLM calls are made.
"""

from __future__ import annotations

import uuid
from typing import cast
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.agents.prompts.registry import PromptRegistry
from backend.app.agents.provider_tools import (
    NormalizedStreamEvent,
    NormalizedToolCall,
    NormalizedToolResult,
)
from backend.app.models.base import Base
from backend.app.models.concept import ConceptEdge, ConceptNode
from backend.app.models.conversation import Conversation, ConversationTurn  # noqa: F401
from backend.app.models.mastery import MasteryRecord
from backend.app.models.source import ConceptSourceLink, SourceRecord  # noqa: F401
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.services.conversations import (
    RETRIEVAL_TOOLS,
    TutorContext,
    TutorSourceMetadata,
    build_tutor_context,
)
from backend.app.services.tutor import (
    FallbackTutorModeClassifier,
    LLMTutorAgent,
    _build_chat_messages,
    _context_to_prompt_vars,
    _normalize_tutor_instruction_request,
    _parse_mode_json,
    _restore_final_system_prompt,
    _retrieval_planning_messages,
    _should_replay_retrieval_result,
    _strip_control_prefix,
)

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


# ---------------------------------------------------------------------------
# Graph seed helper
# ---------------------------------------------------------------------------


async def _seed_graph(db_engine):
    """
    Seed a Trail with this structure:
        umbrella
        ├── topic (concept under test: Derivatives)
        │   ├── prerequisite: Limits → Derivatives
        │   ├── contains: Derivatives → Chain Rule
        │   └── application: Derivatives → Optimization
        └── Integrals (no edges to Derivatives)
    """
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        ws = Workspace(name="Service Test WS")
        session.add(ws)
        await session.flush()

        trail = Trail(
            workspace_id=ws.id,
            title="Calculus",
            topic="Calculus",
            goal="Master differential calculus",
            target_depth="apply",
        )
        session.add(trail)
        await session.flush()

        def _node(slug, title, level):
            return ConceptNode(
                trail_id=trail.id,
                slug=slug,
                title=title,
                node_type="concept",
                concept_level=level,
                difficulty="beginner",
                bloom_level="understand",
                mastery_check_labels=[f"check_{slug}"],
                metadata_json={},
            )

        umbrella = _node("calculus", "Calculus", "umbrella")
        topic = _node("derivatives", "Derivatives", "topic")
        prereq = _node("limits", "Limits", "subtopic")
        subtopic = _node("chain-rule", "Chain Rule", "subtopic")
        app_concept = _node("optimization", "Optimization", "granular")
        unrelated = _node("integrals", "Integrals", "topic")

        session.add_all([umbrella, topic, prereq, subtopic, app_concept, unrelated])
        await session.flush()

        session.add(
            ConceptEdge(
                trail_id=trail.id,
                source_node_id=umbrella.id,
                target_node_id=topic.id,
                relation_type="contains",
            )
        )
        session.add(
            ConceptEdge(
                trail_id=trail.id,
                source_node_id=prereq.id,
                target_node_id=topic.id,
                relation_type="prerequisite",
            )
        )
        session.add(
            ConceptEdge(
                trail_id=trail.id,
                source_node_id=topic.id,
                target_node_id=subtopic.id,
                relation_type="contains",
            )
        )
        session.add(
            ConceptEdge(
                trail_id=trail.id,
                source_node_id=topic.id,
                target_node_id=app_concept.id,
                relation_type="application",
            )
        )

        await session.commit()
        return (
            ws.id,
            trail.id,
            topic.id,
            {
                "umbrella": umbrella.id,
                "prereq": prereq.id,
                "subtopic": subtopic.id,
                "app": app_concept.id,
                "unrelated": unrelated.id,
            },
        )


async def _make_db_context(
    db_session, ws_id, trail_id, concept_id, message="test", user_turn_index=0
):
    """Create a Conversation and load trail/concept, return TutorContext."""
    conv = Conversation(workspace_id=ws_id, trail_id=trail_id, concept_id=concept_id)
    db_session.add(conv)
    await db_session.flush()

    trail = await db_session.scalar(select(Trail).where(Trail.id == trail_id))
    concept = await db_session.scalar(select(ConceptNode).where(ConceptNode.id == concept_id))
    assert trail is not None
    assert concept is not None

    return await build_tutor_context(
        db_session,
        conversation=conv,
        concept=concept,
        trail=trail,
        learner_message=message,
        user_turn_index=user_turn_index,
    ), conv


# ---------------------------------------------------------------------------
# build_tutor_context tests
# ---------------------------------------------------------------------------


async def test_context_includes_current_concept(db_engine, db_session):
    ws_id, trail_id, concept_id, ids = await _seed_graph(db_engine)
    ctx, _ = await _make_db_context(
        db_session, ws_id, trail_id, concept_id, "What is a derivative?"
    )

    assert ctx.concept.title == "Derivatives"
    assert ctx.concept.id == concept_id


async def test_context_includes_prerequisites(db_engine, db_session):
    ws_id, trail_id, concept_id, ids = await _seed_graph(db_engine)
    ctx, _ = await _make_db_context(db_session, ws_id, trail_id, concept_id)

    prereq_titles = [c.title for c in ctx.prerequisites]
    assert "Limits" in prereq_titles


async def test_context_includes_containing_and_contained_nodes(db_engine, db_session):
    ws_id, trail_id, concept_id, ids = await _seed_graph(db_engine)
    ctx, _ = await _make_db_context(db_session, ws_id, trail_id, concept_id)

    containing_titles = [c.title for c in ctx.containing_nodes]
    contained_titles = [c.title for c in ctx.contained_nodes]

    assert "Calculus" in containing_titles
    assert "Chain Rule" in contained_titles


async def test_context_includes_application_nodes(db_engine, db_session):
    ws_id, trail_id, concept_id, ids = await _seed_graph(db_engine)
    ctx, _ = await _make_db_context(db_session, ws_id, trail_id, concept_id)

    app_titles = [c.title for c in ctx.application_nodes]
    assert "Optimization" in app_titles


async def test_context_includes_trail_topic_and_goal(db_engine, db_session):
    ws_id, trail_id, concept_id, ids = await _seed_graph(db_engine)
    ctx, _ = await _make_db_context(db_session, ws_id, trail_id, concept_id)

    assert ctx.trail.topic == "Calculus"
    assert "differential calculus" in ctx.trail.goal


async def test_context_includes_recent_turns(db_engine, db_session):
    ws_id, trail_id, concept_id, ids = await _seed_graph(db_engine)

    # Create a conversation and add a prior turn.
    conv = Conversation(workspace_id=ws_id, trail_id=trail_id, concept_id=concept_id)
    db_session.add(conv)
    await db_session.flush()

    prior_turn = ConversationTurn(
        conversation_id=conv.id,
        role="user",
        kind="visible",
        content="Earlier question",
        mode=None,
        turn_index=0,
    )
    db_session.add(prior_turn)
    await db_session.flush()

    trail = await db_session.scalar(select(Trail).where(Trail.id == trail_id))
    concept = await db_session.scalar(select(ConceptNode).where(ConceptNode.id == concept_id))

    # user_turn_index=1 so recent_turns fetches turns with index < 1
    ctx = await build_tutor_context(
        db_session,
        conversation=conv,
        concept=concept,
        trail=trail,
        learner_message="New question",
        user_turn_index=1,
    )

    assert len(ctx.recent_turns) == 1
    assert ctx.recent_turns[0].content == "Earlier question"


async def test_context_keeps_tool_turns_with_retained_visible_window(db_engine, db_session):
    ws_id, trail_id, concept_id, _ = await _seed_graph(db_engine)

    conv = Conversation(workspace_id=ws_id, trail_id=trail_id, concept_id=concept_id)
    db_session.add(conv)
    await db_session.flush()

    for index in range(12):
        db_session.add(
            ConversationTurn(
                conversation_id=conv.id,
                role="user" if index % 2 == 0 else "assistant",
                kind="visible",
                content=f"visible-{index}",
                mode=None if index % 2 == 0 else "socratic",
                turn_index=index,
            )
        )

    db_session.add(
        ConversationTurn(
            conversation_id=conv.id,
            role="assistant",
            kind="tool_call",
            content='<tool name="get_tutor_instructions" mode="direct" />',
            mode="direct",
            turn_index=12,
        )
    )
    db_session.add(
        ConversationTurn(
            conversation_id=conv.id,
            role="tool",
            kind="tool_result",
            content=(
                '<tool_result name="get_tutor_instructions" mode="direct">'
                "Use direct mode.</tool_result>"
            ),
            mode="direct",
            turn_index=13,
        )
    )
    db_session.add(
        ConversationTurn(
            conversation_id=conv.id,
            role="assistant",
            kind="visible",
            content="visible-12",
            mode="direct",
            turn_index=14,
        )
    )
    await db_session.flush()

    trail = await db_session.scalar(select(Trail).where(Trail.id == trail_id))
    concept = await db_session.scalar(select(ConceptNode).where(ConceptNode.id == concept_id))

    ctx = await build_tutor_context(
        db_session,
        conversation=conv,
        concept=concept,
        trail=trail,
        learner_message="New question",
        user_turn_index=15,
    )

    kept_contents = [turn.content for turn in ctx.recent_turns]
    assert '<tool name="get_tutor_instructions" mode="direct" />' in kept_contents
    expected_tool_result = (
        '<tool_result name="get_tutor_instructions" mode="direct">Use direct mode.</tool_result>'
    )
    assert expected_tool_result in kept_contents
    assert "visible-0" not in kept_contents


async def test_context_does_not_include_unrelated_nodes(db_engine, db_session):
    """The unrelated concept (no edges to Derivatives) must not appear in context."""
    ws_id, trail_id, concept_id, ids = await _seed_graph(db_engine)
    ctx, _ = await _make_db_context(db_session, ws_id, trail_id, concept_id)

    all_context_ids = (
        {c.id for c in ctx.prerequisites}
        | {c.id for c in ctx.contained_nodes}
        | {c.id for c in ctx.containing_nodes}
        | {c.id for c in ctx.related}
        | {c.id for c in ctx.application_nodes}
    )
    assert ids["unrelated"] not in all_context_ids, "Integrals (unrelated) must not be in context"


async def test_context_sources_are_empty_when_none_linked(db_engine, db_session):
    """When no sources are linked to the concept, sources renders as 'none available'."""
    ws_id, trail_id, concept_id, ids = await _seed_graph(db_engine)
    ctx, _ = await _make_db_context(db_session, ws_id, trail_id, concept_id)

    vars_ = _context_to_prompt_vars("socratic", ctx)
    assert vars_["sources"] == "none available"
    assert vars_["concept_id"] == str(concept_id)


# ---------------------------------------------------------------------------
# FallbackTutorModeClassifier tests
# ---------------------------------------------------------------------------


def _make_context(message: str) -> TutorContext:
    """Build a minimal TutorContext for classifier tests using simple namespace objects."""
    from types import SimpleNamespace

    concept = SimpleNamespace(
        title="Test Concept",
        concept_level="topic",
        bloom_level="understand",
        id=uuid.uuid4(),
    )
    trail = SimpleNamespace(
        topic="Test Topic",
        goal="Learn stuff",
        id=uuid.uuid4(),
    )

    return TutorContext(
        conversation_id=uuid.uuid4(),
        concept=cast(ConceptNode, concept),
        trail=cast(Trail, trail),
        learner_message=message,
        user_turn_index=0,
    )


class _StubTaggedLLMClient:
    def __init__(self, *streams: list[tuple[str, str]]) -> None:
        self._streams = [list(stream) for stream in streams]
        self.calls: list[list[dict]] = []

    async def chat_stream_tagged(self, messages: list[dict], **_: object):
        if not self._streams:
            raise AssertionError("Unexpected extra chat_stream_tagged call")
        self.calls.append(messages)
        for kind, chunk in self._streams.pop(0):
            yield (kind, chunk)


class _StubToolEventLLMClient(_StubTaggedLLMClient):
    def __init__(self, *streams: list[tuple[str, str]], event_streams: list | None = None) -> None:
        super().__init__(*streams)
        self._event_streams = list(event_streams or [])
        self.event_calls: list[list[dict]] = []

    async def chat_stream_events(self, messages: list[dict], **_: object):
        if not self._event_streams:
            raise AssertionError("Unexpected extra chat_stream_events call")
        self.event_calls.append(messages)
        for event in self._event_streams.pop(0):
            yield event


class _StaticPromptRegistry(PromptRegistry):
    def render(self, task: str, variables: dict[str, object], version: int | None = None) -> str:
        return f"{task} prompt mastery={variables.get('mastery_status')}"


async def test_fallback_classifier_default_is_socratic():
    clf = FallbackTutorModeClassifier()
    ctx = _make_context("How does this work?")
    assert await clf.classify(ctx) == "socratic"


async def test_fallback_classifier_direct_on_explain():
    clf = FallbackTutorModeClassifier()
    ctx = _make_context("Can you explain what a derivative is?")
    assert await clf.classify(ctx) == "direct"


async def test_fallback_classifier_default_on_what_is():
    clf = FallbackTutorModeClassifier()
    ctx = _make_context("What is a limit in calculus?")
    assert await clf.classify(ctx) == "socratic"


async def test_fallback_classifier_direct_on_just_tell_me():
    clf = FallbackTutorModeClassifier()
    ctx = _make_context("Just tell me what a limit is.")
    assert await clf.classify(ctx) == "direct"


async def test_fallback_classifier_direct_on_summarise():
    clf = FallbackTutorModeClassifier()
    ctx = _make_context("Summarise this concept for me.")
    assert await clf.classify(ctx) == "direct"


async def test_fallback_classifier_repair_on_confused():
    clf = FallbackTutorModeClassifier()
    ctx = _make_context("I'm confused about how this works")
    assert await clf.classify(ctx) == "repair"


async def test_fallback_classifier_repair_on_i_thought():
    clf = FallbackTutorModeClassifier()
    ctx = _make_context("I thought derivatives were always positive")
    assert await clf.classify(ctx) == "repair"


async def test_fallback_classifier_quiz_prompt_on_test_me():
    clf = FallbackTutorModeClassifier()
    ctx = _make_context("Test me on what I've learned so far")
    assert await clf.classify(ctx) == "quiz_prompt"


async def test_fallback_classifier_quiz_prompt_on_quiz_me():
    clf = FallbackTutorModeClassifier()
    ctx = _make_context("Can you quiz me on derivatives?")
    assert await clf.classify(ctx) == "quiz_prompt"


async def test_fallback_classifier_explore_on_real_world():
    clf = FallbackTutorModeClassifier()
    ctx = _make_context("How is this used in the real world?")
    assert await clf.classify(ctx) == "explore"


async def test_fallback_classifier_explore_on_application():
    clf = FallbackTutorModeClassifier()
    ctx = _make_context("How are derivatives applied in the real world?")
    assert await clf.classify(ctx) == "explore"


# ---------------------------------------------------------------------------
# _parse_mode_json tests
# ---------------------------------------------------------------------------


def test_parse_mode_json_valid():
    raw = '{"mode": "direct", "reason": "learner asked for explanation"}'
    assert _parse_mode_json(raw) == "direct"


def test_parse_mode_json_invalid_mode_falls_back_to_socratic():
    raw = '{"mode": "lecture", "reason": "unknown"}'
    assert _parse_mode_json(raw) == "socratic"


def test_parse_mode_json_malformed_json_falls_back_to_socratic():
    assert _parse_mode_json("not json at all") == "socratic"


def test_parse_mode_json_empty_falls_back_to_socratic():
    assert _parse_mode_json("") == "socratic"


def test_parse_mode_json_strips_markdown_fences():
    raw = '```json\n{"mode": "repair", "reason": "confused"}\n```'
    assert _parse_mode_json(raw) == "repair"


def test_parse_mode_json_all_valid_modes():
    for mode in ("socratic", "direct", "repair", "quiz_prompt", "explore"):
        raw = f'{{"mode": "{mode}", "reason": "test"}}'
        assert _parse_mode_json(raw) == mode


# ---------------------------------------------------------------------------
# _context_to_prompt_vars tests
# ---------------------------------------------------------------------------


def test_context_to_prompt_vars_socratic_mode():
    ctx = _make_context("Hello")
    from types import SimpleNamespace

    ctx.concept = cast(
        ConceptNode,
        SimpleNamespace(
            title="Derivatives",
            concept_level="topic",
            bloom_level="apply",
            id=uuid.uuid4(),
        ),
    )
    ctx.trail = cast(
        Trail,
        SimpleNamespace(
            topic="Calculus",
            goal="Master calculus",
            id=uuid.uuid4(),
        ),
    )

    vars_ = _context_to_prompt_vars("socratic", ctx)

    assert "Derivatives" in vars_["concept"]
    assert vars_["bloom_target"] == "apply"
    assert vars_["learning_goal"] == "Master calculus"
    assert vars_["learner_message"] == "Hello"
    assert vars_["mastery_status"] == "not_started"
    assert "application_nodes" not in vars_, "socratic mode must not include application_nodes"


async def test_context_reads_real_mastery_status(db_engine, db_session):
    ws_id, trail_id, concept_id, _ = await _seed_graph(db_engine)
    db_session.add(
        MasteryRecord(
            workspace_id=ws_id,
            concept_id=concept_id,
            status="needs_review",
            bloom_level="understand",
            score=0.6,
        )
    )
    await db_session.commit()

    ctx, _ = await _make_db_context(db_session, ws_id, trail_id, concept_id)

    assert ctx.mastery_status == "needs_review"


def test_context_to_prompt_vars_explore_mode_includes_application_nodes():
    ctx = _make_context("Why does this matter?")
    from types import SimpleNamespace

    app_node = cast(ConceptNode, SimpleNamespace(title="Neural Networks", id=uuid.uuid4()))
    ctx.application_nodes = [app_node]

    vars_ = _context_to_prompt_vars("explore", ctx)
    assert "application_nodes" in vars_
    assert "Neural Networks" in vars_["application_nodes"]


def test_context_to_prompt_vars_empty_lists_become_none_string():
    ctx = _make_context("test")
    vars_ = _context_to_prompt_vars("socratic", ctx)
    assert vars_["prerequisites"] == "none"
    assert vars_["contained_nodes"] == "none"
    assert vars_["containing_nodes"] == "none"


# ---------------------------------------------------------------------------
# _build_chat_messages tests
# ---------------------------------------------------------------------------


def test_build_chat_messages_no_history():
    """With no prior turns the messages array is [system, user]."""
    msgs = _build_chat_messages("Be a tutor.", [], "What is a derivative?")
    assert msgs == [
        {"role": "system", "content": "Be a tutor."},
        {"role": "user", "content": "What is a derivative?"},
    ]


def test_build_chat_messages_with_history():
    """Prior turns are inserted between the system message and the latest user turn."""
    from types import SimpleNamespace

    turns = [
        SimpleNamespace(role="user", content="Hello"),
        SimpleNamespace(role="assistant", content="Hi there"),
    ]
    msgs = _build_chat_messages("Be a tutor.", turns, "Tell me more")
    assert msgs[0] == {"role": "system", "content": "Be a tutor."}
    assert msgs[1] == {"role": "user", "content": "Hello"}
    assert msgs[2] == {"role": "assistant", "content": "Hi there"}
    assert msgs[3] == {"role": "user", "content": "Tell me more"}
    assert len(msgs) == 4


def test_build_chat_messages_replays_tool_turns_as_assistant_messages():
    from types import SimpleNamespace

    turns = [
        SimpleNamespace(
            role="assistant",
            kind="tool_call",
            content='<tool name="get_tutor_instructions" mode="direct" />',
            mode="direct",
        ),
        SimpleNamespace(
            role="tool",
            kind="tool_result",
            content=(
                '<tool_result name="get_tutor_instructions" mode="direct">'
                "Use direct mode.</tool_result>"
            ),
            mode="direct",
        ),
    ]

    msgs = _build_chat_messages("Be a tutor.", turns, "Latest")

    assert msgs == [
        {"role": "system", "content": "Be a tutor."},
        {"role": "assistant", "content": '<tool name="get_tutor_instructions" mode="direct" />'},
        {
            "role": "assistant",
            "content": (
                '<tool_result name="get_tutor_instructions" mode="direct">'
                "Use direct mode.</tool_result>"
            ),
        },
        {"role": "user", "content": "Latest"},
    ]


def test_build_chat_messages_system_is_always_first():
    """System message must always be the first element regardless of history."""
    from types import SimpleNamespace

    turns = [SimpleNamespace(role="user", content="Prior question")]
    msgs = _build_chat_messages("Instructions.", turns, "New question")
    assert msgs[0]["role"] == "system"


def test_strip_control_prefix_removes_leaked_mode_line():
    raw = '<mode name="socratic" />\nVisible answer.'
    assert _strip_control_prefix(raw) == "Visible answer."


def test_strip_control_prefix_removes_leaked_tool_line():
    raw = '<tool name="get_tutor_instructions" mode="direct" />\nVisible answer.'
    assert _strip_control_prefix(raw) == "Visible answer."


def test_tutor_instruction_request_uses_normalized_tool_schema():
    call = _normalize_tutor_instruction_request("direct")

    assert call.is_valid
    assert call.name == "get_tutor_instructions"
    assert call.arguments == {"mode": "direct"}
    assert call.provider == "colearni_compat"


def test_tutor_instruction_request_rejects_invalid_arguments_safely():
    call = _normalize_tutor_instruction_request("lecture")

    assert not call.is_valid
    assert call.arguments == {"mode": "lecture"}
    assert call.validation_error is not None
    assert "lecture" not in call.validation_error


def test_build_chat_messages_learner_message_is_always_last():
    """Learner's latest message must always be the final element."""
    from types import SimpleNamespace

    turns = [
        SimpleNamespace(role="user", content="A"),
        SimpleNamespace(role="assistant", content="B"),
    ]
    msgs = _build_chat_messages("System.", turns, "Latest")
    assert msgs[-1] == {"role": "user", "content": "Latest"}


async def test_locked_direct_summary_request_only_emits_socratic_question():
    from types import SimpleNamespace

    client = _StubTaggedLLMClient(
        [("text", '<tool name="get_tutor_instructions" mode="direct" />')],
        [
            ("text", '<mode name="socratic" />\nMylo Xyloto explores hope and escape. '),
            ("text", "What theme do you think ties the album together?"),
        ],
    )
    agent = LLMTutorAgent(client, max_tokens=512)
    ctx = _make_context("Summarise the topics within Mylo Xyloto")
    ctx.mastery_status = "learning"
    ctx.concept = cast(
        ConceptNode,
        SimpleNamespace(
            title="Mylo Xyloto",
            concept_level="topic",
            bloom_level="understand",
            id=uuid.uuid4(),
        ),
    )

    events = [(kind, chunk) async for kind, chunk in agent.respond_stream(ctx)]

    assert [chunk for kind, chunk in events if kind == "mode"] == ["socratic"]
    assert [chunk for kind, chunk in events if kind == "status"] == [
        "calling_tool",
        "tool_called",
        "tool_complete",
    ]
    assert [chunk for kind, chunk in events if kind == "text"] == [
        "What theme do you think ties the album together?"
    ]


async def test_locked_direct_summary_without_question_uses_default_socratic_question():
    from types import SimpleNamespace

    client = _StubTaggedLLMClient(
        [("text", '<tool name="get_tutor_instructions" mode="direct" />')],
        [("text", "Mylo Xyloto explores hope, color, and resistance.")],
    )
    agent = LLMTutorAgent(client, max_tokens=512)
    ctx = _make_context("Summarise the topics within Mylo Xyloto")
    ctx.mastery_status = "learning"
    ctx.concept = cast(
        ConceptNode,
        SimpleNamespace(
            title="Mylo Xyloto",
            concept_level="topic",
            bloom_level="understand",
            id=uuid.uuid4(),
        ),
    )

    events = [(kind, chunk) async for kind, chunk in agent.respond_stream(ctx)]

    assert [chunk for kind, chunk in events if kind == "text"] == [
        "What do you think are the main topics or themes within Mylo Xyloto?"
    ]


async def test_prepare_mode_stream_emits_first_pass_thinking_live():
    """First-call reasoning must stream as live thinking events, not be buffered."""
    client = _StubTaggedLLMClient(
        [
            ("thinking", "Considering the learner's question..."),
            ("thinking", " choosing a mode."),
            ("text", '<mode name="socratic" />'),
        ],
    )
    agent = LLMTutorAgent(client, registry=_StaticPromptRegistry(), max_tokens=512)

    events: list[tuple[str, object]] = []
    prep = None
    async for kind, payload in agent.prepare_mode_stream(_make_context("Help me")):
        if kind == "__prep__":
            prep = payload
            break
        events.append((kind, payload))

    assert prep is not None
    assert prep.mode == "socratic"
    # Thinking streamed live during the first pass.
    assert ("status", "thinking") in events
    assert [chunk for kind, chunk in events if kind == "thinking"] == [
        "Considering the learner's question...",
        " choosing a mode.",
    ]
    # Live-streamed reasoning must NOT be duplicated in the buffered events.
    assert all(kind != "thinking" for kind, _ in prep.buffered_events)


async def test_non_tool_mode_final_call_uses_final_response_prompt():
    client = _StubTaggedLLMClient(
        [("text", '<mode name="socratic" />')],
        [("text", "What do you already understand about this concept?")],
    )
    agent = LLMTutorAgent(client, max_tokens=512)

    events = [
        (kind, chunk) async for kind, chunk in agent.respond_stream(_make_context("Check me"))
    ]

    assert [chunk for kind, chunk in events if kind == "text"] == [
        "What do you already understand about this concept?"
    ]
    assert len(client.calls) == 2
    final_system_prompt = client.calls[1][0]["content"]
    assert "Final response contract" in final_system_prompt
    assert "First choose the response mode" not in final_system_prompt
    assert {"role": "assistant", "content": '<mode name="socratic" />'} not in client.calls[1]


async def test_mastered_direct_request_keeps_direct_mode_and_prompt():
    client = _StubTaggedLLMClient(
        [("text", '<tool name="get_tutor_instructions" mode="direct" />')],
        [("text", "feelslikeimfallinginlove is the only lead single.")],
    )
    agent = LLMTutorAgent(client, registry=_StaticPromptRegistry(), max_tokens=512)
    ctx = _make_context("Which are the lead singles?")
    ctx.mastery_status = "mastered"

    events = [(kind, chunk) async for kind, chunk in agent.respond_stream(ctx)]

    assert [chunk for kind, chunk in events if kind == "mode"] == ["direct"]
    assert [chunk for kind, chunk in events if kind == "text"] == [
        "feelslikeimfallinginlove is the only lead single."
    ]
    assert [kind for kind, _chunk in events if kind in {"tool_call", "tool_result"}] == []
    final_system_prompt = client.calls[1][0]["content"]
    assert "tutor_direct prompt mastery=mastered" in final_system_prompt
    assert "do not append a Socratic follow-up" in final_system_prompt
    assert len(client.calls[1]) == 2


async def test_retrieval_planner_text_is_reused_when_no_tool_called(db_session):
    client = _StubToolEventLLMClient(
        [("text", '<tool name="get_tutor_instructions" mode="direct" />')],
        event_streams=[
            [
                NormalizedStreamEvent.text_delta("Direct answer from no-tool planner."),
                NormalizedStreamEvent.done_event(),
            ]
        ],
    )
    agent = LLMTutorAgent(client, registry=_StaticPromptRegistry(), max_tokens=512)
    ctx = _make_context("What is the answer?")
    ctx.mastery_status = "mastered"
    ctx.sources = [
        TutorSourceMetadata(
            id=uuid.uuid4(),
            title="Notes",
            url=None,
            origin="manual",
            access="private",
            license=None,
            relation="supports",
        )
    ]

    events = []
    prep = await agent.prepare_mode(ctx)
    for event in prep.buffered_events:
        events.append(event)
    retrieval_messages = _retrieval_planning_messages(prep.messages_after_mode)
    from backend.app.services.conversations import _run_retrieval_loop

    retrieval_loop = await _run_retrieval_loop(
        retrieval_messages,
        RETRIEVAL_TOOLS,
        session=db_session,
        workspace_id=uuid.uuid4(),
        concept_id=ctx.concept.id,
        llm_client=client,
    )

    assert retrieval_loop.tool_results == []
    assert retrieval_loop.text == "Direct answer from no-tool planner."
    assert len(client.calls) == 1
    assert len(client.event_calls) == 1


async def test_retrieval_tool_call_preview_includes_search_query(db_session):
    client = _StubToolEventLLMClient(
        event_streams=[
            [
                NormalizedStreamEvent.tool_call_event(
                    NormalizedToolCall(
                        call_id="call_search",
                        name="search_sources",
                        arguments={"query": "lead singles"},
                    )
                )
            ],
            [
                NormalizedStreamEvent.text_delta("enough context"),
                NormalizedStreamEvent.done_event(),
            ],
        ],
    )

    async def fake_search(*, query, workspace_id, session, concept_id):
        assert query == "lead singles"
        return []

    from backend.app.services.conversations import _run_retrieval_loop

    with patch(
        "backend.app.services.conversations.search_sources_by_text",
        side_effect=fake_search,
    ):
        retrieval_loop = await _run_retrieval_loop(
            [{"role": "user", "content": "Which are the lead singles?"}],
            RETRIEVAL_TOOLS,
            session=db_session,
            workspace_id=uuid.uuid4(),
            concept_id=uuid.uuid4(),
            llm_client=client,
        )

    assert retrieval_loop.tool_results[0].public_preview["query"] == "lead singles"


def test_direct_prompt_tells_mastered_mode_not_to_append_socratic_followup():
    ctx = _make_context("Which are the lead singles?")
    ctx.mastery_status = "mastered"
    agent = LLMTutorAgent(_StubTaggedLLMClient(), max_tokens=512)

    prompt = agent._final_response_prompt("direct", ctx)

    assert "Mastery status**: mastered" in prompt
    assert "do not append a Socratic follow-up" in prompt


def test_retrieval_planning_messages_reuse_no_tool_answers():
    messages = [
        {"role": "system", "content": "Final response contract"},
        {"role": "user", "content": "Check me"},
    ]

    retrieval_messages = _retrieval_planning_messages(messages)

    assert "selecting retrieval tools" in retrieval_messages[0]["content"]
    assert (
        "answer the learner directly in the already-selected mode"
        in retrieval_messages[0]["content"]
    )
    assert "Do not output `<mode .../>` tags" in retrieval_messages[0]["content"]
    assert "Prefer search_sources" in retrieval_messages[0]["content"]
    assert "Once you have enough context" in retrieval_messages[0]["content"]
    assert (
        "omit concept_id unless you are given an explicit UUID" in retrieval_messages[0]["content"]
    )


def test_restore_final_system_prompt_removes_retrieval_instruction_before_final_call():
    final_messages = [
        {"role": "system", "content": "Final response contract"},
        {"role": "user", "content": "What do you know?"},
    ]
    retrieval_messages = [
        {"role": "system", "content": "Final response contract\n\n## Retrieval tool planning only"},
        {"role": "user", "content": "What do you know?"},
        {"role": "assistant", "content": [{"type": "tool_call", "name": "search_sources"}]},
        {"role": "tool", "name": "search_sources", "content": "Result"},
    ]

    restored = _restore_final_system_prompt(final_messages, retrieval_messages)

    assert restored[0]["content"] == "Final response contract"
    assert "Retrieval tool planning only" not in restored[0]["content"]
    assert restored[2:] == retrieval_messages[2:]


def test_only_directed_document_reads_are_replayed_in_future_prompt_context():
    search_result = NormalizedToolResult(
        call_id="call_search",
        name="search_sources",
        content="Search metadata dump",
        public_preview={"preview": "Search metadata dump"},
    )
    document_result = NormalizedToolResult(
        call_id="call_read",
        name="read_document_section",
        content="Directed document content",
        public_preview={"preview": "Directed document content"},
    )

    assert _should_replay_retrieval_result(search_result) is False
    assert _should_replay_retrieval_result(document_result) is True
