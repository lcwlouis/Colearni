"""Readiness analyzer background job.

Usage:
    python -m apps.jobs.readiness_analyzer

Iterates all (workspace, user) pairs and recomputes readiness scores.
"""

from __future__ import annotations

import logging

from adapters.db.engine import create_db_engine
from core.settings import get_settings
from domain.readiness.analyzer import analyze_workspace_readiness
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def run_readiness_analysis() -> None:
    """Run readiness analysis for all active users across workspaces."""
    settings = get_settings()
    engine = create_db_engine(settings)

    with Session(engine) as session:
        # Find all (workspace, user) pairs that have mastery records
        pairs = (
            session.execute(
                text(
                    """
                    SELECT DISTINCT workspace_id, user_id
                    FROM mastery
                    ORDER BY workspace_id, user_id
                    """
                )
            )
            .mappings()
            .all()
        )

        total_updated = 0
        for pair in pairs:
            workspace_id = int(pair["workspace_id"])
            user_id = int(pair["user_id"])
            try:
                results = analyze_workspace_readiness(
                    session,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    half_life_days=settings.readiness_half_life_days,
                )
                total_updated += len(results)
                logger.info(
                    "readiness: workspace=%d user=%d topics=%d",
                    workspace_id,
                    user_id,
                    len(results),
                )
            except Exception:
                logger.exception(
                    "readiness: failed for workspace=%d user=%d",
                    workspace_id,
                    user_id,
                )
                if callable(getattr(session, "rollback", None)):
                    session.rollback()

        # Snapshot
        session.execute(
            text(
                """
                INSERT INTO tutor_readiness_snapshots (workspace_id, user_id, snapshot)
                SELECT
                    uts.workspace_id,
                    uts.user_id,
                    jsonb_agg(jsonb_build_object(
                        'concept_id', uts.concept_id,
                        'readiness_score', uts.readiness_score,
                        'recommend_quiz', uts.recommend_quiz
                    ))
                FROM user_topic_state uts
                GROUP BY uts.workspace_id, uts.user_id
                """
            )
        )
        session.commit()

        logger.info(
            "readiness_analyzer: completed. Total topic states updated: %d",
            total_updated,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_readiness_analysis()
