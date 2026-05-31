from __future__ import annotations

import uuid
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.concept import ConceptNode
from backend.app.models.mastery import MasteryRecord, QuizAttempt
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.schemas.types import QuizType
from backend.app.schemas.workspace import (
    ConceptMasteryItem,
    MasterySummary,
    TrailProgressItem,
    WorkspaceProgressResponse,
    WorkspaceQuizAttemptItem,
)


async def list_workspace_quiz_attempts(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
) -> list[WorkspaceQuizAttemptItem]:
    """Return up to 200 quiz attempts scoped to a workspace, newest first."""
    if await session.get(Workspace, workspace_id) is None:
        raise LookupError(f"Workspace {workspace_id} not found")

    stmt = (
        select(
            QuizAttempt,
            ConceptNode.title.label("concept_title"),
            Trail.id.label("trail_id"),
            Trail.title.label("trail_title"),
        )
        .join(ConceptNode, QuizAttempt.concept_id == ConceptNode.id)
        .join(Trail, ConceptNode.trail_id == Trail.id)
        .where(Trail.workspace_id == workspace_id)
        .order_by(QuizAttempt.created_at.desc())
        .limit(200)
    )
    rows = list(await session.execute(stmt))
    return [
        WorkspaceQuizAttemptItem(
            id=attempt.id,
            concept_id=attempt.concept_id,
            concept_title=concept_title,
            trail_id=trail_id,
            trail_title=trail_title,
            quiz_type=cast(QuizType, attempt.quiz_type),
            passed=attempt.passed,
            score=attempt.score,
            evaluator_feedback=attempt.evaluator_feedback,
            created_at=attempt.created_at,
        )
        for attempt, concept_title, trail_id, trail_title in rows
    ]


async def get_workspace_progress(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
) -> WorkspaceProgressResponse:
    """Return per-trail mastery aggregation for a workspace."""
    if await session.get(Workspace, workspace_id) is None:
        raise LookupError(f"Workspace {workspace_id} not found")

    trails_stmt = (
        select(Trail)
        .where(Trail.workspace_id == workspace_id)
        .order_by(Trail.created_at)
    )
    trails = list(await session.scalars(trails_stmt))

    trail_items: list[TrailProgressItem] = []
    for trail in trails:
        concepts_stmt = select(ConceptNode).where(ConceptNode.trail_id == trail.id)
        concepts = list(await session.scalars(concepts_stmt))

        if not concepts:
            trail_items.append(
                TrailProgressItem(
                    trail_id=trail.id,
                    trail_title=trail.title,
                    mastery_summary=MasterySummary(
                        total=0, not_started=0, learning=0, needs_review=0, mastered=0
                    ),
                    concepts=[],
                )
            )
            continue

        concept_ids = [c.id for c in concepts]
        mastery_stmt = select(MasteryRecord).where(
            MasteryRecord.workspace_id == workspace_id,
            MasteryRecord.concept_id.in_(concept_ids),
        )
        mastery_records = list(await session.scalars(mastery_stmt))
        mastery_map = {r.concept_id: r for r in mastery_records}

        concept_items: list[ConceptMasteryItem] = []
        counts: dict[str, int] = {"not_started": 0, "learning": 0, "needs_review": 0, "mastered": 0}

        for concept in concepts:
            record = mastery_map.get(concept.id)
            if record is not None:
                status = record.status
                score = record.score
                bloom_level = record.bloom_level
            else:
                status = "not_started"
                score = 0.0
                bloom_level = concept.bloom_level
            counts[status] += 1
            concept_items.append(
                ConceptMasteryItem(
                    concept_id=concept.id,
                    concept_title=concept.title,
                    status=cast(str, status),  # type: ignore[arg-type]
                    score=score,
                    bloom_level=cast(str, bloom_level),  # type: ignore[arg-type]
                )
            )

        trail_items.append(
            TrailProgressItem(
                trail_id=trail.id,
                trail_title=trail.title,
                mastery_summary=MasterySummary(
                    total=len(concepts),
                    not_started=counts["not_started"],
                    learning=counts["learning"],
                    needs_review=counts["needs_review"],
                    mastered=counts["mastered"],
                ),
                concepts=concept_items,
            )
        )

    return WorkspaceProgressResponse(trails=trail_items)
