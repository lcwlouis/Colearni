"""Onboarding helpers — suggest starting topics and workspace readiness check."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def suggest_starting_topics(
    session: Session,
    *,
    workspace_id: int,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return top-N concepts by degree for a workspace.

    These are the most connected concepts — good starting points for a new user.
    """
    rows = (
        session.execute(
            text(
                """
                SELECT
                    c.id   AS concept_id,
                    c.canonical_name,
                    c.description,
                    c.tier,
                    (
                        SELECT count(*)
                        FROM edges_canon e
                        WHERE e.workspace_id = :workspace_id
                          AND (e.src_id = c.id OR e.tgt_id = c.id)
                    ) AS degree
                FROM concepts_canon c
                WHERE c.workspace_id = :workspace_id
                  AND c.is_active = TRUE
                  AND (c.tier IN ('umbrella', 'topic') OR c.tier IS NULL)
                ORDER BY degree DESC, c.canonical_name
                LIMIT :limit
                """
            ),
            {"workspace_id": workspace_id, "limit": limit},
        )
        .mappings()
        .all()
    )
    return [
        {
            "concept_id": int(r["concept_id"]),
            "canonical_name": str(r["canonical_name"]),
            "description": str(r["description"]) if r["description"] else None,
            "tier": str(r["tier"]) if r["tier"] else None,
            "degree": int(r["degree"]),
        }
        for r in rows
    ]


def get_onboarding_status(
    session: Session,
    *,
    workspace_id: int,
    topic_limit: int = 5,
) -> dict[str, Any]:
    """Return workspace onboarding readiness status.

    Checks whether the workspace has documents and active concepts,
    and suggests top starting topics.
    """
    doc_count = int(
        session.execute(
            text("SELECT count(*) FROM documents WHERE workspace_id = :workspace_id"),
            {"workspace_id": workspace_id},
        ).scalar_one()
    )
    concept_count = int(
        session.execute(
            text(
                "SELECT count(*) FROM concepts_canon "
                "WHERE workspace_id = :workspace_id AND is_active = TRUE"
            ),
            {"workspace_id": workspace_id},
        ).scalar_one()
    )
    suggested_topics = (
        suggest_starting_topics(session, workspace_id=workspace_id, limit=topic_limit)
        if concept_count > 0
        else []
    )
    return {
        "has_documents": doc_count > 0,
        "has_active_concepts": concept_count > 0,
        "suggested_topics": suggested_topics,
    }
