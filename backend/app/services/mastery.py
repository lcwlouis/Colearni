from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.concept import ConceptNode
from backend.app.models.mastery import MasteryRecord, QuizAttempt
from backend.app.schemas.mastery import QuizAnswer, QuizQuestion
from backend.app.schemas.types import QuizType

PASS_THRESHOLD = 0.7
_LEARNING_TRANSITION_STATUSES = frozenset({"not_started", "needs_review"})


@dataclass(frozen=True)
class MasteryState:
    id: uuid.UUID | None
    workspace_id: uuid.UUID
    concept_id: uuid.UUID
    status: str
    bloom_level: str
    score: float
    updated_at: datetime | None


def default_mastery_state(*, workspace_id: uuid.UUID, concept: ConceptNode) -> MasteryState:
    return MasteryState(
        id=None,
        workspace_id=workspace_id,
        concept_id=concept.id,
        status="not_started",
        bloom_level=concept.bloom_level,
        score=0.0,
        updated_at=None,
    )


def default_mastery_state_map(
    *, workspace_id: uuid.UUID, concepts: Iterable[ConceptNode]
) -> dict[uuid.UUID, MasteryState]:
    return {
        concept.id: default_mastery_state(workspace_id=workspace_id, concept=concept)
        for concept in concepts
    }


async def get_mastery_state(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    concept: ConceptNode,
) -> MasteryState:
    record = await session.scalar(
        select(MasteryRecord).where(
            MasteryRecord.workspace_id == workspace_id,
            MasteryRecord.concept_id == concept.id,
        )
    )
    if record is None:
        return default_mastery_state(workspace_id=workspace_id, concept=concept)
    return mastery_state_from_record(record)


async def list_mastery_states(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    concepts: Sequence[ConceptNode],
) -> dict[uuid.UUID, MasteryState]:
    if not concepts:
        return {}

    mastery_by_concept = default_mastery_state_map(workspace_id=workspace_id, concepts=concepts)
    concept_ids = [concept.id for concept in concepts]
    records = list(
        await session.scalars(
            select(MasteryRecord).where(
                MasteryRecord.workspace_id == workspace_id,
                MasteryRecord.concept_id.in_(concept_ids),
            )
        )
    )
    for record in records:
        mastery_by_concept[record.concept_id] = mastery_state_from_record(record)
    return mastery_by_concept


async def mark_learning_from_tutor_turn(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    concept: ConceptNode,
) -> MasteryState:
    current_state = await get_mastery_state(session, workspace_id=workspace_id, concept=concept)
    if current_state.status not in _LEARNING_TRANSITION_STATUSES:
        return current_state

    record = await upsert_mastery_record(
        session,
        workspace_id=workspace_id,
        concept=concept,
        status="learning",
        score=current_state.score,
    )
    return mastery_state_from_record(record)


async def apply_level_up_result(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    concept: ConceptNode,
    score: float,
) -> MasteryState:
    record = await upsert_mastery_record(
        session,
        workspace_id=workspace_id,
        concept=concept,
        status="mastered" if score >= PASS_THRESHOLD else "needs_review",
        score=score,
    )
    return mastery_state_from_record(record)


async def upsert_mastery_record(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    concept: ConceptNode,
    status: str,
    score: float | None = None,
) -> MasteryRecord:
    record = await session.scalar(
        select(MasteryRecord).where(
            MasteryRecord.workspace_id == workspace_id,
            MasteryRecord.concept_id == concept.id,
        )
    )
    now = datetime.now(UTC)

    if record is None:
        record = MasteryRecord(
            workspace_id=workspace_id,
            concept_id=concept.id,
            status=status,
            bloom_level=concept.bloom_level,
            score=score if score is not None else 0.0,
            updated_at=now,
        )
        session.add(record)
    else:
        record.status = status
        record.bloom_level = concept.bloom_level
        if score is not None:
            record.score = score
        record.updated_at = now

    await session.flush()
    return record


async def store_quiz_attempt(
    session: AsyncSession,
    *,
    concept_id: uuid.UUID,
    quiz_type: QuizType,
    questions: list[QuizQuestion],
    answers: list[QuizAnswer],
    evaluator_feedback: str,
    passed: bool,
    score: float,
) -> QuizAttempt:
    attempt = QuizAttempt(
        concept_id=concept_id,
        quiz_type=quiz_type,
        questions_json=[question.model_dump(mode="json") for question in questions],
        answers_json=[answer.model_dump(mode="json") for answer in answers],
        evaluator_feedback=evaluator_feedback.strip(),
        passed=passed,
        score=score,
    )
    session.add(attempt)
    await session.flush()
    return attempt


def mastery_state_from_record(record: MasteryRecord) -> MasteryState:
    return MasteryState(
        id=record.id,
        workspace_id=record.workspace_id,
        concept_id=record.concept_id,
        status=record.status,
        bloom_level=record.bloom_level,
        score=record.score,
        updated_at=record.updated_at,
    )
