"""Readiness routes (workspace-scoped)."""

from __future__ import annotations

from adapters.db.dependencies import get_db_session
from apps.api.dependencies import WorkspaceContext, get_workspace_context
from core.schemas import ReadinessSnapshotResponse, ReadinessTopicState
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

router = APIRouter(prefix="/workspaces/{ws_id}/readiness", tags=["readiness"])


@router.get("/snapshot", response_model=ReadinessSnapshotResponse)
def get_readiness_snapshot(
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> ReadinessSnapshotResponse:
    """Return per-topic readiness scores for the current user."""
    rows = (
        db.execute(
            text(
                """
                SELECT
                    uts.concept_id,
                    cc.canonical_name AS concept_name,
                    uts.readiness_score,
                    uts.recommend_quiz,
                    uts.last_assessed_at
                FROM user_topic_state uts
                JOIN concepts_canon cc ON cc.id = uts.concept_id
                WHERE uts.workspace_id = :workspace_id
                  AND uts.user_id = :user_id
                ORDER BY uts.readiness_score ASC, cc.canonical_name ASC
                """
            ),
            {"workspace_id": ws.workspace_id, "user_id": ws.user.id},
        )
        .mappings()
        .all()
    )
    return ReadinessSnapshotResponse(
        workspace_id=ws.workspace_id,
        user_id=ws.user.id,
        topics=[
            ReadinessTopicState(
                concept_id=int(row["concept_id"]),
                concept_name=str(row["concept_name"]),
                readiness_score=float(row["readiness_score"]),
                recommend_quiz=bool(row["recommend_quiz"]),
                last_assessed_at=row["last_assessed_at"],
            )
            for row in rows
        ],
    )


__all__ = ["router"]
