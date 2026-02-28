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
from domain.research.service import CandidateNotFoundError
from domain.research import service as research_service
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
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
    return research_service.add_source(
        db,
        workspace_id=ws.workspace_id,
        url=payload.url,
        label=payload.label,
    )


@router.get("/sources", response_model=list[ResearchSourceSummary])
def list_research_sources(
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> list[ResearchSourceSummary]:
    """List registered research sources for the workspace."""
    return research_service.list_sources(db, workspace_id=ws.workspace_id)


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_research_source(
    source_id: int,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> Response:
    """Deactivate (soft-delete) a research source."""
    research_service.deactivate_source(db, source_id=source_id, workspace_id=ws.workspace_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Runs ──────────────────────────────────────────────────────────────


@router.post("/runs", response_model=ResearchRunSummary, status_code=status.HTTP_201_CREATED)
def trigger_research_run(
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> ResearchRunSummary:
    """Trigger a new research run."""
    return research_service.trigger_run(db, workspace_id=ws.workspace_id)


@router.get("/runs", response_model=list[ResearchRunSummary])
def list_research_runs(
    limit: int = Query(default=10, ge=1, le=50),
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> list[ResearchRunSummary]:
    """List recent research runs."""
    return research_service.list_runs(db, workspace_id=ws.workspace_id, limit=limit)


# ── Candidates ────────────────────────────────────────────────────────


@router.get("/candidates", response_model=list[ResearchCandidateSummary])
def list_research_candidates(
    run_id: int | None = Query(default=None, gt=0),
    status_filter: str | None = Query(default=None, alias="status"),
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> list[ResearchCandidateSummary]:
    """List research candidates, optionally filtered by run or status."""
    return research_service.list_candidates(
        db,
        workspace_id=ws.workspace_id,
        run_id=run_id,
        status_filter=status_filter,
    )


@router.patch("/candidates/{candidate_id}", response_model=ResearchCandidateSummary)
def review_research_candidate(
    candidate_id: int,
    payload: ResearchCandidateReviewRequest,
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> ResearchCandidateSummary:
    """Approve or reject a research candidate."""
    try:
        return research_service.review_candidate(
            db,
            candidate_id=candidate_id,
            workspace_id=ws.workspace_id,
            new_status=payload.status,
            user_id=ws.user.id,
        )
    except CandidateNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found.",
        )


__all__ = ["router"]
