import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.models.base import Base
from backend.app.models.concept import ConceptNode
from backend.app.models.conversation import Conversation, ConversationSummary, ConversationTurn
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.services.conversation_summaries import (
    delete_stale_conversation_summaries,
    maybe_generate_conversation_summary,
)


class FakeSummarizer:
    def __init__(self, text: str = "LLM summary"):
        self.text = text
        self.calls: list[dict[str, str]] = []

    async def summarize(self, *, previous_summary: str, new_turns: str) -> str:
        self.calls.append({"previous_summary": previous_summary, "new_turns": new_turns})
        return self.text


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


async def _seed_conversation(session):
    workspace = Workspace(name="Summary Workspace")
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
    return conversation


async def test_llm_summary_covers_old_visible_turns_and_excludes_tool_turns(session):
    conversation = await _seed_conversation(session)
    turns = [
        ConversationTurn(
            conversation_id=conversation.id,
            role="user",
            kind="visible",
            content="What are the TCP/IP layers?",
            turn_index=0,
        ),
        ConversationTurn(
            conversation_id=conversation.id,
            role="assistant",
            kind="visible",
            content="The model has Application, Transport, Internet, and Network Access.",
            mode="direct",
            turn_index=1,
        ),
        ConversationTurn(
            conversation_id=conversation.id,
            role="tool",
            kind="tool_result",
            content="hidden internal tool payload",
            turn_index=2,
        ),
        ConversationTurn(
            conversation_id=conversation.id,
            role="user",
            kind="visible",
            content="I keep reversing the order.",
            turn_index=3,
        ),
        ConversationTurn(
            conversation_id=conversation.id,
            role="assistant",
            kind="visible",
            content="Remember the top starts near the user: Application first.",
            mode="repair",
            turn_index=4,
        ),
        ConversationTurn(
            conversation_id=conversation.id,
            role="user",
            kind="visible",
            content="Okay, quiz me later.",
            turn_index=5,
        ),
    ]
    session.add_all(turns)
    await session.flush()
    summarizer = FakeSummarizer()

    summary = await maybe_generate_conversation_summary(
        session,
        summarizer,
        conversation_id=conversation.id,
        through_turn_index=5,
        recent_visible_turns_limit=2,
        history_char_budget=0,  # always trigger for test
        batch_size=1,
    )

    assert summary is not None
    assert summary.summary_text == "LLM summary"
    assert summary.turns_covered_to == 3
    assert len(summarizer.calls) == 1
    prompt_turns = summarizer.calls[0]["new_turns"]
    assert "TCP/IP layers" in prompt_turns
    assert "I keep reversing" in prompt_turns
    assert "hidden internal tool payload" not in prompt_turns


async def test_summary_generation_is_idempotent_for_same_cutoff(session):
    conversation = await _seed_conversation(session)
    for index in range(5):
        session.add(
            ConversationTurn(
                conversation_id=conversation.id,
                role="user" if index % 2 == 0 else "assistant",
                kind="visible",
                content=f"visible {index}",
                mode=None if index % 2 == 0 else "socratic",
                turn_index=index,
            )
        )
    await session.flush()
    summarizer = FakeSummarizer()

    first = await maybe_generate_conversation_summary(
        session,
        summarizer,
        conversation_id=conversation.id,
        through_turn_index=4,
        recent_visible_turns_limit=2,
        history_char_budget=0,
        batch_size=1,
    )
    second = await maybe_generate_conversation_summary(
        session,
        summarizer,
        conversation_id=conversation.id,
        through_turn_index=4,
        recent_visible_turns_limit=2,
        history_char_budget=0,
        batch_size=1,
    )

    assert first is not None
    assert second is not None
    assert first.id == second.id
    assert len(summarizer.calls) == 1


async def test_no_summary_when_history_fits_char_budget(session):
    conversation = await _seed_conversation(session)
    content = "x" * 100  # small content well under any real budget
    for index in range(8):
        session.add(
            ConversationTurn(
                conversation_id=conversation.id,
                role="user" if index % 2 == 0 else "assistant",
                kind="visible",
                content=content,
                mode=None if index % 2 == 0 else "socratic",
                turn_index=index,
            )
        )
    await session.flush()
    summarizer = FakeSummarizer()

    result = await maybe_generate_conversation_summary(
        session,
        summarizer,
        conversation_id=conversation.id,
        through_turn_index=7,
        recent_visible_turns_limit=2,
        history_char_budget=10_000,  # total ~800 chars — well under budget
        batch_size=1,
    )

    assert result is None
    assert len(summarizer.calls) == 0


async def test_no_summary_when_batch_floor_not_met(session):
    conversation = await _seed_conversation(session)
    content = "x" * 5_000  # big enough to exceed budget with a few turns
    for index in range(5):
        session.add(
            ConversationTurn(
                conversation_id=conversation.id,
                role="user" if index % 2 == 0 else "assistant",
                kind="visible",
                content=content,
                mode=None if index % 2 == 0 else "socratic",
                turn_index=index,
            )
        )
    await session.flush()
    summarizer = FakeSummarizer()

    # Budget exceeded (5 × 5000 = 25 000 > 10 000), but only 2 turns fall
    # outside the verbatim window (5 total − 3 recent = 2), which is below
    # the batch floor of 5.
    result = await maybe_generate_conversation_summary(
        session,
        summarizer,
        conversation_id=conversation.id,
        through_turn_index=4,
        recent_visible_turns_limit=3,
        history_char_budget=10_000,
        batch_size=5,
    )

    assert result is None
    assert len(summarizer.calls) == 0


async def test_stale_summaries_are_deleted_after_edit(session):
    conversation = await _seed_conversation(session)
    session.add_all(
        [
            ConversationSummary(
                conversation_id=conversation.id,
                turns_covered_to=1,
                summary_text="safe summary",
            ),
            ConversationSummary(
                conversation_id=conversation.id,
                turns_covered_to=4,
                summary_text="stale summary",
            ),
        ]
    )
    await session.flush()

    await delete_stale_conversation_summaries(
        session,
        conversation_id=conversation.id,
        from_turn_index=3,
    )

    rows = list(
        await session.scalars(
            select(ConversationSummary).order_by(ConversationSummary.turns_covered_to.asc())
        )
    )
    assert [row.summary_text for row in rows] == ["safe summary"]
