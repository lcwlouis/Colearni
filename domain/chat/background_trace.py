"""Read helpers for background digest / candidate state used by tutor traces."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class BackgroundTraceState:
    """Snapshot of background state for trace enrichment."""

    digest_available: bool = False
    frontier_suggestion_count: int = 0
    research_candidate_pending: int = 0
    research_candidate_approved: int = 0


def fetch_background_trace_state(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
) -> BackgroundTraceState:
    """Query latest background digest and candidate counts for trace fields.

    Designed to be cheap and failure-safe — returns defaults on any error.
    """
    try:
        return _fetch(session, workspace_id=workspace_id, user_id=user_id)
    except Exception:
        return BackgroundTraceState()


def _fetch(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
) -> BackgroundTraceState:
    # 1. Check if any learner digest exists for this user+workspace
    digest_row = session.execute(
        text(
            """
            SELECT digest_type, payload
            FROM learner_digests
            WHERE workspace_id = :workspace_id AND user_id = :user_id
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"workspace_id": workspace_id, "user_id": user_id},
    ).mappings().first()

    digest_available = digest_row is not None

    # 2. Count frontier suggestions from latest frontier_suggestions digest
    frontier_count = 0
    if digest_available:
        frontier_row = session.execute(
            text(
                """
                SELECT payload
                FROM learner_digests
                WHERE workspace_id = :workspace_id
                  AND user_id = :user_id
                  AND digest_type = 'frontier_suggestions'
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"workspace_id": workspace_id, "user_id": user_id},
        ).mappings().first()

        if frontier_row is not None:
            payload = frontier_row["payload"]
            if isinstance(payload, dict):
                suggestions = payload.get("suggestions", [])
                frontier_count = len(suggestions) if isinstance(suggestions, list) else 0

    # 3. Count research candidates by status
    pending = 0
    approved = 0
    candidate_rows = session.execute(
        text(
            """
            SELECT status, COUNT(*) AS cnt
            FROM workspace_research_candidates
            WHERE workspace_id = :workspace_id
            GROUP BY status
            """
        ),
        {"workspace_id": workspace_id},
    ).mappings().all()

    for row in candidate_rows:
        status = str(row["status"])
        cnt = int(row["cnt"])
        if status == "pending":
            pending = cnt
        elif status == "approved":
            approved = cnt

    return BackgroundTraceState(
        digest_available=digest_available,
        frontier_suggestion_count=frontier_count,
        research_candidate_pending=pending,
        research_candidate_approved=approved,
    )
