"""Concept-activity aggregate surface (AR7.1).

Provides a single read endpoint that returns all study activity for a
concept: practice quizzes, level-up quizzes, and flashcard runs with
aggregate metrics and affordance metadata.

This module does NOT duplicate existing list/detail endpoints — it
composes them into one concept-scoped summary payload.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def get_concept_activity(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    concept_id: int,
) -> dict[str, Any]:
    """Return an aggregate activity summary for a concept.

    Includes:
    - practice_quizzes: list + aggregate metrics
    - level_up_quizzes: list + aggregate metrics
    - flashcard_runs: list + aggregate metrics
    - affordances: what actions are available (retry, open, generate)
    """
    practice = _aggregate_practice_quizzes(
        session, workspace_id=workspace_id, user_id=user_id, concept_id=concept_id,
    )
    level_up = _aggregate_level_up_quizzes(
        session, workspace_id=workspace_id, user_id=user_id, concept_id=concept_id,
    )
    flashcards = _aggregate_flashcard_runs(
        session, workspace_id=workspace_id, user_id=user_id, concept_id=concept_id,
    )

    return {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "concept_id": concept_id,
        "practice_quizzes": practice,
        "level_up_quizzes": level_up,
        "flashcard_runs": flashcards,
        "affordances": _compute_affordances(practice, level_up, flashcards),
    }


def _aggregate_practice_quizzes(
    session: Session, *, workspace_id: int, user_id: int, concept_id: int,
) -> dict[str, Any]:
    """Practice quiz summary with aggregate metrics."""
    rows = (
        session.execute(
            text("""
                SELECT q.id AS quiz_id, q.title,
                       a.score, a.passed, a.graded_at
                FROM practice_quizzes q
                LEFT JOIN LATERAL (
                    SELECT score, passed, graded_at
                    FROM practice_quiz_attempts
                    WHERE quiz_id = q.id
                    ORDER BY id DESC LIMIT 1
                ) a ON true
                WHERE q.workspace_id = :workspace_id
                  AND q.user_id = :user_id
                  AND q.concept_id = :concept_id
                ORDER BY q.id DESC
                LIMIT 10
            """),
            {"workspace_id": workspace_id, "user_id": user_id, "concept_id": concept_id},
        )
        .mappings()
        .all()
    )

    quizzes = []
    scores = []
    for r in rows:
        score = r.get("score")
        if score is not None:
            scores.append(float(score))
        quizzes.append({
            "quiz_id": int(r["quiz_id"]),
            "title": str(r.get("title") or ""),
            "latest_score": float(score) if score is not None else None,
            "passed": bool(r["passed"]) if r.get("passed") is not None else None,
            "graded_at": str(r["graded_at"]) if r.get("graded_at") else None,
            "can_retry": True,
        })

    return {
        "count": len(quizzes),
        "average_score": round(sum(scores) / len(scores), 2) if scores else None,
        "quizzes": quizzes,
    }


def _aggregate_level_up_quizzes(
    session: Session, *, workspace_id: int, user_id: int, concept_id: int,
) -> dict[str, Any]:
    """Level-up quiz summary with aggregate metrics."""
    rows = (
        session.execute(
            text("""
                SELECT q.id AS quiz_id, q.title,
                       a.score, a.passed, a.graded_at,
                       a.critical_misconception
                FROM practice_quizzes q
                LEFT JOIN LATERAL (
                    SELECT score, passed, graded_at, critical_misconception
                    FROM practice_quiz_attempts
                    WHERE quiz_id = q.id
                    ORDER BY id DESC LIMIT 1
                ) a ON true
                WHERE q.workspace_id = :workspace_id
                  AND q.user_id = :user_id
                  AND q.concept_id = :concept_id
                  AND q.quiz_type = 'level_up'
                ORDER BY q.id DESC
                LIMIT 10
            """),
            {"workspace_id": workspace_id, "user_id": user_id, "concept_id": concept_id},
        )
        .mappings()
        .all()
    )

    quizzes = []
    passed_count = 0
    for r in rows:
        passed = r.get("passed")
        if passed:
            passed_count += 1
        quizzes.append({
            "quiz_id": int(r["quiz_id"]),
            "title": str(r.get("title") or ""),
            "latest_score": float(r["score"]) if r.get("score") is not None else None,
            "passed": bool(passed) if passed is not None else None,
            "critical_misconception": str(r["critical_misconception"]) if r.get("critical_misconception") else None,
            "graded_at": str(r["graded_at"]) if r.get("graded_at") else None,
            "can_retry": True,
            "can_promote": bool(passed),
        })

    return {
        "count": len(quizzes),
        "passed_count": passed_count,
        "quizzes": quizzes,
    }


def _aggregate_flashcard_runs(
    session: Session, *, workspace_id: int, user_id: int, concept_id: int,
) -> dict[str, Any]:
    """Flashcard run summary with concept-level aggregation."""
    rows = (
        session.execute(
            text("""
                SELECT r.run_id, r.item_count, r.has_more,
                       r.exhausted_reason, r.created_at
                FROM practice_generation_runs r
                WHERE r.workspace_id = :workspace_id
                  AND r.user_id = :user_id
                  AND r.concept_id = :concept_id
                  AND r.generation_type = 'flashcard'
                ORDER BY r.id DESC
                LIMIT 10
            """),
            {"workspace_id": workspace_id, "user_id": user_id, "concept_id": concept_id},
        )
        .mappings()
        .all()
    )

    total_cards = sum(int(r.get("item_count") or 0) for r in rows)
    runs = [
        {
            "run_id": str(r["run_id"]),
            "item_count": int(r.get("item_count") or 0),
            "has_more": bool(r.get("has_more")),
            "exhausted": bool(r.get("exhausted_reason")),
            "created_at": str(r["created_at"]) if r.get("created_at") else None,
            "can_open": True,
        }
        for r in rows
    ]

    return {
        "count": len(runs),
        "total_cards_generated": total_cards,
        "runs": runs,
    }


def _compute_affordances(
    practice: dict, level_up: dict, flashcards: dict,
) -> dict[str, bool]:
    """Compute what actions are available for this concept."""
    return {
        "can_generate_flashcards": True,
        "can_create_practice_quiz": True,
        "can_create_level_up_quiz": True,
        "has_prior_flashcards": flashcards["count"] > 0,
        "has_prior_practice": practice["count"] > 0,
        "has_prior_level_up": level_up["count"] > 0,
    }


__all__ = ["get_concept_activity"]
