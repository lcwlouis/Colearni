"""Gardener seed concept listing."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from adapters.db.graph import CanonicalConceptRow, _to_canonical_concept_required


def list_gardener_seed_concepts(
    session: Session,
    *,
    workspace_id: int,
    recent_window_days: int,
    limit: int,
) -> list[CanonicalConceptRow]:
    """List bounded dirty/recent active canonical concepts for one workspace."""
    if recent_window_days < 1:
        raise ValueError("recent_window_days must be >= 1")
    if limit < 1:
        raise ValueError("limit must be >= 1")

    rows = (
        session.execute(
            text(
                """
                SELECT
                    id,
                    workspace_id,
                    canonical_name,
                    description,
                    aliases,
                    embedding,
                    is_active,
                    dirty,
                    tier
                FROM concepts_canon
                WHERE workspace_id = :workspace_id
                  AND is_active = TRUE
                  AND (
                    dirty = TRUE
                    OR updated_at >= now() - make_interval(days => :recent_window_days)
                  )
                ORDER BY dirty DESC, updated_at DESC, id ASC
                LIMIT :limit
                """
            ),
            {
                "workspace_id": workspace_id,
                "recent_window_days": recent_window_days,
                "limit": limit,
            },
        )
        .mappings()
        .all()
    )
    return [_to_canonical_concept_required(row) for row in rows]


def list_null_tier_concepts(
    session: Session,
    *,
    workspace_id: int,
    limit: int,
) -> list[CanonicalConceptRow]:
    """List active canonical concepts with tier IS NULL, bounded by limit."""
    if limit < 1:
        raise ValueError("limit must be >= 1")
    rows = (
        session.execute(
            text(
                """
                SELECT
                    id, workspace_id, canonical_name, description,
                    aliases, embedding, is_active, dirty, tier
                FROM concepts_canon
                WHERE workspace_id = :workspace_id
                  AND is_active = TRUE
                  AND tier IS NULL
                ORDER BY id ASC
                LIMIT :limit
                """
            ),
            {"workspace_id": workspace_id, "limit": limit},
        )
        .mappings()
        .all()
    )
    return [_to_canonical_concept_required(row) for row in rows]


def list_neighbor_names(
    session: Session,
    *,
    workspace_id: int,
    concept_id: int,
    limit: int = 10,
) -> list[str]:
    """Return canonical names of direct edge neighbors for a concept."""
    rows = (
        session.execute(
            text(
                """
                SELECT DISTINCT c.canonical_name
                FROM edges_canon e
                JOIN concepts_canon c
                  ON c.workspace_id = e.workspace_id
                  AND (
                    (c.id = e.src_id AND e.tgt_id = :concept_id)
                    OR (c.id = e.tgt_id AND e.src_id = :concept_id)
                  )
                WHERE e.workspace_id = :workspace_id
                  AND c.is_active = TRUE
                LIMIT :limit
                """
            ),
            {"workspace_id": workspace_id, "concept_id": concept_id, "limit": limit},
        )
        .scalars()
        .all()
    )
    return [str(name) for name in rows]
