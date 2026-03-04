"""Level-up quiz module — backward-compatible wrapper over shared quiz core.

The actual create/submit logic now lives in :mod:`domain.learning.quiz_flow`.
This module re-exports the shared functions and error classes under their
original ``LevelUp``-prefixed names so existing callers keep working.
"""

from __future__ import annotations

from typing import Any

from domain.learning.quiz_flow import (  # noqa: F401
    QuizGradingError as LevelUpQuizGradingError,
)
from domain.learning.quiz_flow import (
    QuizNotFoundError as LevelUpQuizNotFoundError,
)
from domain.learning.quiz_flow import (
    QuizUnavailableError as LevelUpQuizUnavailableError,
)
from domain.learning.quiz_flow import (
    QuizValidationError as LevelUpQuizValidationError,
)
from domain.learning.quiz_flow import (
    create_quiz as create_level_up_quiz,
)
from domain.learning.quiz_flow import (
    submit_quiz as submit_level_up_quiz,
)
from domain.learning.quiz_flow import create_quiz as _create_quiz
from domain.learning.quiz_persistence import (  # noqa: F401
    get_latest_quiz_summary_for_concept,
)
from domain.learning.quiz_persistence import (
    list_quizzes_with_latest_attempt as _list_quizzes_with_latest_attempt,
)
from domain.learning.quiz_persistence import (
    load_quiz_items as _load_quiz_items,
)
from domain.learning.quiz_persistence import (
    load_quiz_with_latest_attempt as _load_quiz_with_latest_attempt,
)

MIN_ITEMS = 5
MAX_ITEMS = 12
RETRY_HINT = "create a new level-up quiz to retry"


def list_level_up_quizzes(
    session,
    *,
    workspace_id: int,
    user_id: int,
    concept_id: int | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    rows = _list_quizzes_with_latest_attempt(
        session,
        workspace_id=workspace_id,
        user_id=user_id,
        quiz_type="level_up",
        concept_id=concept_id,
        limit=limit,
    )
    return {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "concept_id": concept_id,
        "quizzes": [_serialize_level_up_history_row(row) for row in rows],
    }


def get_level_up_quiz(
    session,
    *,
    quiz_id: int,
    workspace_id: int,
    user_id: int,
) -> dict[str, Any]:
    row = _load_quiz_with_latest_attempt(
        session,
        workspace_id=workspace_id,
        user_id=user_id,
        quiz_id=quiz_id,
        quiz_type="level_up",
    )
    if row is None:
        raise LevelUpQuizNotFoundError("Level-up quiz not found.")

    payload = _serialize_level_up_history_row(row)
    items = _load_quiz_items(session, quiz_id=quiz_id)
    payload["items"] = [
        {
            "item_id": int(item["item_id"]),
            "position": int(item["position"]),
            "item_type": str(item["item_type"]),
            "prompt": str(item["prompt"]),
            "choices": [
                {"id": str(choice.get("id", "")), "text": str(choice.get("text", ""))}
                for choice in (
                    item["payload"].get("choices", [])
                    if isinstance(item.get("payload"), dict)
                    else []
                )
                if isinstance(choice, dict)
                and str(choice.get("id", "")).strip()
                and str(choice.get("text", "")).strip()
            ]
            or None,
        }
        for item in items
    ]
    return payload


def promote_level_up_quiz_to_practice(
    session,
    *,
    quiz_id: int,
    workspace_id: int,
    user_id: int,
) -> dict[str, Any]:
    source = _load_quiz_with_latest_attempt(
        session,
        workspace_id=workspace_id,
        user_id=user_id,
        quiz_id=quiz_id,
        quiz_type="level_up",
    )
    if source is None:
        raise LevelUpQuizNotFoundError("Level-up quiz not found.")
    if source.get("concept_id") is None:
        raise LevelUpQuizValidationError("Level-up quiz has no concept and cannot be promoted.")

    item_rows = _load_quiz_items(session, quiz_id=quiz_id)
    if not item_rows:
        raise LevelUpQuizValidationError("Level-up quiz has no items to promote.")
    promoted_items = [
        {
            "item_type": str(item["item_type"]),
            "prompt": str(item["prompt"]),
            "payload": item["payload"] if isinstance(item["payload"], dict) else {},
        }
        for item in item_rows
    ]
    practice_quiz = _create_quiz(
        session,
        workspace_id=workspace_id,
        user_id=user_id,
        concept_id=int(source["concept_id"]),
        session_id=None,
        question_count=len(promoted_items),
        items=promoted_items,
        llm_client=None,
        quiz_type="practice",
        min_items=1,
        max_items=max(12, len(promoted_items)),
        context_source="provided",
    )
    return {
        "source_quiz_id": quiz_id,
        "practice_quiz": practice_quiz,
    }


def _serialize_level_up_history_row(row: Any) -> dict[str, Any]:
    grading = row["grading"] if isinstance(row.get("grading"), dict) else {}
    latest_attempt = None
    if row.get("attempt_id") is not None and row.get("graded_at") is not None:
        latest_attempt = {
            "attempt_id": int(row["attempt_id"]),
            "score": float(row["score"] or 0.0),
            "passed": bool(row["passed"]),
            "critical_misconception": bool(grading.get("critical_misconception", False)),
            "overall_feedback": str(grading.get("overall_feedback", "")).strip() or "(no feedback)",
            "graded_at": row["graded_at"],
        }
    return {
        "quiz_id": int(row["quiz_id"]),
        "workspace_id": int(row["workspace_id"]),
        "user_id": int(row["user_id"]),
        "concept_id": int(row["concept_id"]) if row.get("concept_id") is not None else None,
        "concept_name": str(row["concept_name"]) if row.get("concept_name") else None,
        "status": str(row["status"]),
        "item_count": int(row.get("item_count") or 0),
        "created_at": row["created_at"],
        "latest_attempt": latest_attempt,
    }


__all__ = [
    "LevelUpQuizGradingError",
    "LevelUpQuizNotFoundError",
    "LevelUpQuizUnavailableError",
    "LevelUpQuizValidationError",
    "create_level_up_quiz",
    "get_latest_quiz_summary_for_concept",
    "get_level_up_quiz",
    "list_level_up_quizzes",
    "promote_level_up_quiz_to_practice",
    "submit_level_up_quiz",
]
