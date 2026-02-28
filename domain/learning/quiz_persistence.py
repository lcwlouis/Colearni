"""Shared quiz persistence helpers.

DB-level quiz reads that are used across quiz flows (level-up, practice,
and chat context enrichment).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_latest_quiz_summary_for_concept(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    concept_id: int,
) -> dict[str, Any] | None:
    """Return a summary of the latest quiz attempt for a given concept.

    Used by the tutor prompt to include recent quiz context in conversation.
    Returns None if no quiz has been attempted for this concept.
    """
    row = (
        session.execute(
            text(
                """
                SELECT q.id AS quiz_id,
                       q.status AS quiz_status,
                       qa.score,
                       qa.passed,
                       qa.graded_at,
                       qa.grading
                FROM quizzes q
                LEFT JOIN quiz_attempts qa
                  ON qa.quiz_id = q.id
                 AND qa.user_id = :user_id
                 AND qa.graded_at IS NOT NULL
                WHERE q.workspace_id = :workspace_id
                  AND q.user_id = :user_id
                  AND q.concept_id = :concept_id
                ORDER BY q.id DESC
                LIMIT 1
                """
            ),
            {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "concept_id": concept_id,
            },
        )
        .mappings()
        .first()
    )
    if row is None:
        return None

    grading = row["grading"] if isinstance(row["grading"], dict) else {}
    return {
        "quiz_id": int(row["quiz_id"]),
        "quiz_status": str(row["quiz_status"]),
        "score": float(row["score"]) if row["score"] is not None else None,
        "passed": bool(row["passed"]) if row["passed"] is not None else None,
        "overall_feedback": str(grading.get("overall_feedback", "")).strip()[:200],
        "attempted": row["graded_at"] is not None,
    }
