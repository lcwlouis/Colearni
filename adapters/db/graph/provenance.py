"""Provenance recording."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def insert_provenance(
    session: Session,
    *,
    workspace_id: int,
    target_type: str,
    target_id: int,
    chunk_id: int,
) -> None:
    """Insert provenance row idempotently."""
    session.execute(
        text(
            """
            INSERT INTO provenance (
                workspace_id,
                target_type,
                target_id,
                chunk_id
            )
            VALUES (
                :workspace_id,
                :target_type,
                :target_id,
                :chunk_id
            )
            ON CONFLICT (workspace_id, target_type, target_id, chunk_id)
            DO NOTHING
            """
        ),
        {
            "workspace_id": workspace_id,
            "target_type": target_type,
            "target_id": target_id,
            "chunk_id": chunk_id,
        },
    )


def count_provenance_for_concepts(
    session: Session,
    *,
    workspace_id: int,
    concept_ids: list[int],
) -> dict[int, int]:
    """Return {concept_id: provenance_count} for the given concepts."""
    if not concept_ids:
        return {}
    rows = (
        session.execute(
            text(
                """
                SELECT target_id, COUNT(*) AS cnt
                FROM provenance
                WHERE workspace_id = :workspace_id
                  AND target_type = 'concept'
                  AND target_id = ANY(:concept_ids)
                GROUP BY target_id
                """
            ),
            {"workspace_id": workspace_id, "concept_ids": concept_ids},
        )
        .mappings()
        .all()
    )
    return {int(r["target_id"]): int(r["cnt"]) for r in rows}
