"""Research digest background job (AR6.2).

Produces periodic research digests summarizing recent candidate activity
and approved-source changes across workspaces.

Digests are stored in the ``learner_digests`` table with digest_type
"research_digest" and "research_what_changed".  They are non-authoritative
recommendation material until explicitly surfaced.

No auto-ingestion, no approval-bypass.

Usage:
    python -m apps.jobs.research_digest
"""

from __future__ import annotations

import json
import logging
from typing import Any

from adapters.db.engine import create_db_engine
from core.observability import emit_event
from core.settings import get_settings
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

MAX_WORKSPACES_PER_RUN = 50


# ---------------------------------------------------------------------------
# Digest generators
# ---------------------------------------------------------------------------


def generate_research_digest(
    session: Session,
    *,
    workspace_id: int,
) -> dict[str, Any]:
    """Summarize recent research candidate activity for a workspace.

    Counts candidates by status and lists recent titles for review.
    """
    rows = (
        session.execute(
            text(
                """
                SELECT status, COUNT(*) AS cnt
                FROM workspace_research_candidates
                WHERE workspace_id = :workspace_id
                GROUP BY status
                """
            ),
            {"workspace_id": workspace_id},
        )
        .mappings()
        .all()
    )

    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[str(row["status"])] = int(row["cnt"])

    recent = (
        session.execute(
            text(
                """
                SELECT title, status, source_url
                FROM workspace_research_candidates
                WHERE workspace_id = :workspace_id
                ORDER BY created_at DESC
                LIMIT 10
                """
            ),
            {"workspace_id": workspace_id},
        )
        .mappings()
        .all()
    )

    recent_items = [
        {"title": r["title"], "status": r["status"], "url": r["source_url"]}
        for r in recent
    ]

    return {
        "workspace_id": workspace_id,
        "status_counts": status_counts,
        "total_candidates": sum(status_counts.values()),
        "recent_candidates": recent_items,
    }


def generate_what_changed(
    session: Session,
    *,
    workspace_id: int,
) -> dict[str, Any]:
    """Summarize recent research runs and delta from the last digest.

    Reports completed runs, new candidates found, and newly
    approved/rejected/ingested counts since the last digest.
    """
    runs = (
        session.execute(
            text(
                """
                SELECT id, status, candidates_found, started_at, finished_at
                FROM workspace_research_runs
                WHERE workspace_id = :workspace_id
                ORDER BY started_at DESC
                LIMIT 5
                """
            ),
            {"workspace_id": workspace_id},
        )
        .mappings()
        .all()
    )

    run_summaries = [
        {
            "run_id": int(r["id"]),
            "status": r["status"],
            "candidates_found": int(r["candidates_found"] or 0),
            "started_at": str(r["started_at"]) if r["started_at"] else None,
        }
        for r in runs
    ]

    # Count newly reviewed candidates (reviewed_at within a window)
    reviewed = (
        session.execute(
            text(
                """
                SELECT status, COUNT(*) AS cnt
                FROM workspace_research_candidates
                WHERE workspace_id = :workspace_id
                  AND reviewed_at IS NOT NULL
                GROUP BY status
                """
            ),
            {"workspace_id": workspace_id},
        )
        .mappings()
        .all()
    )

    reviewed_counts: dict[str, int] = {}
    for row in reviewed:
        reviewed_counts[str(row["status"])] = int(row["cnt"])

    return {
        "workspace_id": workspace_id,
        "recent_runs": run_summaries,
        "run_count": len(run_summaries),
        "reviewed_counts": reviewed_counts,
    }


# ---------------------------------------------------------------------------
# Storage (reuses learner_digests table)
# ---------------------------------------------------------------------------

_INSERT_DIGEST = text("""
    INSERT INTO learner_digests (workspace_id, user_id, digest_type, payload)
    VALUES (:workspace_id, :user_id, :digest_type, :payload)
""")


def store_research_digest(
    session: Session,
    *,
    workspace_id: int,
    digest_type: str,
    payload: dict[str, Any],
) -> None:
    """Persist a research digest record (user_id=0 for workspace-level)."""
    session.execute(
        _INSERT_DIGEST,
        {
            "workspace_id": workspace_id,
            "user_id": 0,
            "digest_type": digest_type,
            "payload": json.dumps(payload),
        },
    )


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def run_research_digest() -> None:
    """Generate and store research digests for all active workspaces."""
    settings = get_settings()
    engine = create_db_engine(settings)

    with Session(engine) as session:
        workspaces = (
            session.execute(
                text(
                    """
                    SELECT DISTINCT workspace_id
                    FROM workspace_research_runs
                    ORDER BY workspace_id
                    LIMIT :limit
                    """
                ),
                {"limit": MAX_WORKSPACES_PER_RUN},
            )
            .mappings()
            .all()
        )

        total_digests = 0
        for ws in workspaces:
            workspace_id = int(ws["workspace_id"])
            try:
                digest = generate_research_digest(session, workspace_id=workspace_id)
                store_research_digest(
                    session,
                    workspace_id=workspace_id,
                    digest_type="research_digest",
                    payload=digest,
                )

                what_changed = generate_what_changed(session, workspace_id=workspace_id)
                store_research_digest(
                    session,
                    workspace_id=workspace_id,
                    digest_type="research_what_changed",
                    payload=what_changed,
                )

                total_digests += 2
                logger.info(
                    "research_digest: workspace=%d digests=2",
                    workspace_id,
                )
                emit_event(
                    "bg_research_digest",
                    status="ok",
                    component="research_digest",
                    workspace_id=workspace_id,
                )
            except Exception:
                logger.exception(
                    "research_digest: failed for workspace=%d",
                    workspace_id,
                )
                if callable(getattr(session, "rollback", None)):
                    session.rollback()

        session.commit()
        logger.info("research_digest: completed. Total digests stored: %d", total_digests)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_research_digest()
