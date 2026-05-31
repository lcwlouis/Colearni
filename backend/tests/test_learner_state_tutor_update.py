import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.models.base import Base
from backend.app.models.concept import ConceptNode
from backend.app.models.conversation import Conversation, ConversationTurn
from backend.app.models.learner_state import LearnerState
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.schemas.mastery import LearnerStateObservation
from backend.app.services.learner_state import maybe_update_learner_state_from_chat


class FakeLLMClient:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.calls: list[list[dict]] = []

    async def chat(self, messages: list[dict], **_: object) -> str:
        self.calls.append(messages)
        return self.responses.pop(0)


class FakeObserver:
    def __init__(self, observation: LearnerStateObservation | None = None):
        self.observation = observation or LearnerStateObservation()
        self.calls: list[dict[str, str]] = []

    async def observe(
        self, *, concept_title, current_state, recent_turns
    ) -> LearnerStateObservation:
        self.calls.append(
            {
                "concept_title": concept_title,
                "current_state": current_state,
                "recent_turns": recent_turns,
            }
        )
        return self.observation


class RaisingObserver:
    async def observe(self, **_):
        raise RuntimeError("observer must never be reached")


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


async def _seed(session, *, user_turns: int):
    workspace = Workspace(name="LS Workspace")
    session.add(workspace)
    await session.flush()
    trail = Trail(
        workspace_id=workspace.id,
        title="Networks",
        topic="Networking",
        goal="Understand TCP/IP",
        target_depth="understand",
    )
    session.add(trail)
    await session.flush()
    concept = ConceptNode(
        trail_id=trail.id,
        slug="tcp-ip",
        title="TCP/IP Model",
        node_type="concept",
        concept_level="topic",
        difficulty="beginner",
        bloom_level="understand",
        mastery_check_labels=["layers", "protocols"],
        metadata_json={},
    )
    session.add(concept)
    await session.flush()
    conversation = Conversation(
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
    )
    session.add(conversation)
    await session.flush()

    turn_index = 0
    for i in range(user_turns):
        session.add(
            ConversationTurn(
                conversation_id=conversation.id,
                role="user",
                kind="visible",
                content=f"learner message {i}",
                turn_index=turn_index,
            )
        )
        turn_index += 1
        session.add(
            ConversationTurn(
                conversation_id=conversation.id,
                role="assistant",
                kind="visible",
                content=f"tutor reply {i}",
                mode="socratic",
                turn_index=turn_index,
            )
        )
        turn_index += 1
    # A hidden tool turn that must never reach the observer.
    session.add(
        ConversationTurn(
            conversation_id=conversation.id,
            role="tool",
            kind="tool_result",
            content="hidden internal payload",
            turn_index=turn_index,
        )
    )
    await session.flush()
    return workspace, concept, conversation


async def test_observer_not_consulted_off_cadence(session):
    # 3 user turns with interval 4 -> 3 % 4 != 0, so no model call at all.
    _, concept, conversation = await _seed(session, user_turns=3)
    observer = RaisingObserver()

    result = await maybe_update_learner_state_from_chat(
        session,
        observer,
        workspace_id=conversation.workspace_id,
        concept=concept,
        conversation_id=conversation.id,
        interval=4,
        recent_visible_turns_limit=10,
    )

    assert result is None
    assert await session.scalar(select(LearnerState)) is None


async def test_disabled_when_interval_zero(session):
    _, concept, conversation = await _seed(session, user_turns=4)
    observer = RaisingObserver()

    result = await maybe_update_learner_state_from_chat(
        session,
        observer,
        workspace_id=conversation.workspace_id,
        concept=concept,
        conversation_id=conversation.id,
        interval=0,
        recent_visible_turns_limit=10,
    )

    assert result is None


async def test_no_write_when_observer_declines(session):
    _, concept, conversation = await _seed(session, user_turns=4)
    observer = FakeObserver(LearnerStateObservation(should_update=False))

    result = await maybe_update_learner_state_from_chat(
        session,
        observer,
        workspace_id=conversation.workspace_id,
        concept=concept,
        conversation_id=conversation.id,
        interval=4,
        recent_visible_turns_limit=10,
    )

    assert result is None
    assert len(observer.calls) == 1
    # Hidden tool payload never enters the observer context.
    assert "hidden internal payload" not in observer.calls[0]["recent_turns"]
    assert await session.scalar(select(LearnerState)) is None


async def test_creates_learner_state_on_positive_observation(session):
    _, concept, conversation = await _seed(session, user_turns=4)
    observer = FakeObserver(
        LearnerStateObservation(
            should_update=True,
            summary="Learner can name the four TCP/IP layers in order.",
            strengths=["layer ordering"],
            misconceptions=["confuses transport and internet"],
        )
    )

    state = await maybe_update_learner_state_from_chat(
        session,
        observer,
        workspace_id=conversation.workspace_id,
        concept=concept,
        conversation_id=conversation.id,
        interval=4,
        recent_visible_turns_limit=10,
    )

    assert state is not None
    assert state.summary_text == "Learner can name the four TCP/IP layers in order."
    assert [item["mastery_label"] for item in state.strengths_json] == ["layer ordering"]
    # A revealed misconception is also recorded as a repair target.
    assert [item["mastery_label"] for item in state.misconceptions_json] == [
        "confuses transport and internet"
    ]
    assert [item["mastery_label"] for item in state.next_repair_targets_json] == [
        "confuses transport and internet"
    ]
    assert state.last_quiz_attempt_id is None


async def test_resolved_clears_repair_targets_and_preserves_quiz_linkage(session):
    _, concept, conversation = await _seed(session, user_turns=4)
    # Pre-existing quiz-derived state with a repair target.
    session.add(
        LearnerState(
            workspace_id=conversation.workspace_id,
            concept_id=concept.id,
            summary_text="Failed level-up; needs to fix layer ordering.",
            strengths_json=[{"mastery_label": "protocols", "source": "quiz"}],
            misconceptions_json=[{"mastery_label": "layer ordering", "source": "quiz"}],
            next_repair_targets_json=[{"mastery_label": "layer ordering", "source": "quiz"}],
            last_quiz_attempt_id=None,
        )
    )
    await session.flush()
    observer = FakeObserver(
        LearnerStateObservation(
            should_update=True,
            summary="Learner now orders the layers correctly.",
            strengths=["layer ordering"],
            resolved=["layer ordering"],
        )
    )

    state = await maybe_update_learner_state_from_chat(
        session,
        observer,
        workspace_id=conversation.workspace_id,
        concept=concept,
        conversation_id=conversation.id,
        interval=4,
        recent_visible_turns_limit=10,
    )

    assert state is not None
    # The resolved label is removed from misconceptions and repair targets...
    assert state.next_repair_targets_json == []
    assert [item["mastery_label"] for item in state.misconceptions_json] == []
    # ...but it is now a demonstrated strength, merged with the prior quiz strength.
    labels = {item["mastery_label"] for item in state.strengths_json}
    assert labels == {"protocols", "layer ordering"}
    assert state.summary_text == "Learner now orders the layers correctly."
    # Exactly one LearnerState row (updated in place, not duplicated).
    rows = list(await session.scalars(select(LearnerState)))
    assert len(rows) == 1


async def test_llm_observer_renders_prompt_and_parses(session):
    from backend.app.services.learner_state import LLMLearnerStateObserver

    client = FakeLLMClient(
        [
            '{"should_update": true, "summary": "Knows the layers.", '
            '"strengths": ["layer ordering"], "misconceptions": [], "resolved": []}'
        ]
    )
    observer = LLMLearnerStateObserver(client)

    observation = await observer.observe(
        concept_title="TCP/IP Model",
        current_state="No learner-state record yet for this concept.",
        recent_turns="Learner: I think Application is on top.",
    )

    assert observation.should_update is True
    assert observation.summary == "Knows the layers."
    assert observation.strengths == ["layer ordering"]
    rendered = client.calls[0][0]["content"]
    assert "TCP/IP Model" in rendered
    assert "Application is on top" in rendered


async def test_llm_observer_fails_closed_on_bad_json(session):
    from backend.app.services.learner_state import LLMLearnerStateObserver

    observer = LLMLearnerStateObserver(FakeLLMClient(["not json at all"]))

    observation = await observer.observe(
        concept_title="TCP/IP Model",
        current_state="state",
        recent_turns="turns",
    )

    # A malformed model response must never trigger a write.
    assert observation.should_update is False
