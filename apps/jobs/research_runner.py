"""Research runner background job.

Usage:
    python -m apps.jobs.research_runner --workspace-id <ID>

Executes a research run for the specified workspace, processing all
active sources and producing approval-gated candidates.
"""

from __future__ import annotations

import argparse
import logging

from adapters.db.engine import build_engine
from core.settings import get_settings
from domain.research.runner import run_research
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run research for a workspace")
    parser.add_argument("--workspace-id", type=int, required=True)
    args = parser.parse_args()

    settings = get_settings()
    engine = build_engine(settings.database_url)

    with Session(engine) as session:
        # Create a run record
        row = (
            session.execute(
                text(
                    "INSERT INTO workspace_research_runs (workspace_id) "
                    "VALUES (:workspace_id) RETURNING id"
                ),
                {"workspace_id": args.workspace_id},
            )
            .mappings()
            .one()
        )
        session.commit()
        run_id = int(row["id"])

        result = run_research(
            session,
            workspace_id=args.workspace_id,
            run_id=run_id,
            max_candidates=settings.research_max_candidates_per_run,
        )
        logger.info("research_runner: %s", result)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
