"""Learner digest background jobs (AR6.1).

Recommendation-first jobs that produce structured summaries, frontier
suggestions, and deep-review packs from existing learner data.

Outputs are stored in the ``learner_digests`` table as JSONB payloads.
No direct user messaging; no autonomous web research.

Usage:
    python -m apps.jobs.learner_digest
"""

from __future__ import annotations

import json
import logging
from typing import Any

from adapters.db.engine import create_db_engine
from core.settings import get_settings
from domain.learner.assembler import assemble_learner_snapshot
from domain.learner.profile import LearnerProfileSnapshot
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

MAX_USERS_PER_RUN = 50
DIGEST_TYPES = ("learner_summary", "frontier_suggestions", "deep_review")


# ---------------------------------------------------------------------------
# Pure generators — take a snapshot, return structured dicts
# ---------------------------------------------------------------------------


def generate_learner_summary(snapshot: LearnerProfileSnapshot) -> dict[str, Any]:
    """Consolidate recent progress into a structured summary.

    Returns counts, mastery distribution, and a prose summary.
    """
    total = len(snapshot.topic_states)
    weak = len(snapshot.weak_topics)
    strong = len(snapshot.strong_topics)
    frontier = len(snapshot.current_frontier)
    review = len(snapshot.review_queue)
    unseen = sum(1 for t in snapshot.topic_states if t.mastery_status == "unseen")

    return {
        "workspace_id": snapshot.workspace_id,
        "user_id": snapshot.user_id,
        "total_topics": total,
        "mastery_distribution": {
            "unseen": unseen,
            "novice": sum(1 for t in snapshot.topic_states if t.mastery_status == "novice"),
            "intermediate": frontier,
            "expert": sum(1 for t in snapshot.topic_states if t.mastery_status == "expert"),
        },
        "weak_count": weak,
        "strong_count": strong,
        "frontier_count": frontier,
        "review_count": review,
        "summary": snapshot.summary_text(),
    }


def generate_frontier_suggestions(
    snapshot: LearnerProfileSnapshot,
    *,
    max_suggestions: int = 5,
) -> dict[str, Any]:
    """Identify review and next-topic candidates.

    Prioritizes topics needing review, then frontier topics closest to
    leveling up, then weak topics that could benefit from targeted study.
    """
    suggestions: list[dict[str, Any]] = []

    # Priority 1: topics recommended for review quiz
    for t in snapshot.review_queue[:max_suggestions]:
        suggestions.append({
            "concept_id": t.concept_id,
            "name": t.canonical_name,
            "reason": "review_quiz_recommended",
            "mastery": t.mastery_status,
            "readiness": t.readiness_score,
        })

    remaining = max_suggestions - len(suggestions)

    # Priority 2: frontier topics (intermediate) sorted by readiness desc
    if remaining > 0:
        frontier_sorted = sorted(
            snapshot.current_frontier,
            key=lambda t: t.readiness_score or 0,
            reverse=True,
        )
        for t in frontier_sorted[:remaining]:
            if not any(s["concept_id"] == t.concept_id for s in suggestions):
                suggestions.append({
                    "concept_id": t.concept_id,
                    "name": t.canonical_name,
                    "reason": "frontier_close_to_mastery",
                    "mastery": t.mastery_status,
                    "readiness": t.readiness_score,
                })
        remaining = max_suggestions - len(suggestions)

    # Priority 3: weak topics sorted by score desc (most recoverable first)
    if remaining > 0:
        weak_sorted = sorted(
            snapshot.weak_topics,
            key=lambda t: t.mastery_score or 0,
            reverse=True,
        )
        for t in weak_sorted[:remaining]:
            if not any(s["concept_id"] == t.concept_id for s in suggestions):
                suggestions.append({
                    "concept_id": t.concept_id,
                    "name": t.canonical_name,
                    "reason": "weak_needs_practice",
                    "mastery": t.mastery_status,
                    "readiness": t.readiness_score,
                })

    return {
        "workspace_id": snapshot.workspace_id,
        "user_id": snapshot.user_id,
        "suggestions": suggestions,
        "suggestion_count": len(suggestions),
    }


def generate_deep_review(snapshot: LearnerProfileSnapshot) -> dict[str, Any]:
    """Produce a 'what you know / what seems shaky / what to review next' pack.

    Synthesizes across the full snapshot to give a structured review
    suitable for surfacing in a study dashboard.
    """
    strong_names = [t.canonical_name for t in snapshot.strong_topics]
    shaky = [
        {"name": t.canonical_name, "mastery": t.mastery_status, "readiness": t.readiness_score}
        for t in snapshot.topic_states
        if t.mastery_status == "intermediate"
        and t.readiness_score is not None
        and t.readiness_score < 0.5
    ]
    weak_names = [t.canonical_name for t in snapshot.weak_topics]
    review_names = [t.canonical_name for t in snapshot.review_queue]

    return {
        "workspace_id": snapshot.workspace_id,
        "user_id": snapshot.user_id,
        "what_you_know": strong_names,
        "what_seems_shaky": shaky,
        "what_to_review_next": review_names or weak_names[:5],
        "session_context": snapshot.recent_session_summary or None,
    }


# ---------------------------------------------------------------------------
# Storage helper
# ---------------------------------------------------------------------------

_INSERT_DIGEST = text("""
    INSERT INTO learner_digests (workspace_id, user_id, digest_type, payload)
    VALUES (:workspace_id, :user_id, :digest_type, :payload)
""")


def store_digest(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    digest_type: str,
    payload: dict[str, Any],
) -> None:
    """Persist a digest record."""
    session.execute(
        _INSERT_DIGEST,
        {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "digest_type": digest_type,
            "payload": json.dumps(payload),
        },
    )


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def run_learner_digest() -> None:
    """Generate and store learner digests for all active user-workspace pairs."""
    settings = get_settings()
    engine = create_db_engine(settings)

    with Session(engine) as session:
        pairs = (
            session.execute(
                text(
                    """
                    SELECT DISTINCT workspace_id, user_id
                    FROM mastery
                    ORDER BY workspace_id, user_id
                    LIMIT :limit
                    """
                ),
                {"limit": MAX_USERS_PER_RUN},
            )
            .mappings()
            .all()
        )

        total_digests = 0
        for pair in pairs:
            workspace_id = int(pair["workspace_id"])
            user_id = int(pair["user_id"])
            try:
                snapshot = assemble_learner_snapshot(
                    session, workspace_id=workspace_id, user_id=user_id,
                )

                generators = {
                    "learner_summary": generate_learner_summary,
                    "frontier_suggestions": generate_frontier_suggestions,
                    "deep_review": generate_deep_review,
                }

                for dtype, gen_fn in generators.items():
                    payload = gen_fn(snapshot)
                    store_digest(
                        session,
                        workspace_id=workspace_id,
                        user_id=user_id,
                        digest_type=dtype,
                        payload=payload,
                    )
                    total_digests += 1

                logger.info(
                    "learner_digest: workspace=%d user=%d digests=%d",
                    workspace_id,
                    user_id,
                    len(generators),
                )
            except Exception:
                logger.exception(
                    "learner_digest: failed for workspace=%d user=%d",
                    workspace_id,
                    user_id,
                )
                if callable(getattr(session, "rollback", None)):
                    session.rollback()

        session.commit()
        logger.info("learner_digest: completed. Total digests stored: %d", total_digests)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_learner_digest()
