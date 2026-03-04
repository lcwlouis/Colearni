"""Quiz gardener background job.

Auto-generates level-up quizzes for concepts that have entered active
learning scope but don't yet have a quiz.

Usage:
    python -m apps.jobs.quiz_gardener
"""

from __future__ import annotations

import logging

from adapters.db.engine import create_db_engine
from adapters.llm.factory import build_graph_llm_client
from core.settings import get_settings
from domain.learning.level_up import create_level_up_quiz
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Maximum concepts to process per run to bound execution time
MAX_CONCEPTS_PER_RUN = 20


def run_quiz_gardener() -> None:
    """Generate level-up quizzes for concepts in active learning without a quiz."""
    settings = get_settings()
    engine = create_db_engine(settings)

    try:
        llm_client = build_graph_llm_client(settings=settings)
    except ValueError:
        logger.warning("quiz_gardener: no LLM client available, skipping run")
        return

    with Session(engine) as session:
        # Find (workspace, user, concept) tuples where:
        # 1. User has mastery status 'learning' for the concept
        # 2. No level_up quiz exists yet for that concept+user+workspace
        candidates = (
            session.execute(
                text(
                    """
                    SELECT m.workspace_id, m.user_id, m.concept_id,
                           c.canonical_name
                    FROM mastery m
                    JOIN concepts_canon c
                      ON c.id = m.concept_id
                     AND c.workspace_id = m.workspace_id
                     AND c.is_active = TRUE
                    WHERE m.status = 'learning'
                      AND NOT EXISTS (
                          SELECT 1 FROM quizzes q
                          WHERE q.workspace_id = m.workspace_id
                            AND q.user_id = m.user_id
                            AND q.concept_id = m.concept_id
                            AND q.quiz_type = 'level_up'
                      )
                    ORDER BY m.workspace_id, m.user_id, m.concept_id
                    LIMIT :limit
                    """
                ),
                {"limit": MAX_CONCEPTS_PER_RUN},
            )
            .mappings()
            .all()
        )

        if not candidates:
            logger.info("quiz_gardener: no concepts need auto-quiz generation")
            return

        created = 0
        for candidate in candidates:
            workspace_id = int(candidate["workspace_id"])
            user_id = int(candidate["user_id"])
            concept_id = int(candidate["concept_id"])
            concept_name = str(candidate["canonical_name"])
            try:
                create_level_up_quiz(
                    session,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    concept_id=concept_id,
                    session_id=None,
                    question_count=None,
                    items=None,
                    llm_client=llm_client,
                    context_source="auto_gardener",
                )
                created += 1
                logger.info(
                    "quiz_gardener: created quiz for workspace=%d user=%d concept=%d (%s)",
                    workspace_id,
                    user_id,
                    concept_id,
                    concept_name,
                )
            except Exception:
                logger.exception(
                    "quiz_gardener: failed for workspace=%d user=%d concept=%d (%s)",
                    workspace_id,
                    user_id,
                    concept_id,
                    concept_name,
                )
                if callable(getattr(session, "rollback", None)):
                    session.rollback()

        logger.info("quiz_gardener: completed. Created %d quizzes.", created)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_quiz_gardener()
