from __future__ import annotations

from typing import Any, Literal

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

MAX_HOPS_CAP = 3
MAX_NODES_CAP = 80
MAX_EDGES_CAP = 160

_RANKED_REACH_CTE = """
WITH RECURSIVE reach AS (
    SELECT CAST(:concept_id AS bigint) AS concept_id,
           CAST(0 AS integer) AS hop_distance

    UNION ALL

    SELECT CASE WHEN e.src_id = reach.concept_id THEN e.tgt_id ELSE e.src_id END AS concept_id,
           reach.hop_distance + 1 AS hop_distance
    FROM reach
    JOIN edges_canon e
      ON e.workspace_id = :workspace_id
     AND (e.src_id = reach.concept_id OR e.tgt_id = reach.concept_id)
    JOIN concepts_canon next_c
      ON next_c.workspace_id = e.workspace_id
     AND next_c.id = CASE WHEN e.src_id = reach.concept_id THEN e.tgt_id ELSE e.src_id END
     AND next_c.is_active = TRUE
    WHERE reach.hop_distance < :hop_limit
),
ranked AS (
    SELECT concept_id, min(hop_distance) AS hop_distance
    FROM reach
    GROUP BY concept_id
)
"""


class GraphNotFoundError(ValueError):
    pass


class LuckyNoCandidateError(ValueError):
    pass


def get_concept_detail(session: Session, *, workspace_id: int, concept_id: int) -> dict[str, Any]:
    row = (
        session.execute(
            text(
                """
                SELECT
                    c.id AS concept_id,
                    c.canonical_name,
                    c.description,
                    c.aliases,
                    (
                        SELECT count(*)
                        FROM edges_canon e
                        JOIN concepts_canon src
                          ON src.id = e.src_id
                         AND src.workspace_id = e.workspace_id
                         AND src.is_active = TRUE
                        JOIN concepts_canon tgt
                          ON tgt.id = e.tgt_id
                         AND tgt.workspace_id = e.workspace_id
                         AND tgt.is_active = TRUE
                        WHERE e.workspace_id = :workspace_id
                          AND (e.src_id = c.id OR e.tgt_id = c.id)
                    ) AS degree
                FROM concepts_canon c
                WHERE c.workspace_id = :workspace_id
                  AND c.id = :concept_id
                  AND c.is_active = TRUE
                LIMIT 1
                """
            ),
            {"workspace_id": workspace_id, "concept_id": concept_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise GraphNotFoundError("Concept not found in workspace.")
    return {
        "workspace_id": workspace_id,
        "concept": {
            "concept_id": int(row["concept_id"]),
            "canonical_name": str(row["canonical_name"]),
            "description": str(row["description"] or ""),
            "aliases": [str(alias) for alias in (row["aliases"] or [])],
            "degree": int(row["degree"] or 0),
        },
    }


def get_bounded_subgraph(
    session: Session,
    *,
    workspace_id: int,
    concept_id: int,
    max_hops: int,
    max_nodes: int,
    max_edges: int,
) -> dict[str, Any]:
    node_rows = (
        session.execute(
            text(
                _RANKED_REACH_CTE
                + """
                SELECT ranked.concept_id, ranked.hop_distance, c.canonical_name, c.description
                FROM ranked
                JOIN concepts_canon c
                  ON c.id = ranked.concept_id
                 AND c.workspace_id = :workspace_id
                 AND c.is_active = TRUE
                ORDER BY ranked.hop_distance ASC, lower(c.canonical_name) ASC, ranked.concept_id ASC
                LIMIT :max_nodes
                """
            ),
            {
                "workspace_id": workspace_id,
                "concept_id": concept_id,
                "hop_limit": max_hops,
                "max_nodes": max_nodes,
            },
        )
        .mappings()
        .all()
    )
    if not node_rows:
        raise GraphNotFoundError("Concept not found in workspace.")

    edge_rows = (
        session.execute(
            text(
                """
                SELECT e.id AS edge_id, e.src_id, e.tgt_id, e.relation_type, e.description,
                       e.keywords, e.weight
                FROM edges_canon e
                JOIN concepts_canon src
                  ON src.id = e.src_id
                 AND src.workspace_id = e.workspace_id
                 AND src.is_active = TRUE
                JOIN concepts_canon tgt
                  ON tgt.id = e.tgt_id
                 AND tgt.workspace_id = e.workspace_id
                 AND tgt.is_active = TRUE
                WHERE e.workspace_id = :workspace_id
                  AND e.src_id IN :node_ids
                  AND e.tgt_id IN :node_ids
                ORDER BY e.weight DESC, e.id ASC
                LIMIT :max_edges
                """
            ).bindparams(bindparam("node_ids", expanding=True)),
            {
                "workspace_id": workspace_id,
                "node_ids": [int(row["concept_id"]) for row in node_rows],
                "max_edges": max_edges,
            },
        )
        .mappings()
        .all()
    )
    return {
        "workspace_id": workspace_id,
        "root_concept_id": concept_id,
        "max_hops": max_hops,
        "nodes": [
            {
                "concept_id": int(r["concept_id"]),
                "canonical_name": str(r["canonical_name"]),
                "description": str(r["description"] or ""),
                "hop_distance": int(r["hop_distance"]),
            }
            for r in node_rows
        ],
        "edges": [
            {
                "edge_id": int(r["edge_id"]),
                "src_concept_id": int(r["src_id"]),
                "tgt_concept_id": int(r["tgt_id"]),
                "relation_type": str(r["relation_type"]),
                "description": str(r["description"] or ""),
                "keywords": [str(k) for k in (r["keywords"] or [])],
                "weight": float(r["weight"]),
            }
            for r in edge_rows
        ],
    }


def pick_lucky(
    session: Session,
    *,
    workspace_id: int,
    concept_id: int,
    mode: Literal["adjacent", "wildcard"],
    k_hops: int,
) -> dict[str, Any]:
    row = _pick_adjacent(session, workspace_id, concept_id, k_hops)
    if mode == "wildcard":
        row = _pick_wildcard(session, workspace_id, concept_id, k_hops)
    if row is None:
        raise LuckyNoCandidateError(f"No {mode} candidate found.")

    pick: dict[str, Any]
    if mode == "adjacent":
        pick = {
            "concept_id": int(row["concept_id"]),
            "canonical_name": str(row["canonical_name"]),
            "description": str(row["description"] or ""),
            "hop_distance": int(row["hop_distance"]),
            "score_components": {
                "hop_distance": int(row["hop_distance"]),
                "strongest_link_weight": float(row["strongest_link_weight"]),
            },
        }
    else:
        pick = {
            "concept_id": int(row["concept_id"]),
            "canonical_name": str(row["canonical_name"]),
            "description": str(row["description"] or ""),
            "hop_distance": None,
            "score_components": {
                "degree": int(row["degree"]),
                "total_incident_weight": float(row["total_incident_weight"]),
            },
        }
    return {"workspace_id": workspace_id, "seed_concept_id": concept_id, "mode": mode, "pick": pick}


def _pick_adjacent(session: Session, workspace_id: int, concept_id: int, k_hops: int):
    return (
        session.execute(
            text(
                _RANKED_REACH_CTE
                + """
                SELECT
                    ranked.concept_id,
                    c.canonical_name,
                    c.description,
                    ranked.hop_distance,
                    COALESCE((
                        SELECT max(e.weight)
                        FROM edges_canon e
                        JOIN ranked prev
                          ON prev.concept_id = CASE
                                WHEN e.src_id = ranked.concept_id THEN e.tgt_id
                                ELSE e.src_id
                             END
                        WHERE e.workspace_id = :workspace_id
                          AND (e.src_id = ranked.concept_id OR e.tgt_id = ranked.concept_id)
                          AND prev.hop_distance < ranked.hop_distance
                    ), 0.0) AS strongest_link_weight
                FROM ranked
                JOIN concepts_canon c
                  ON c.id = ranked.concept_id
                 AND c.workspace_id = :workspace_id
                 AND c.is_active = TRUE
                WHERE ranked.concept_id <> :concept_id
                ORDER BY ranked.hop_distance ASC, strongest_link_weight DESC, ranked.concept_id ASC
                LIMIT 1
                """
            ),
            {"workspace_id": workspace_id, "concept_id": concept_id, "hop_limit": k_hops},
        )
        .mappings()
        .first()
    )


def _pick_wildcard(session: Session, workspace_id: int, concept_id: int, k_hops: int):
    return (
        session.execute(
            text(
                _RANKED_REACH_CTE
                + """
                , metrics AS (
                    SELECT
                        c.id AS concept_id,
                        c.canonical_name,
                        c.description,
                        count(e.id) FILTER (WHERE other.id IS NOT NULL) AS degree,
                        COALESCE(sum(e.weight) FILTER (WHERE other.id IS NOT NULL), 0.0)
                            AS total_incident_weight
                    FROM concepts_canon c
                    LEFT JOIN edges_canon e
                      ON e.workspace_id = :workspace_id
                     AND (e.src_id = c.id OR e.tgt_id = c.id)
                    LEFT JOIN concepts_canon other
                      ON other.workspace_id = :workspace_id
                     AND other.is_active = TRUE
                     AND other.id = CASE WHEN e.src_id = c.id THEN e.tgt_id ELSE e.src_id END
                    WHERE c.workspace_id = :workspace_id
                      AND c.is_active = TRUE
                      AND c.id NOT IN (
                        SELECT concept_id FROM ranked WHERE hop_distance <= :hop_limit
                      )
                    GROUP BY c.id, c.canonical_name, c.description
                )
                SELECT concept_id, canonical_name, description, degree, total_incident_weight
                FROM metrics
                WHERE degree > 0
                ORDER BY degree DESC, total_incident_weight DESC, concept_id ASC
                LIMIT 1
                """
            ),
            {"workspace_id": workspace_id, "concept_id": concept_id, "hop_limit": k_hops},
        )
        .mappings()
        .first()
    )
