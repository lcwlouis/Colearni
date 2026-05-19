import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.models.base import Base
from backend.app.models.concept import ConceptNode
from backend.app.models.mastery import MasteryRecord, QuizAttempt
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.schemas.mastery import QuizAnswer, QuizQuestion
from backend.app.services.mastery import (
    get_mastery_state,
    mark_learning_from_tutor_turn,
    store_quiz_attempt,
    upsert_mastery_record,
)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


async def _seed_concept(session):
    workspace = Workspace(name="Mastery Workspace")
    session.add(workspace)
    await session.flush()
    trail = Trail(
        workspace_id=workspace.id,
        title="Calculus",
        topic="Calculus",
        goal="Understand derivatives",
        target_depth="apply",
    )
    session.add(trail)
    await session.flush()
    concept = ConceptNode(
        trail_id=trail.id,
        slug="derivatives",
        title="Derivatives",
        node_type="concept",
        concept_level="topic",
        difficulty="beginner",
        bloom_level="apply",
        mastery_check_labels=["explain_derivative", "apply_derivative"],
        metadata_json={},
    )
    session.add(concept)
    await session.commit()
    return workspace, trail, concept


async def test_get_mastery_state_defaults_to_not_started(session):
    workspace, _, concept = await _seed_concept(session)

    state = await get_mastery_state(session, workspace_id=workspace.id, concept=concept)

    assert state.id is None
    assert state.status == "not_started"
    assert state.score == 0.0


async def test_upsert_mastery_record_creates_then_updates(session):
    workspace, _, concept = await _seed_concept(session)

    created = await upsert_mastery_record(
        session,
        workspace_id=workspace.id,
        concept=concept,
        status="learning",
        score=0.4,
    )
    await session.commit()

    updated = await upsert_mastery_record(
        session,
        workspace_id=workspace.id,
        concept=concept,
        status="mastered",
        score=0.9,
    )
    await session.commit()

    assert created.id == updated.id
    row = await session.scalar(select(MasteryRecord).where(MasteryRecord.id == updated.id))
    assert row is not None
    assert row.status == "mastered"
    assert row.score == pytest.approx(0.9)


async def test_mark_learning_from_tutor_turn_creates_learning_record(session):
    workspace, _, concept = await _seed_concept(session)

    state = await mark_learning_from_tutor_turn(session, workspace_id=workspace.id, concept=concept)
    await session.commit()

    assert state.status == "learning"
    record = await session.scalar(
        select(MasteryRecord).where(MasteryRecord.workspace_id == workspace.id)
    )
    assert record is not None
    assert record.status == "learning"


async def test_mark_learning_from_tutor_turn_resets_needs_review_to_learning(session):
    workspace, _, concept = await _seed_concept(session)
    await upsert_mastery_record(
        session,
        workspace_id=workspace.id,
        concept=concept,
        status="needs_review",
        score=0.55,
    )
    await session.commit()

    state = await mark_learning_from_tutor_turn(session, workspace_id=workspace.id, concept=concept)
    await session.commit()

    assert state.status == "learning"
    assert state.score == pytest.approx(0.55)


async def test_store_quiz_attempt_persists_snapshot_and_answers(session):
    _, _, concept = await _seed_concept(session)
    questions = [
        QuizQuestion(
            id="q1",
            type="explain",
            prompt="Explain it",
            mastery_label="explain_derivative",
        )
    ]
    answers = [QuizAnswer(question_id="q1", answer="A derivative is a rate of change.")]

    attempt = await store_quiz_attempt(
        session,
        concept_id=concept.id,
        quiz_type="practice",
        questions=questions,
        answers=answers,
        evaluator_feedback="Solid start.",
        passed=True,
        score=0.8,
    )
    await session.commit()

    row = await session.scalar(select(QuizAttempt).where(QuizAttempt.id == attempt.id))
    assert row is not None
    assert row.quiz_type == "practice"
    assert row.questions_json == [question.model_dump(mode="json") for question in questions]
    assert row.answers_json == [answer.model_dump(mode="json") for answer in answers]
    assert row.evaluator_feedback == "Solid start."
    assert row.passed is True
    assert row.score == pytest.approx(0.8)
