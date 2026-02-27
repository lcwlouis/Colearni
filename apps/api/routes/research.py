"""Research agent routes (workspace-scoped)."""

from __future__ import annotations

from adapters.db.dependencies import get_db_session
from apps.api.dependencies import WorkspaceContext, get_workspace_context
from core.schemas import (
    ResearchCandidateReviewRequest,
    ResearchCandidateSummary,
    ResearchRunSummary,
    ResearchSourceCreate,
    ResearchSourceSummary,
)
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

router = APIRouter(prefix="/workspaces/{ws_id}/research", tags=["research"])


# ── Sources ───────────────────────────────────────────────────────────


@router.post("/sources", response_model=ResearchSourceSummary, status_code=status.HTTP_201_CREATED)
def add_research_source(
    payload: ResearchSourceCreate,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> ResearchSourceSummary:
    """Register a new research source URL for the workspace."""
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
                "workspace_id": ws.workspace_id,
                "url": payload.url.strip(),
                "label": (payload.label or "").strip() or None,
            },
        )
        .mappings()
        .one()
    )
    db.commit()
    return ResearchSourceSummary(
        source_id=int(row["id"]),
        url=str(row["url"]),
        label=str(row["label"]) if row["label"] else None,
        active=bool(row["active"]),
    )


@router.get("/sources", response_model=list[ResearchSourceSummary])
def list_research_sources(
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> list[ResearchSourceSummary]:
    """List registered research sources for the workspace."""
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
            {"workspace_id": ws.workspace_id},
        )
        .mappings()
        .all()
    )
    return [
        ResearchSourceSummary(
            source_id=int(row["id"]),
            url=str(row["url"]),
            label=str(row["label"]) if row["label"] else None,
            active=bool(row["active"]),
        )
        for row in rows
    ]


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_research_source(
    source_id: int,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> Response:
    """Deactivate (soft-delete) a research source."""
    db.execute(
        text(
            """
            UPDATE workspace_research_sources
            SET active = FALSE
            WHERE id = :source_id AND workspace_id = :workspace_id
            """
        ),
        {"source_id": source_id, "workspace_id": ws.workspace_id},
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Runs ──────────────────────────────────────────────────────────────


@router.post("/runs", response_model=ResearchRunSummary, status_code=status.HTTP_201_CREATED)
def trigger_research_run(
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> ResearchRunSummary:
    """Trigger a new research run."""
    row = (
        db.execute(
            text(
                """
                INSERT INTO workspace_research_runs (workspace_id)
                VALUES (:workspace_id)
                RETURNING id, status, candidates_found, started_at, finished_at
                """
            ),
            {"workspace_id": ws.workspace_id},
        )
        .mappings()
        .one()
    )
    db.commit()
    return ResearchRunSummary(
        run_id=int(row["id"]),
        status=str(row["status"]),
        candidates_found=int(row["candidates_found"]),
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )


@router.get("/runs", response_model=list[ResearchRunSummary])
def list_research_runs(
    limit: int = Query(default=10, ge=1, le=50),
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> list[ResearchRunSummary]:
    """List recent research runs."""
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
            {"workspace_id": ws.workspace_id, "limit": limit},
        )
        .mappings()
        .all()
    )
    return [
        ResearchRunSummary(
            run_id=int(row["id"]),
            status=str(row["status"]),
            candidates_found=int(row["candidates_found"]),
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )
        for row in rows
    ]


# ── Candidates ────────────────────────────────────────────────────────


@router.get("/candidates", response_model=list[ResearchCandidateSummary])
def list_research_candidates(
    run_id: int | None = Query(default=None, gt=0),
    status_filter: str | None = Query(default=None, alias="status"),
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> list[ResearchCandidateSummary]:
    """List research candidates, optionally filtered by run or status."""
    where_clauses = ["workspace_id = :workspace_id"]
    params: dict[str, object] = {"workspace_id": ws.workspace_id}

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
    return [
        ResearchCandidateSummary(
            candidate_id=int(row["id"]),
            source_url=str(row["source_url"]),
            title=str(row["title"]) if row["title"] else None,
            snippet=str(row["snippet"]) if row["snippet"] else None,
            status=str(row["status"]),
        )
        for row in rows
    ]


@router.patch("/candidates/{candidate_id}", response_model=ResearchCandidateSummary)
def review_research_candidate(
    candidate_id: int,
    payload: ResearchCandidateReviewRequest,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> ResearchCandidateSummary:
    """Approve or reject a research candidate."""
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
                "workspace_id": ws.workspace_id,
                "status": payload.status,
                "user_id": ws.user.id,
            },
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found.",
        )
    db.commit()
    return ResearchCandidateSummary(
        candidate_id=int(row["id"]),
        source_url=str(row["source_url"]),
        title=str(row["title"]) if row["title"] else None,
        snippet=str(row["snippet"]) if row["snippet"] else None,
        status=str(row["status"]),
    )


__all__ = ["router"]
