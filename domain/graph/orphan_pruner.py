"""Orphan graph pruning after document deletion (S44).

When a document is deleted, its chunks and provenance rows are removed.
Canonical concepts/edges may become 'orphans' — no remaining provenance
links to any chunk.  This module provides the pruning logic.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def find_orphan_concept_ids(
    session: Session,
    *,
    workspace_id: int,
) -> list[int]:
    """Return concept IDs with zero provenance rows in the workspace."""
    rows = (
        session.execute(
            text("""
                SELECT cc.id
                FROM concepts_canon cc
                WHERE cc.workspace_id = :wid
                  AND cc.is_active = TRUE
                  AND NOT EXISTS (
                      SELECT 1 FROM provenance p
                      WHERE p.workspace_id = :wid
                        AND p.target_type = 'concept'
                        AND p.target_id = cc.id
                  )
            """),
            {"wid": workspace_id},
        )
        .scalars()
        .all()
    )
    return [int(r) for r in rows]


def find_orphan_edge_ids(
    session: Session,
    *,
    workspace_id: int,
) -> list[int]:
    """Return edge IDs with zero provenance rows in the workspace."""
    rows = (
        session.execute(
            text("""
                SELECT ec.id
                FROM edges_canon ec
                WHERE ec.workspace_id = :wid
                  AND NOT EXISTS (
                      SELECT 1 FROM provenance p
                      WHERE p.workspace_id = :wid
                        AND p.target_type = 'edge'
                        AND p.target_id = ec.id
                  )
            """),
            {"wid": workspace_id},
        )
        .scalars()
        .all()
    )
    return [int(r) for r in rows]


def prune_orphan_graph_nodes(
    session: Session,
    *,
    workspace_id: int,
) -> dict[str, Any]:
    """Remove canonical concepts and edges with no remaining provenance.

    Returns a summary of what was pruned:
        {"pruned_concepts": int, "pruned_edges": int}
    """
    # Prune orphan edges first (they reference concepts via FK)
    orphan_edge_ids = find_orphan_edge_ids(session, workspace_id=workspace_id)
    pruned_edges = 0
    if orphan_edge_ids:
        result = session.execute(
            text("""
                DELETE FROM edges_canon
                WHERE workspace_id = :wid AND id = ANY(:ids)
            """),
            {"wid": workspace_id, "ids": orphan_edge_ids},
        )
        pruned_edges = result.rowcount or 0

    # Prune orphan concepts (also remove edges referencing them first)
    orphan_concept_ids = find_orphan_concept_ids(session, workspace_id=workspace_id)
    pruned_concepts = 0
    if orphan_concept_ids:
        # Remove any edges that reference orphan concepts (cascading)
        session.execute(
            text("""
                DELETE FROM edges_canon
                WHERE workspace_id = :wid
                  AND (src_id = ANY(:ids) OR tgt_id = ANY(:ids))
            """),
            {"wid": workspace_id, "ids": orphan_concept_ids},
        )
        # Remove mastery rows referencing orphan concepts
        session.execute(
            text("""
                DELETE FROM mastery
                WHERE workspace_id = :wid AND concept_id = ANY(:ids)
            """),
            {"wid": workspace_id, "ids": orphan_concept_ids},
        )
        result = session.execute(
            text("""
                DELETE FROM concepts_canon
                WHERE workspace_id = :wid AND id = ANY(:ids)
            """),
            {"wid": workspace_id, "ids": orphan_concept_ids},
        )
        pruned_concepts = result.rowcount or 0

    return {
        "pruned_concepts": pruned_concepts,
        "pruned_edges": pruned_edges,
    }
