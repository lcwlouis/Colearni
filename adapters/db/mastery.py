"""Query helpers for mastery status lookups."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_mastery_status(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    concept_id: int,
) -> str | None:
    """Return mastery status for one workspace/user/concept tuple."""
    row = (
        session.execute(
            text(
                """
                SELECT status
                FROM mastery
                WHERE workspace_id = :workspace_id
                  AND user_id = :user_id
                  AND concept_id = :concept_id
                LIMIT 1
                """
            ),
            {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "concept_id": concept_id,
            },
        )
        .mappings()
        .first()
    )
    if row is None:
        return None

    raw_status = row["status"]
    status = str(raw_status).strip().lower()
    return status or None


__all__ = ["get_mastery_status"]
