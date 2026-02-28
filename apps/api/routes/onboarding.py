"""Onboarding route — workspace readiness and suggested topics."""

from __future__ import annotations

from adapters.db.dependencies import get_db_session
from apps.api.dependencies import WorkspaceContext, get_workspace_context
from core.schemas import OnboardingStatusResponse
from domain.onboarding.status import get_onboarding_status
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

router = APIRouter(prefix="/workspaces/{ws_id}/onboarding", tags=["onboarding"])


@router.get("/status", response_model=OnboardingStatusResponse)
def onboarding_status(
    topic_limit: int = Query(default=5, ge=1, le=20),
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> OnboardingStatusResponse:
    return OnboardingStatusResponse.model_validate(
        get_onboarding_status(db, workspace_id=ws.workspace_id, topic_limit=topic_limit)
    )
