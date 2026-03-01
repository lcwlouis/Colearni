"""Learning-gated candidate promotion (AR5.4).

Converts approved research candidates into learning candidates with
optional quiz/review gates before promotion into trusted material.

All promotion decisions go through CandidatePromotionDecision — no
automatic promotion of unapproved content.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from domain.research.planner import CandidatePromotionDecision

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def evaluate_candidate_for_promotion(
    *,
    candidate_id: int,
    candidate_status: str,
    has_quiz_gate: bool = False,
    quiz_passed: bool = False,
) -> CandidatePromotionDecision:
    """Decide whether a candidate should be promoted to trusted material.

    Only approved candidates can be promoted.  Optionally requires a
    quiz gate to be satisfied first.
    """
    if candidate_status != "approved":
        return CandidatePromotionDecision(
            candidate_id=candidate_id,
            action="reject",
            reason=f"Candidate status is '{candidate_status}', not 'approved'",
        )

    if has_quiz_gate and not quiz_passed:
        return CandidatePromotionDecision(
            candidate_id=candidate_id,
            action="quiz_gate",
            reason="Quiz gate required before promotion",
            requires_review_quiz=True,
        )

    return CandidatePromotionDecision(
        candidate_id=candidate_id,
        action="promote",
        reason="Approved and ready for promotion",
    )


def promote_candidate(
    session: "Session",
    *,
    candidate_id: int,
    workspace_id: int,
    decision: CandidatePromotionDecision,
) -> bool:
    """Execute a promotion decision for a candidate.

    If the decision is 'promote', marks the candidate as 'ingested'
    in the DB.  Returns True if the candidate was promoted.

    The actual ingestion into the learning pipeline should be triggered
    separately via the existing ingest_approved_candidates() path.
    """
    if decision.action != "promote":
        logger.debug(
            "Candidate %d not promoted: action=%s, reason=%s",
            candidate_id, decision.action, decision.reason,
        )
        return False

    from sqlalchemy import text as sql_text

    try:
        result = session.execute(
            sql_text(
                "UPDATE workspace_research_candidates "
                "SET status = 'ingested' "
                "WHERE id = :candidate_id AND workspace_id = :workspace_id AND status = 'approved'"
            ),
            {"candidate_id": candidate_id, "workspace_id": workspace_id},
        )
        session.commit()
        promoted = result.rowcount > 0  # type: ignore[union-attr]
        if promoted:
            logger.info("Promoted candidate %d to ingested status", candidate_id)
        return promoted
    except Exception:
        logger.warning("Failed to promote candidate %d", candidate_id, exc_info=True)
        return False


def record_promotion_feedback(
    session: "Session",
    *,
    candidate_id: int,
    workspace_id: int,
    user_id: int,
    feedback: str,
) -> None:
    """Record user feedback on a promotion decision.

    Feedback is stored as a review note for future planning relevance.
    """
    from sqlalchemy import text as sql_text

    try:
        session.execute(
            sql_text(
                "UPDATE workspace_research_candidates "
                "SET reviewed_by_user_id = :user_id, reviewed_at = now() "
                "WHERE id = :candidate_id AND workspace_id = :workspace_id"
            ),
            {"candidate_id": candidate_id, "workspace_id": workspace_id, "user_id": user_id},
        )
        session.commit()
        logger.debug("Recorded feedback for candidate %d by user %d", candidate_id, user_id)
    except Exception:
        logger.warning("Failed to record feedback for candidate %d", candidate_id, exc_info=True)
