"""Learner snapshot assembly service (AR4.2).

Assembles a LearnerProfileSnapshot from existing data sources:
- mastery status (adapters/db/mastery)
- readiness analysis (domain/readiness/analyzer)
- session memory (domain/chat/session_memory)
- concept names (adapters/db/graph/concepts)

This is a read-model assembly — it never writes back to source tables.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from domain.learner.profile import (
    LearnerProfileSnapshot,
    MasteryLevel,
    TopicStateSnapshot,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_VALID_MASTERY_LEVELS: set[str] = {"unseen", "novice", "intermediate", "expert"}


def _normalize_mastery(raw: str | None) -> MasteryLevel:
    """Coerce DB mastery string to a valid MasteryLevel."""
    if raw is None:
        return "unseen"
    low = raw.strip().lower()
    if low in _VALID_MASTERY_LEVELS:
        return low  # type: ignore[return-value]
    return "unseen"


def assemble_learner_snapshot(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    session_id: int | None = None,
) -> LearnerProfileSnapshot:
    """Build a LearnerProfileSnapshot from current DB state.

    Safe on missing data — returns an empty-but-valid snapshot if any
    source is unavailable.
    """
    topic_states = _build_topic_states(session, workspace_id=workspace_id, user_id=user_id)
    recent_session_summary = _build_session_summary(session, session_id=session_id)

    snapshot = LearnerProfileSnapshot(
        workspace_id=workspace_id,
        user_id=user_id,
        topic_states=topic_states,
        recent_session_summary=recent_session_summary,
    )
    logger.debug(
        "Assembled learner snapshot: %d topics, %d weak, %d strong",
        len(topic_states),
        len(snapshot.weak_topics),
        len(snapshot.strong_topics),
    )
    return snapshot


def _build_topic_states(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
) -> list[TopicStateSnapshot]:
    """Derive per-topic snapshots from readiness analysis results."""
    from domain.readiness.analyzer import analyze_workspace_readiness

    try:
        rows = analyze_workspace_readiness(
            session, workspace_id=workspace_id, user_id=user_id,
        )
    except Exception:
        logger.warning("Readiness analysis failed; returning empty topic list", exc_info=True)
        return []

    concept_names = _resolve_concept_names(
        session, workspace_id=workspace_id,
        concept_ids=[int(r["concept_id"]) for r in rows],
    )

    topic_states: list[TopicStateSnapshot] = []
    for row in rows:
        cid = int(row["concept_id"])
        mastery_score = float(row.get("mastery_score", 0) or 0)
        readiness_score = float(row.get("readiness_score", 0) or 0)
        recommend_quiz = bool(row.get("recommend_quiz", False))

        mastery_status = _mastery_score_to_level(mastery_score)

        topic_states.append(TopicStateSnapshot(
            concept_id=cid,
            canonical_name=concept_names.get(cid, f"concept-{cid}"),
            mastery_status=mastery_status,
            mastery_score=mastery_score,
            readiness_score=readiness_score,
            recommend_quiz=recommend_quiz,
        ))

    return topic_states


def _mastery_score_to_level(score: float) -> MasteryLevel:
    """Map a numeric mastery_score to a categorical MasteryLevel."""
    if score >= 0.8:
        return "expert"
    if score >= 0.5:
        return "intermediate"
    if score > 0.0:
        return "novice"
    return "unseen"


def _resolve_concept_names(
    session: Session,
    *,
    workspace_id: int,
    concept_ids: list[int],
) -> dict[int, str]:
    """Batch-resolve concept IDs to canonical names."""
    from adapters.db.graph.concepts import get_canonical_concept

    names: dict[int, str] = {}
    for cid in concept_ids:
        try:
            row = get_canonical_concept(session, workspace_id=workspace_id, concept_id=cid)
            if row is not None:
                names[cid] = row.canonical_name
        except Exception:
            logger.debug("Could not resolve concept name for %d", cid, exc_info=True)
    return names


def _build_session_summary(
    session: Session,
    *,
    session_id: int | None,
) -> str:
    """Load a compact session summary from recent chat + assessment context."""
    if session_id is None:
        return ""

    from domain.chat.session_memory import load_assessment_context

    try:
        return load_assessment_context(session, session_id=session_id)
    except Exception:
        logger.debug("Could not load session summary", exc_info=True)
        return ""
