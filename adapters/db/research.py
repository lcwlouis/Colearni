"""Research persistence layer – all SQL for research sources, runs, and candidates."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


# ── Sources ───────────────────────────────────────────────────────────


def upsert_source(
    db: Session,
    *,
    workspace_id: int,
    url: str,
    label: str | None,
) -> dict[str, Any]:
    """Insert or reactivate a research source. Returns the row dict."""
    row = (
        db.execute(
            text(
                """
                INSERT INTO workspace_research_sources (workspace_id, url, label)
                VALUES (:workspace_id, :url, :label)
                ON CONFLICT (workspace_id, url) DO UPDATE
                    SET active = TRUE, label = COALESCE(EXCLUDED.label, workspace_research_sources.label)
                RETURNING id, url, label, active
                """
            ),
            {
                "workspace_id": workspace_id,
                "url": url,
                "label": label,
            },
        )
        .mappings()
        .one()
    )
    return dict(row)


def list_sources(db: Session, *, workspace_id: int) -> list[dict[str, Any]]:
    """List all research sources for a workspace."""
    rows = (
        db.execute(
            text(
                """
                SELECT id, url, label, active
                FROM workspace_research_sources
                WHERE workspace_id = :workspace_id
                ORDER BY created_at DESC
                """
            ),
            {"workspace_id": workspace_id},
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


def deactivate_source(db: Session, *, source_id: int, workspace_id: int) -> None:
    """Soft-delete a research source by marking it inactive."""
    db.execute(
        text(
            """
            UPDATE workspace_research_sources
            SET active = FALSE
            WHERE id = :source_id AND workspace_id = :workspace_id
            """
        ),
        {"source_id": source_id, "workspace_id": workspace_id},
    )


# ── Runs ──────────────────────────────────────────────────────────────


def insert_run(db: Session, *, workspace_id: int) -> dict[str, Any]:
    """Create a new research run. Returns the row dict."""
    row = (
        db.execute(
            text(
                """
                INSERT INTO workspace_research_runs (workspace_id)
                VALUES (:workspace_id)
                RETURNING id, status, candidates_found, started_at, finished_at
                """
            ),
            {"workspace_id": workspace_id},
        )
        .mappings()
        .one()
    )
    return dict(row)


def list_runs(
    db: Session,
    *,
    workspace_id: int,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """List recent research runs for a workspace."""
    rows = (
        db.execute(
            text(
                """
                SELECT id, status, candidates_found, started_at, finished_at
                FROM workspace_research_runs
                WHERE workspace_id = :workspace_id
                ORDER BY started_at DESC
                LIMIT :limit
                """
            ),
            {"workspace_id": workspace_id, "limit": limit},
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


# ── Candidates ────────────────────────────────────────────────────────


def list_candidates(
    db: Session,
    *,
    workspace_id: int,
    run_id: int | None = None,
    status_filter: str | None = None,
) -> list[dict[str, Any]]:
    """List research candidates, optionally filtered by run or status."""
    where_clauses = ["workspace_id = :workspace_id"]
    params: dict[str, object] = {"workspace_id": workspace_id}

    if run_id is not None:
        where_clauses.append("run_id = :run_id")
        params["run_id"] = run_id
    if status_filter is not None:
        where_clauses.append("status = :status_filter")
        params["status_filter"] = status_filter

    where_sql = " AND ".join(where_clauses)
    rows = (
        db.execute(
            text(
                f"""
                SELECT id, source_url, title, snippet, status
                FROM workspace_research_candidates
                WHERE {where_sql}
                ORDER BY created_at DESC
                LIMIT 100
                """
            ),
            params,
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


def review_candidate(
    db: Session,
    *,
    candidate_id: int,
    workspace_id: int,
    new_status: str,
    user_id: int,
) -> dict[str, Any] | None:
    """Update candidate status (approve/reject). Returns updated row or None."""
    row = (
        db.execute(
            text(
                """
                UPDATE workspace_research_candidates
                SET status = :status,
                    reviewed_by_user_id = :user_id,
                    reviewed_at = now()
                WHERE id = :candidate_id AND workspace_id = :workspace_id
                RETURNING id, source_url, title, snippet, status
                """
            ),
            {
                "candidate_id": candidate_id,
                "workspace_id": workspace_id,
                "status": new_status,
                "user_id": user_id,
            },
        )
        .mappings()
        .first()
    )
    return dict(row) if row is not None else None
