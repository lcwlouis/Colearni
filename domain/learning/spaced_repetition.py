"""SM-2 variant spaced repetition scheduler for flashcard reviews."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

# Interval multipliers per self-rating
_MULTIPLIERS: dict[str, float] = {
    "again": 0.5,
    "hard": 1.0,
    "good": 2.5,
    "easy": 4.0,
}

# Minimum interval in days (floor)
_MIN_INTERVAL_DAYS: float = 0.25  # 6 hours


def compute_next_review(
    *,
    current_interval_days: float,
    self_rating: str,
) -> tuple[float, datetime]:
    """Compute the next review interval and due timestamp.

    Returns (new_interval_days, next_review_at).
    """
    multiplier = _MULTIPLIERS.get(self_rating, 1.0)
    new_interval = max(current_interval_days * multiplier, _MIN_INTERVAL_DAYS)
    next_review_at = datetime.now(tz=timezone.utc) + timedelta(days=new_interval)
    return new_interval, next_review_at


def update_flashcard_schedule(
    session: Session,
    *,
    flashcard_id: int,
    user_id: int,
    self_rating: str,
) -> dict[str, Any]:
    """Update the flashcard progress row with new spaced-repetition schedule.

    Should be called after recording the flashcard rating.
    """
    # Fetch current interval
    row = (
        session.execute(
            text(
                "SELECT interval_days FROM practice_flashcard_progress "
                "WHERE flashcard_id = :flashcard_id AND user_id = :user_id"
            ),
            {"flashcard_id": flashcard_id, "user_id": user_id},
        )
        .mappings()
        .first()
    )
    current_interval = float(row["interval_days"]) if row else 1.0
    new_interval, next_review_at = compute_next_review(
        current_interval_days=current_interval,
        self_rating=self_rating,
    )
    session.execute(
        text(
            "UPDATE practice_flashcard_progress "
            "SET interval_days = :interval, due_at = :due_at, updated_at = now() "
            "WHERE flashcard_id = :flashcard_id AND user_id = :user_id"
        ),
        {
            "interval": new_interval,
            "due_at": next_review_at,
            "flashcard_id": flashcard_id,
            "user_id": user_id,
        },
    )
    return {
        "interval_days": new_interval,
        "due_at": next_review_at.isoformat(),
    }


def get_due_flashcards(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return flashcards due for review, ordered by most overdue first."""
    rows = (
        session.execute(
            text(
                """
                SELECT
                    b.id AS flashcard_id,
                    b.front,
                    b.back,
                    b.hint,
                    c.canonical_name AS concept_name,
                    fp.due_at,
                    fp.interval_days,
                    fp.self_rating AS last_rating
                FROM practice_flashcard_progress fp
                JOIN practice_flashcard_bank b ON b.id = fp.flashcard_id
                JOIN concepts_canon c ON c.id = b.concept_id AND c.workspace_id = b.workspace_id
                WHERE b.workspace_id = :workspace_id
                  AND fp.user_id = :user_id
                  AND fp.due_at IS NOT NULL
                  AND fp.due_at <= now()
                ORDER BY fp.due_at ASC
                LIMIT :limit
                """
            ),
            {"workspace_id": workspace_id, "user_id": user_id, "limit": limit},
        )
        .mappings()
        .all()
    )
    return [
        {
            "flashcard_id": int(r["flashcard_id"]),
            "front": str(r["front"]),
            "back": str(r["back"]),
            "hint": str(r["hint"]) if r["hint"] else None,
            "concept_name": str(r["concept_name"]),
            "due_at": r["due_at"].isoformat() if r["due_at"] else None,
            "interval_days": float(r["interval_days"]),
            "last_rating": str(r["last_rating"]) if r["last_rating"] else None,
        }
        for r in rows
    ]
