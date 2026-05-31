import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.models.base import Base
from backend.app.models.concept import ConceptNode
from backend.app.models.conversation import Conversation, ConversationTurn
from backend.app.models.learner_state import LearnerState
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.services.tutor_followups import TutorFollowupManager, run_tutor_followups


class FakeLLMClient:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.calls: list[list[dict]] = []

    async def chat(self, messages: list[dict], **_: object) -> str:
        self.calls.append(messages)
        return self.responses.pop(0)


@pytest.fixture
async def session_factory(tmp_path):
    # File-backed SQLite so the detached follow-up opens its OWN connection,
    # mirroring how the production background task uses a separate pool
    # connection from the request.
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'followups.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


async def _seed(maker, *, user_turns: int):
    async with maker() as session:
        workspace = Workspace(name="Followup Workspace")
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
            mastery_check_labels=["layers"],
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
        await session.commit()
        return workspace.id, concept.id, conversation.id, turn_index - 1


async def test_run_followups_updates_learner_state_in_own_session(session_factory):
    # 4 user turns -> default interval 4 fires; small history stays under the
    # summary budget so only the learner-state observer calls the model.
    ws_id, concept_id, conv_id, through = await _seed(session_factory, user_turns=4)
    client = FakeLLMClient(
        [
            '{"should_update": true, "summary": "Knows the layers.", '
            '"strengths": ["layer ordering"], "misconceptions": [], "resolved": []}'
        ]
    )

    await run_tutor_followups(
        session_factory,
        client,
        workspace_id=ws_id,
        concept_id=concept_id,
        conversation_id=conv_id,
        through_turn_index=through,
    )

    # The follow-up persisted via its OWN session; a fresh session sees it.
    async with session_factory() as session:
        state = await session.scalar(select(LearnerState))
    assert state is not None
    assert state.summary_text == "Knows the layers."
    assert len(client.calls) == 1  # summary skipped (under budget); observer ran once


async def test_manager_schedule_and_drain_persists(session_factory):
    ws_id, concept_id, conv_id, through = await _seed(session_factory, user_turns=4)
    client = FakeLLMClient(
        [
            '{"should_update": true, "summary": "Solid.", '
            '"strengths": ["layers"], "misconceptions": [], "resolved": []}'
        ]
    )
    manager = TutorFollowupManager()

    manager.schedule(
        session_factory,
        client,
        workspace_id=ws_id,
        concept_id=concept_id,
        conversation_id=conv_id,
        through_turn_index=through,
    )
    await manager.drain()

    async with session_factory() as session:
        state = await session.scalar(select(LearnerState))
    assert state is not None
    assert state.summary_text == "Solid."


async def test_followups_swallow_errors(session_factory):
    # A client that raises must not propagate out of the detached runner.
    ws_id, concept_id, conv_id, through = await _seed(session_factory, user_turns=4)

    class RaisingClient:
        async def chat(self, *_a, **_k):
            raise RuntimeError("model down")

    # Should complete without raising; nothing is written.
    await run_tutor_followups(
        session_factory,
        RaisingClient(),
        workspace_id=ws_id,
        concept_id=concept_id,
        conversation_id=conv_id,
        through_turn_index=through,
    )

    async with session_factory() as session:
        assert await session.scalar(select(LearnerState)) is None
