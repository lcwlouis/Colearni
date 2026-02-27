"""Readiness analyzer – computes half-life decay on per-topic mastery.

Runs as a periodic job (see apps/jobs/readiness_analyzer.py).
For each (workspace, user, concept) triple:
  1. Loads the latest mastery score from the `mastery` table.
  2. Computes time elapsed since last quiz/practice submission.
  3. Applies exponential decay: readiness = mastery_score * 2^(-t / half_life).
  4. Sets `recommend_quiz = True` when readiness drops below a threshold.
  5. Upserts into `user_topic_state`.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

DEFAULT_HALF_LIFE_DAYS = 7.0
RECOMMEND_THRESHOLD = 0.5

# Cadence thresholds (hours since last activity)
ACTIVE_CADENCE_HOURS = 24          # nightly if active
IDLE_CADENCE_HOURS = 72            # every 3 days if idle 1-7d
IDLE_BOUNDARY_DAYS = 1.0
PAUSED_BOUNDARY_DAYS = 7.0


def determine_cadence(hours_since_last_activity: float) -> str:
    """Return the readiness refresh cadence for this user.

    Returns one of: "active", "idle", "paused".
    """
    days = hours_since_last_activity / 24.0
    if days < IDLE_BOUNDARY_DAYS:
        return "active"
    if days < PAUSED_BOUNDARY_DAYS:
        return "idle"
    return "paused"


def should_run_readiness(hours_since_last_run: float | None, cadence: str) -> bool:
    """Return True if enough time has elapsed for this cadence tier."""
    if hours_since_last_run is None:
        return True  # never run before
    if cadence == "active":
        return hours_since_last_run >= ACTIVE_CADENCE_HOURS
    if cadence == "idle":
        return hours_since_last_run >= IDLE_CADENCE_HOURS
    return False  # "paused" — skip


def analyze_workspace_readiness(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
    recommend_threshold: float = RECOMMEND_THRESHOLD,
) -> list[dict[str, object]]:
    """Recompute readiness scores for all concepts a user has mastery on."""
    rows = (
        session.execute(
            text(
                """
                SELECT
                    m.concept_id,
                    m.mastery_score,
                    m.updated_at AS last_activity
                FROM mastery m
                WHERE m.workspace_id = :workspace_id
                  AND m.user_id = :user_id
                """
            ),
            {"workspace_id": workspace_id, "user_id": user_id},
        )
        .mappings()
        .all()
    )

    now = datetime.now(tz=UTC)
    results: list[dict[str, object]] = []

    for row in rows:
        concept_id = int(row["concept_id"])
        mastery_score = float(row["mastery_score"])
        last_activity: datetime = row["last_activity"]

        elapsed_days = max(0.0, (now - last_activity).total_seconds() / 86400.0)
        readiness = mastery_score * math.pow(2, -elapsed_days / half_life_days)
        readiness = max(0.0, min(1.0, readiness))
        recommend = readiness < recommend_threshold and mastery_score >= 0.3

        session.execute(
            text(
                """
                INSERT INTO user_topic_state
                    (workspace_id, user_id, concept_id, readiness_score,
                     recommend_quiz, last_assessed_at, updated_at)
                VALUES
                    (:workspace_id, :user_id, :concept_id, :readiness_score,
                     :recommend_quiz, now(), now())
                ON CONFLICT (workspace_id, user_id, concept_id)
                DO UPDATE SET
                    readiness_score = EXCLUDED.readiness_score,
                    recommend_quiz = EXCLUDED.recommend_quiz,
                    last_assessed_at = now(),
                    updated_at = now()
                """
            ),
            {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "concept_id": concept_id,
                "readiness_score": round(readiness, 4),
                "recommend_quiz": recommend,
            },
        )
        results.append(
            {
                "concept_id": concept_id,
                "mastery_score": mastery_score,
                "readiness_score": round(readiness, 4),
                "recommend_quiz": recommend,
            }
        )

    if results:
        session.commit()

    return results


def build_readiness_actions(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    limit: int = 3,
) -> list[dict[str, object]]:
    """Return CTA actions for topics that need review."""
    rows = (
        session.execute(
            text(
                """
                SELECT
                    uts.concept_id,
                    cc.canonical_name AS concept_name,
                    uts.readiness_score
                FROM user_topic_state uts
                JOIN concepts_canon cc ON cc.id = uts.concept_id
                WHERE uts.workspace_id = :workspace_id
                  AND uts.user_id = :user_id
                  AND uts.recommend_quiz = TRUE
                ORDER BY uts.readiness_score ASC
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
            "action_type": "quiz_cta",
            "label": f"Review: {row['concept_name']} (readiness {int(float(row['readiness_score']) * 100)}%)",
            "concept_id": int(row["concept_id"]),
            "concept_name": str(row["concept_name"]),
        }
        for row in rows
    ]


__all__ = [
    "analyze_workspace_readiness",
    "build_readiness_actions",
    "determine_cadence",
    "should_run_readiness",
]
