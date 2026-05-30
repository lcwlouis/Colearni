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

from backend.app.agents.prompts import prompt_registry
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
    _context_to_base_prompt_vars,
    _context_to_prompt_vars,
    _infer_mode_from_message,
    _normalize_tutor_instruction_request,
    _parse_control_from_buffer,
    _parse_mode_json,
    _ParsedControl,
    _resolve_control_mode,
    _restore_final_system_prompt,
    _retrieval_planning_messages,
    _should_replay_retrieval_result,
    _strip_control_prefix,
    stream_chat_response,
)
from backend.app.settings import settings

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


class _RecordingTaggedLLMClient:
    """Tagged stub that records the ``thinking`` kwarg per call.

    Simulates a provider: ``thinking`` chunks are only emitted when the call was
    made with a truthy ``thinking`` argument, mirroring how providers suppress
    reasoning when thinking is disabled.
    """

    def __init__(self, *streams: list[tuple[str, str]]) -> None:
        self._streams = [list(stream) for stream in streams]
        self.calls: list[list[dict]] = []
        self.thinking_args: list[object] = []
        self.max_tokens_args: list[object] = []

    async def chat_stream_tagged(self, messages: list[dict], **kwargs: object):
        if not self._streams:
            raise AssertionError("Unexpected extra chat_stream_tagged call")
        self.calls.append(messages)
        thinking = kwargs.get("thinking")
        self.thinking_args.append(thinking)
        self.max_tokens_args.append(kwargs.get("max_tokens"))
        for kind, chunk in self._streams.pop(0):
            if kind == "thinking" and not thinking:
                continue
            yield (kind, chunk)


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
# Stuck-learner / prose-fallback mode inference (Bug A + Bug B)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "I actually genuinely don't know",
        "I don't know",
        "honestly no idea where to start",
        "I'm completely lost",
        "I give up",
        "no clue, sorry",
    ],
)
async def test_fallback_classifier_routes_stuck_learner_to_repair(message):
    """A learner who says they're stuck should be taught (repair), not re-questioned."""
    clf = FallbackTutorModeClassifier()
    ctx = _make_context(message)
    assert await clf.classify(ctx) == "repair"


def test_infer_mode_from_message_stuck_is_repair():
    assert _infer_mode_from_message("I really don't know") == "repair"
    assert _infer_mode_from_message("I'm stuck on this") == "repair"


def test_infer_mode_from_message_quiz_beats_stuck():
    # "quiz me" is an explicit readiness signal even if other words appear.
    assert _infer_mode_from_message("quiz me, I'm not sure I'm ready") == "quiz_prompt"


def test_infer_mode_from_message_defaults_to_socratic():
    assert _infer_mode_from_message("How does TCP relate to this?") == "socratic"


def test_parse_control_from_buffer_parses_mode_line():
    parsed = _parse_control_from_buffer('<mode name="repair" />\n')
    assert parsed is not None
    assert parsed.kind == "mode"
    assert parsed.value == "repair"


def test_parse_control_from_buffer_parses_tool_line():
    parsed = _parse_control_from_buffer('<tool name="get_tutor_instructions" mode="direct" />\n')
    assert parsed is not None
    assert parsed.kind == "tool"
    assert parsed.value == "direct"


def test_parse_control_from_buffer_finds_tag_after_leading_blank_line():
    parsed = _parse_control_from_buffer('\n<mode name="explore" />')
    assert parsed is not None
    assert parsed.kind == "mode"
    assert parsed.value == "explore"


def test_parse_control_from_buffer_flags_prose_as_fallback():
    """When the classifier writes a learner-facing reply, parsing signals fallback."""
    prose = "That's completely fine — the layer you want is the Network Layer.\nMore text."
    parsed = _parse_control_from_buffer(prose)
    assert parsed is not None
    assert parsed.kind == "fallback"


def test_parse_control_from_buffer_waits_on_partial_tag():
    # A partial control tag is not yet prose: keep buffering.
    assert _parse_control_from_buffer('<mode name="soc') is None


def test_resolve_control_mode_uses_real_tag_over_inference():
    ctx = _make_context("I don't know, I'm lost")
    parsed = _ParsedControl(kind="mode", value="explore", remainder="")
    # A real tag is authoritative even if the message looks stuck.
    assert _resolve_control_mode(parsed, ctx) == "explore"


def test_resolve_control_mode_infers_from_message_on_fallback():
    ctx = _make_context("I actually genuinely don't know")
    parsed = _ParsedControl(kind="fallback", value="socratic", remainder="")
    # Prose fallback must NOT blindly return socratic for a stuck learner.
    assert _resolve_control_mode(parsed, ctx) == "repair"


async def test_first_pass_prose_resolves_stuck_learner_to_repair():
    """End-to-end: classifier emits prose, stuck learner resolves to repair, not socratic."""
    client = _StubTaggedLLMClient(
        # First (classifier) call ignores the contract and writes a reply.
        [("text", "That's completely fine — the answer is the Network Layer.\n")],
        # Second (final) call produces the visible answer.
        [("text", "Here is what the Network Layer does...")],
    )
    agent = LLMTutorAgent(client, registry=_StaticPromptRegistry(), max_tokens=512)

    events = [
        (kind, chunk)
        async for kind, chunk in agent.respond_stream(
            _make_context("I actually genuinely don't know")
        )
    ]

    modes = [chunk for kind, chunk in events if kind == "mode"]
    assert modes == ["repair"]


async def test_first_pass_prose_keeps_socratic_for_engaged_learner():
    """A normal content question with prose fallback still resolves to socratic."""
    client = _StubTaggedLLMClient(
        [("text", "Great question! Let's think about it.\n")],
        [("text", "What do you already know about this?")],
    )
    agent = LLMTutorAgent(client, registry=_StaticPromptRegistry(), max_tokens=512)

    events = [
        (kind, chunk)
        async for kind, chunk in agent.respond_stream(
            _make_context("How does the network layer route packets?")
        )
    ]

    modes = [chunk for kind, chunk in events if kind == "mode"]
    assert modes == ["socratic"]


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


async def test_gated_direct_teaches_instead_of_coercing_a_question():
    """A `direct` request while still learning must TEACH (guided), not refuse and
    bounce a bare Socratic question back at the learner."""
    from types import SimpleNamespace

    teaching = (
        "Imbibition is water absorption by hydrophilic solids like seeds. "
        "Step 1: water binds to the surface. Step 2: the seed swells. "
        "Does that picture make sense so far?"
    )
    client = _StubTaggedLLMClient(
        [("text", '<tool name="get_tutor_instructions" mode="direct" />')],
        [("text", teaching)],
    )
    agent = LLMTutorAgent(client, max_tokens=512)
    ctx = _make_context("Walk me through the process of imbibition.")
    ctx.mastery_status = "learning"
    ctx.concept = cast(
        ConceptNode,
        SimpleNamespace(
            title="Imbibition",
            concept_level="topic",
            bloom_level="understand",
            id=uuid.uuid4(),
        ),
    )

    events = [(kind, chunk) async for kind, chunk in agent.respond_stream(ctx)]

    # The turn is labelled `direct` (we are teaching what the learner asked for),
    # not silently downgraded to socratic.
    assert [chunk for kind, chunk in events if kind == "mode"] == ["direct"]
    # The model's actual teaching streams through verbatim — it is NOT discarded
    # and replaced with a single bare question.
    assert [chunk for kind, chunk in events if kind == "text"] == [teaching]


def test_gated_direct_final_prompt_carries_guided_teaching_and_guardrail():
    """The final prompt for a gated `direct` turn must use the guided-teaching prompt
    AND embed the no-cheatsheet / no-answer-dump guardrail so an answer-extraction
    request (e.g. "make me a cheatsheet") is redirected rather than satisfied."""
    ctx = _make_context("Just give me all the answers / make me a cheatsheet for the exam.")
    ctx.mastery_status = "learning"
    agent = LLMTutorAgent(_StubTaggedLLMClient(), max_tokens=512)

    prompt = agent._final_response_prompt("direct", ctx)

    # Guided teaching, not the crisp mastered-direct answer prompt.
    assert "guided teaching" in prompt.lower()
    assert "never refuse" in prompt.lower() or "do not refuse" in prompt.lower()
    # Guardrail wording is present in both the gated prompt and the shared contract.
    assert "cheatsheet" in prompt.lower()
    assert "answer key" in prompt.lower()
    assert "redirect" in prompt.lower()


def test_gated_direct_prep_does_not_coerce_to_socratic():
    """_make_mode_prep for a gated `direct` request keeps mode `direct` and does not
    flag any locked-socratic buffering (the old refuse-and-ask path is gone)."""
    ctx = _make_context("Explain the Calvin cycle to me.")
    ctx.mastery_status = "learning"
    agent = LLMTutorAgent(_StubTaggedLLMClient(), registry=_StaticPromptRegistry(), max_tokens=512)

    prep = agent._make_mode_prep("direct", ctx, [{"role": "system", "content": "x"}], [])

    assert prep.mode == "direct"
    assert not hasattr(prep, "locked_socratic")


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


async def test_mode_selection_thinking_off_by_default(monkeypatch):
    """The first (mode-selection) call must receive thinking=False by default and
    emit no thinking events, so mode-selection reasoning never leaks into the trace."""
    monkeypatch.setattr(settings, "tutor_mode_selection_thinking", False)
    client = _RecordingTaggedLLMClient(
        [("thinking", "mode-selection reasoning"), ("text", '<mode name="socratic" />')],
        [("text", "Visible answer")],
    )
    agent = LLMTutorAgent(client, registry=_StaticPromptRegistry(), max_tokens=512)

    events = [(kind, chunk) async for kind, chunk in agent.respond_stream(_make_context("Help me"))]

    # First call = mode selection; reasoning disabled.
    assert client.thinking_args[0] is False
    # No thinking events emitted for the mode-selection phase.
    assert all(kind != "thinking" for kind, _ in events)
    assert [chunk for kind, chunk in events if kind == "mode"] == ["socratic"]


async def test_mode_selection_thinking_enabled_via_settings(monkeypatch):
    """With the setting enabled, the mode-selection call receives thinking=True."""
    monkeypatch.setattr(settings, "tutor_mode_selection_thinking", True)
    client = _RecordingTaggedLLMClient(
        [("thinking", "mode-selection reasoning"), ("text", '<mode name="socratic" />')],
        [("text", "Visible answer")],
    )
    agent = LLMTutorAgent(client, registry=_StaticPromptRegistry(), max_tokens=512)

    events = [(kind, chunk) async for kind, chunk in agent.respond_stream(_make_context("Help me"))]

    assert client.thinking_args[0] is True
    # Reasoning now surfaces for the mode-selection phase.
    assert ("thinking", "mode-selection reasoning") in events


async def test_explicit_mode_selection_thinking_overrides_settings(monkeypatch):
    """An explicit constructor argument wins over the settings default."""
    monkeypatch.setattr(settings, "tutor_mode_selection_thinking", True)
    client = _RecordingTaggedLLMClient(
        [("text", '<mode name="socratic" />')],
        [("text", "Visible answer")],
    )
    agent = LLMTutorAgent(
        client,
        registry=_StaticPromptRegistry(),
        max_tokens=512,
        mode_selection_thinking=False,
    )

    [_ async for _ in agent.respond_stream(_make_context("Help me"))]

    assert client.thinking_args[0] is False


async def test_mode_selection_uses_small_token_cap(monkeypatch):
    """The first (classifier) call uses the dedicated small cap; the second uses the full budget."""
    monkeypatch.setattr(settings, "tutor_mode_selection_max_tokens", 48)
    client = _RecordingTaggedLLMClient(
        [("text", '<mode name="socratic" />')],
        [("text", "Visible answer")],
    )
    # Construct after monkeypatch so __init__ reads the patched cap.
    agent = LLMTutorAgent(client, registry=_StaticPromptRegistry(), max_tokens=4096)

    [_ async for _ in agent.respond_stream(_make_context("Help me"))]

    # First call = mode selection/classifier: small cap. Second call = full answer budget.
    assert client.max_tokens_args[0] == 48
    assert client.max_tokens_args[1] == 4096


async def test_first_pass_is_pure_classifier_and_discards_trailing_text():
    """If the classifier call emits text after the control line, it is discarded.

    The visible answer comes only from the second (final) LLM call.
    """
    client = _StubTaggedLLMClient(
        [("text", '<mode name="socratic" />\nLEAKED discarded reply that must not surface.')],
        [("text", "What do you already understand here?")],
    )
    agent = LLMTutorAgent(client, registry=_StaticPromptRegistry(), max_tokens=512)

    events = [(kind, chunk) async for kind, chunk in agent.respond_stream(_make_context("Help"))]

    text_chunks = [chunk for kind, chunk in events if kind == "text"]
    assert text_chunks == ["What do you already understand here?"]
    assert all("LEAKED" not in chunk for _, chunk in events)
    assert [chunk for kind, chunk in events if kind == "mode"] == ["socratic"]


def test_tutor_base_prompt_is_classify_only():
    """The first-pass base prompt must instruct classify-only output, with no reply rules."""
    from backend.app.agents.prompts import prompt_registry

    body = prompt_registry.load("tutor_base").body
    assert "Output exactly one control line and STOP" in body
    assert "another step writes the learner-facing reply" in body
    # The old "write the visible reply in this pass" rules must be gone.
    assert "Visible reply rules" not in body
    assert "immediately write the visible reply" not in body
    # Mode policy and the beginner-by-default prior-knowledge prior remain.
    assert "complete beginner" in body
    assert "start from the fundamentals" in body


async def test_truncate_tool_result_uses_settings(monkeypatch):
    """_truncate_tool_result must honor tutor_max_tool_result_chars."""
    from backend.app.services.conversations import _truncate_tool_result

    monkeypatch.setattr(settings, "tutor_max_tool_result_chars", 5)
    assert _truncate_tool_result("abcdefghij") == "abcde ... [truncated]"
    assert _truncate_tool_result("abcd") == "abcd"


async def test_recent_visible_turns_limit_uses_settings(db_engine, db_session, monkeypatch):
    """build_tutor_context must clamp recent turns to tutor_recent_visible_turns_limit."""
    monkeypatch.setattr(settings, "tutor_recent_visible_turns_limit", 3)
    ws_id, trail_id, concept_id, _ = await _seed_graph(db_engine)

    conv = Conversation(workspace_id=ws_id, trail_id=trail_id, concept_id=concept_id)
    db_session.add(conv)
    await db_session.flush()

    for index in range(8):
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
    await db_session.flush()

    trail = await db_session.scalar(select(Trail).where(Trail.id == trail_id))
    concept = await db_session.scalar(select(ConceptNode).where(ConceptNode.id == concept_id))

    ctx = await build_tutor_context(
        db_session,
        conversation=conv,
        concept=concept,
        trail=trail,
        learner_message="next",
        user_turn_index=8,
    )

    assert len(ctx.recent_turns) == 3
    assert [turn.content for turn in ctx.recent_turns] == [
        "visible-5",
        "visible-6",
        "visible-7",
    ]


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


def test_final_response_contract_allows_markdown_hierarchy_and_concise_default():
    """The shared final-response contract is concise-by-default and allows markdown headers."""
    ctx = _make_context("Explain this")
    agent = LLMTutorAgent(_StubTaggedLLMClient(), max_tokens=512)

    prompt = agent._final_response_prompt("direct", ctx)

    assert "Default to a concise reply" in prompt
    assert "markdown headers" in prompt
    assert "only when the topic genuinely needs it" in prompt
    assert "walls of text" in prompt


def test_final_mode_prompts_drop_hard_word_caps():
    """Relaxed length guidance must reach the rendered socratic/repair/explore prompts."""
    ctx = _make_context("Tell me more")
    agent = LLMTutorAgent(_StubTaggedLLMClient(), max_tokens=512)

    for mode in ("socratic", "repair", "explore"):
        prompt = agent._final_response_prompt(mode, ctx)
        # The old rigid caps are gone.
        assert "under 80 words" not in prompt
        assert "under 140 words" not in prompt
        assert "under 170 words" not in prompt
        # Concise-by-default guidance is present (via the mode prompt or the contract).
        assert "concise" in prompt.lower()

    # Socratic stays question-led even after relaxing the cap.
    socratic_prompt = agent._final_response_prompt("socratic", ctx)
    assert "ONE focused guiding question" in socratic_prompt


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


# ---------------------------------------------------------------------------
# Phase 13.5b: worked-example-first opening move
# ---------------------------------------------------------------------------


async def _add_visible_turn(db_session, conversation_id, *, role, content, turn_index):
    turn = ConversationTurn(
        conversation_id=conversation_id,
        role=role,
        kind="visible",
        content=content,
        turn_index=turn_index,
    )
    db_session.add(turn)
    await db_session.flush()


_PRIMER_FIXTURE = {
    "overview": "A derivative measures an instantaneous rate of change.",
    "key_terms": [
        {"term": "slope", "definition": "steepness of a line at a point"},
        {"term": "tangent", "definition": "line touching a curve at one point"},
        {"term": "limit", "definition": "value a function approaches"},
    ],
    "version": 1,
}


async def test_first_turn_sets_opening_signal_and_injects_opening_instructions(
    db_engine, db_session
):
    ws_id, trail_id, concept_id, _ = await _seed_graph(db_engine)
    ctx, _ = await _make_db_context(db_session, ws_id, trail_id, concept_id, user_turn_index=0)

    assert ctx.is_opening_turn is True
    assert ctx.primer is None  # no primer cached, and none generated

    vars_ = _context_to_base_prompt_vars(ctx)
    assert vars_["opening_turn"] == "yes"
    assert vars_["opening_guidance"] != ""

    base_prompt = prompt_registry.render("tutor_base", vars_)
    socratic_prompt = prompt_registry.render("tutor_socratic", vars_)
    # The base prompt is now a pure classifier and carries no opening guidance.
    assert "Opening turn" not in base_prompt
    assert "worked example" not in base_prompt
    # The opening guidance reaches the learner-facing (second-call) mode prompt.
    assert "Opening turn" in socratic_prompt
    assert "worked example" in socratic_prompt
    # No primer cached, so the primer block must be absent.
    assert "Concept primer" not in socratic_prompt


async def test_later_turn_does_not_set_opening_signal(db_engine, db_session):
    ws_id, trail_id, concept_id, _ = await _seed_graph(db_engine)

    conv = Conversation(workspace_id=ws_id, trail_id=trail_id, concept_id=concept_id)
    db_session.add(conv)
    await db_session.flush()
    await _add_visible_turn(db_session, conv.id, role="user", content="hi", turn_index=0)
    await _add_visible_turn(
        db_session, conv.id, role="assistant", content="a question?", turn_index=1
    )

    trail = await db_session.scalar(select(Trail).where(Trail.id == trail_id))
    concept = await db_session.scalar(select(ConceptNode).where(ConceptNode.id == concept_id))
    ctx = await build_tutor_context(
        db_session,
        conversation=conv,
        concept=concept,
        trail=trail,
        learner_message="second message",
        user_turn_index=2,
    )

    assert ctx.is_opening_turn is False

    vars_ = _context_to_base_prompt_vars(ctx)
    assert vars_["opening_turn"] == "no"
    assert vars_["opening_guidance"] == ""
    assert "Opening turn" not in prompt_registry.render("tutor_base", vars_)


async def test_cached_primer_included_in_opening_context(db_engine, db_session):
    ws_id, trail_id, concept_id, _ = await _seed_graph(db_engine)

    concept = await db_session.scalar(select(ConceptNode).where(ConceptNode.id == concept_id))
    concept.metadata_json = {"primer": _PRIMER_FIXTURE}
    await db_session.commit()

    ctx, _ = await _make_db_context(db_session, ws_id, trail_id, concept_id, user_turn_index=0)

    assert ctx.is_opening_turn is True
    assert ctx.primer is not None
    assert ctx.primer.overview == _PRIMER_FIXTURE["overview"]

    vars_ = _context_to_base_prompt_vars(ctx)
    # The opening guidance (with the cached primer) reaches the final mode prompt.
    socratic_prompt = prompt_registry.render("tutor_socratic", vars_)
    assert "Concept primer" in socratic_prompt
    assert "instantaneous rate of change" in socratic_prompt
    assert "slope" in socratic_prompt


async def test_primer_absent_does_not_trigger_generation(db_engine, db_session):
    ws_id, trail_id, concept_id, _ = await _seed_graph(db_engine)
    ctx, _ = await _make_db_context(db_session, ws_id, trail_id, concept_id, user_turn_index=0)

    # build_tutor_context only ever reads a cached primer; with none cached it stays None
    # and no LLM-backed generator is constructed or invoked.
    assert ctx.primer is None
    assert ctx.is_opening_turn is True
    assert "Concept primer" not in prompt_registry.render(
        "tutor_base", _context_to_base_prompt_vars(ctx)
    )


async def test_prior_knowledge_reaches_tutor_prompt(db_engine, db_session):
    ws_id, trail_id, concept_id, _ = await _seed_graph(db_engine)

    trail = await db_session.scalar(select(Trail).where(Trail.id == trail_id))
    trail.prior_knowledge = "I already understand limits and basic slopes."
    await db_session.commit()

    ctx, _ = await _make_db_context(db_session, ws_id, trail_id, concept_id, user_turn_index=0)

    assert ctx.prior_knowledge == "I already understand limits and basic slopes."

    vars_ = _context_to_base_prompt_vars(ctx)
    assert vars_["learner_prior_knowledge"] == "I already understand limits and basic slopes."
    assert "I already understand limits and basic slopes." in prompt_registry.render(
        "tutor_base", vars_
    )


async def test_absent_prior_knowledge_renders_cleanly(db_engine, db_session):
    ws_id, trail_id, concept_id, _ = await _seed_graph(db_engine)
    ctx, _ = await _make_db_context(db_session, ws_id, trail_id, concept_id, user_turn_index=0)

    assert ctx.prior_knowledge is None

    vars_ = _context_to_base_prompt_vars(ctx)
    assert vars_["learner_prior_knowledge"] == "none"
    # Rendering must not raise on the missing optional field.
    prompt = prompt_registry.render("tutor_base", vars_)
    assert "Learner's stated prior knowledge" in prompt


async def test_absent_prior_knowledge_prompts_beginner_default(db_engine, db_session):
    """When prior knowledge is absent, the prompt tells the tutor to assume a beginner."""
    ws_id, trail_id, concept_id, _ = await _seed_graph(db_engine)
    ctx, _ = await _make_db_context(db_session, ws_id, trail_id, concept_id, user_turn_index=0)

    vars_ = _context_to_base_prompt_vars(ctx)
    assert vars_["learner_prior_knowledge"] == "none"

    prompt = prompt_registry.render("tutor_base", vars_)
    assert "complete beginner" in prompt
    assert "start from the fundamentals" in prompt


# ---------------------------------------------------------------------------
# Retrieval-loop gating: primer enables the loop on source-less concepts
# ---------------------------------------------------------------------------


class _ToolCapturingLLMClient:
    """Records the tool names offered to each chat_stream_events call.

    Emits no tool calls and empty text so the loop exits immediately and the
    two-phase agent proceeds to its (stubbed) final generation.
    """

    def __init__(self) -> None:
        self.tools_seen: list[list[str]] = []

    async def chat_stream_events(self, messages, tools=None):
        self.tools_seen.append([t.name for t in (tools or [])])
        yield NormalizedStreamEvent.text_delta("")
        yield NormalizedStreamEvent.done_event()


class _GatingTwoPhaseAgent:
    """Minimal two-phase agent that runs the real retrieval-loop gating."""

    def __init__(self, llm_client) -> None:
        self.llm_client = llm_client

    def _prep(self):
        from backend.app.services.tutor import _ModePreparation

        return _ModePreparation(
            mode="socratic",
            messages_after_mode=[
                {"role": "system", "content": "final"},
                {"role": "user", "content": "how do I get started?"},
            ],
            buffered_events=(("mode", "socratic"),),
        )

    async def prepare_mode(self, context):
        return self._prep()

    async def prepare_mode_stream(self, context):
        yield ("__prep__", self._prep())

    async def stream_text(self, context, prep, *, messages=None):
        yield ("text", "A guiding question?")


async def _seed_later_turn_conversation(db_session, ws_id, trail_id, concept_id):
    """Create a conversation with a prior visible exchange (so it is not opening)."""
    conv = Conversation(workspace_id=ws_id, trail_id=trail_id, concept_id=concept_id)
    db_session.add(conv)
    await db_session.flush()
    await _add_visible_turn(db_session, conv.id, role="user", content="hi", turn_index=0)
    await _add_visible_turn(
        db_session, conv.id, role="assistant", content="a question?", turn_index=1
    )
    await db_session.commit()
    return conv


async def test_retrieval_loop_offered_on_sourceless_concept_with_primer(db_engine, db_session):
    """Source-less concept WITH a cached primer: loop runs, primer tool offered,
    source tools withheld, even on a non-opening turn."""
    ws_id, trail_id, concept_id, _ = await _seed_graph(db_engine)
    concept = await db_session.scalar(select(ConceptNode).where(ConceptNode.id == concept_id))
    concept.metadata_json = {"primer": _PRIMER_FIXTURE}
    await db_session.commit()

    conv = await _seed_later_turn_conversation(db_session, ws_id, trail_id, concept_id)

    llm_client = _ToolCapturingLLMClient()
    agent = _GatingTwoPhaseAgent(llm_client)

    async for _ in stream_chat_response(
        db_session,
        agent,
        workspace_id=ws_id,
        trail_id=trail_id,
        concept_id=concept_id,
        message="how do I get started?",
        conversation_id=conv.id,
    ):
        pass

    # The loop ran exactly once and offered the primer tool but no source tools.
    assert llm_client.tools_seen, "retrieval loop should have run"
    offered = llm_client.tools_seen[0]
    assert "get_concept_primer" in offered
    assert "get_graph_neighbourhood" in offered
    assert "search_sources" not in offered
    assert "read_document_section" not in offered
    assert "get_concept_sources" not in offered


async def test_retrieval_loop_skipped_without_sources_or_primer(db_engine, db_session):
    """Source-less concept WITHOUT a primer: the loop is not offered at all."""
    ws_id, trail_id, concept_id, _ = await _seed_graph(db_engine)
    conv = await _seed_later_turn_conversation(db_session, ws_id, trail_id, concept_id)

    llm_client = _ToolCapturingLLMClient()
    agent = _GatingTwoPhaseAgent(llm_client)

    async for _ in stream_chat_response(
        db_session,
        agent,
        workspace_id=ws_id,
        trail_id=trail_id,
        concept_id=concept_id,
        message="how do I get started?",
        conversation_id=conv.id,
    ):
        pass

    # No sources and no primer → retrieval loop never invoked.
    assert llm_client.tools_seen == []
