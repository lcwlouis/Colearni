"""Level-up quiz module — backward-compatible wrapper over shared quiz core.

The actual create/submit logic now lives in :mod:`domain.learning.quiz_flow`.
This module re-exports the shared functions and error classes under their
original ``LevelUp``-prefixed names so existing callers keep working.
"""

from __future__ import annotations

from typing import Any

from domain.learning.quiz_flow import (  # noqa: F401
    QuizGradingError as LevelUpQuizGradingError,
    QuizNotFoundError as LevelUpQuizNotFoundError,
    QuizUnavailableError as LevelUpQuizUnavailableError,
    QuizValidationError as LevelUpQuizValidationError,
    create_quiz as create_level_up_quiz,
    submit_quiz as submit_level_up_quiz,
)
from domain.learning.quiz_persistence import (  # noqa: F401
    get_latest_quiz_summary_for_concept,
)
from sqlalchemy import text
from sqlalchemy.orm import Session

MIN_ITEMS = 5
MAX_ITEMS = 12
RETRY_HINT = "create a new level-up quiz to retry"


def get_mastered_neighbor_context(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    concept_id: int,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Return top-K mastered neighboring concepts by edge weight.

    Used to enrich quiz generation context with surrounding mastered knowledge.
    """
    rows = (
        session.execute(
            text(
                """
                SELECT c.canonical_name, c.description, m.score AS mastery_score, e.weight
                FROM edges_canon e
                JOIN concepts_canon c
                  ON c.workspace_id = e.workspace_id
                 AND c.is_active = TRUE
                 AND c.id = CASE WHEN e.src_id = :concept_id THEN e.tgt_id ELSE e.src_id END
                JOIN mastery m
                  ON m.workspace_id = e.workspace_id
                 AND m.user_id = :user_id
                 AND m.concept_id = c.id
                 AND m.status = 'learned'
                WHERE e.workspace_id = :workspace_id
                  AND (e.src_id = :concept_id OR e.tgt_id = :concept_id)
                ORDER BY e.weight DESC, c.canonical_name ASC
                LIMIT :top_k
                """
            ),
            {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "concept_id": concept_id,
                "top_k": top_k,
            },
        )
        .mappings()
        .all()
    )
    return [
        {
            "name": str(r["canonical_name"]),
            "description": str(r["description"] or "")[:150],
            "mastery_score": float(r["mastery_score"]) if r["mastery_score"] is not None else None,
        }
        for r in rows
    ]


__all__ = [
    "LevelUpQuizGradingError",
    "LevelUpQuizNotFoundError",
    "LevelUpQuizUnavailableError",
    "LevelUpQuizValidationError",
    "create_level_up_quiz",
    "get_latest_quiz_summary_for_concept",
    "submit_level_up_quiz",
]
