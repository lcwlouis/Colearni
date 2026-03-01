from __future__ import annotations

import random
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
                    c.tier,
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
            "tier": str(row["tier"]) if row["tier"] is not None else None,
            "degree": int(row["degree"] or 0),
        },
    }


def list_concepts(
    session: Session,
    *,
    workspace_id: int,
    user_id: int | None,
    q: str | None,
    limit: int,
) -> dict[str, Any]:
    pattern = f"%{(q or '').strip()}%"
    rows = (
        session.execute(
            text(
                """
                SELECT
                    c.id AS concept_id,
                    c.canonical_name,
                    c.description,
                    c.tier,
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
                    ) AS degree,
                    m.status AS mastery_status,
                    m.score AS mastery_score
                FROM concepts_canon c
                LEFT JOIN mastery m
                  ON m.workspace_id = c.workspace_id
                 AND m.concept_id = c.id
                 AND m.user_id = :user_id
                WHERE c.workspace_id = :workspace_id
                  AND c.is_active = TRUE
                  AND (
                        :pattern = '%%'
                        OR c.canonical_name ILIKE :pattern
                        OR EXISTS (
                            SELECT 1
                            FROM unnest(c.aliases) AS alias
                            WHERE alias ILIKE :pattern
                        )
                      )
                ORDER BY lower(c.canonical_name) ASC, c.id ASC
                LIMIT :limit
                """
            ),
            {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "pattern": pattern,
                "limit": limit,
            },
        )
        .mappings()
        .all()
    )
    return {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "concepts": [
            {
                "concept_id": int(row["concept_id"]),
                "canonical_name": str(row["canonical_name"]),
                "description": str(row["description"] or ""),
                "tier": str(row["tier"]) if row["tier"] is not None else None,
                "degree": int(row["degree"] or 0),
                "mastery_status": str(row["mastery_status"]) if row["mastery_status"] else None,
                "mastery_score": (
                    float(row["mastery_score"]) if row["mastery_score"] is not None else None
                ),
            }
            for row in rows
        ],
    }


def get_bounded_subgraph(
    session: Session,
    *,
    workspace_id: int,
    concept_id: int,
    max_hops: int,
    max_nodes: int,
    max_edges: int,
    user_id: int | None = None,
) -> dict[str, Any]:
    node_rows = (
        session.execute(
            text(
                _RANKED_REACH_CTE
                + """
                SELECT
                    ranked.concept_id,
                    ranked.hop_distance,
                    c.canonical_name,
                    c.description,
                    c.tier,
                    m.status AS mastery_status,
                    m.score AS mastery_score
                FROM ranked
                JOIN concepts_canon c
                  ON c.id = ranked.concept_id
                 AND c.workspace_id = :workspace_id
                 AND c.is_active = TRUE
                LEFT JOIN mastery m
                  ON m.workspace_id = c.workspace_id
                 AND m.concept_id = c.id
                 AND m.user_id = :user_id
                ORDER BY ranked.hop_distance ASC, lower(c.canonical_name) ASC, ranked.concept_id ASC
                LIMIT :max_nodes
                """
            ),
            {
                "workspace_id": workspace_id,
                "concept_id": concept_id,
                "hop_limit": max_hops,
                "max_nodes": max_nodes,
                "user_id": user_id,
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
                "tier": str(r["tier"]) if r["tier"] is not None else None,
                "hop_distance": int(r["hop_distance"]),
                "mastery_status": str(r["mastery_status"]) if r["mastery_status"] else None,
                "mastery_score": (
                    float(r["mastery_score"]) if r["mastery_score"] is not None else None
                ),
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


def get_full_subgraph(
    session: Session,
    *,
    workspace_id: int,
    max_nodes: int,
    max_edges: int,
    user_id: int | None = None,
) -> dict[str, Any]:
    # Count total concepts for truncation detection
    total_row = (
        session.execute(
            text(
                """
                SELECT count(*) AS cnt
                FROM concepts_canon c
                WHERE c.workspace_id = :workspace_id
                  AND c.is_active = TRUE
                """
            ),
            {"workspace_id": workspace_id},
        )
        .mappings()
        .first()
    )
    total_concept_count = int(total_row["cnt"]) if total_row else 0

    node_rows = (
        session.execute(
            text(
                """
                SELECT
                    c.id AS concept_id,
                    c.canonical_name,
                    c.description,
                    c.tier,
                    m.status AS mastery_status,
                    m.score AS mastery_score,
                    (
                        SELECT count(*) FROM edges_canon e 
                        WHERE e.workspace_id = :workspace_id AND (e.src_id = c.id OR e.tgt_id = c.id)
                    ) as degree
                FROM concepts_canon c
                LEFT JOIN mastery m
                  ON m.workspace_id = c.workspace_id
                 AND m.concept_id = c.id
                 AND m.user_id = :user_id
                WHERE c.workspace_id = :workspace_id
                  AND c.is_active = TRUE
                ORDER BY degree DESC, c.id ASC
                LIMIT :max_nodes
                """
            ),
            {
                "workspace_id": workspace_id,
                "max_nodes": max_nodes,
                "user_id": user_id,
            },
        )
        .mappings()
        .all()
    )

    if not node_rows:
        return {
            "workspace_id": workspace_id,
            "root_concept_id": None,
            "max_hops": None,
            "nodes": [],
            "edges": [],
            "is_truncated": False,
            "total_concept_count": total_concept_count,
        }

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
    is_truncated = len(node_rows) >= max_nodes or total_concept_count > max_nodes
    return {
        "workspace_id": workspace_id,
        "root_concept_id": None,
        "max_hops": None,
        "is_truncated": is_truncated,
        "total_concept_count": total_concept_count,
        "nodes": [
            {
                "concept_id": int(r["concept_id"]),
                "canonical_name": str(r["canonical_name"]),
                "description": str(r["description"] or ""),
                "tier": str(r["tier"]) if r["tier"] is not None else None,
                "hop_distance": 0,
                "mastery_status": str(r["mastery_status"]) if r["mastery_status"] else None,
                "mastery_score": (
                    float(r["mastery_score"]) if r["mastery_score"] is not None else None
                ),
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


def get_ancestor_chain(
    session: Session,
    *,
    workspace_id: int,
    concept_id: int,
    max_depth: int = 3,
) -> list[dict[str, str]]:
    """Return the ancestor chain for a concept via hierarchy edges.

    Walks upward through ``belongs_to`` and ``has_subtopic`` edges (reversed)
    in ``edges_canon`` up to *max_depth* hops. Returns a list of dicts with
    ``concept_id``, ``canonical_name``, and ``description``, ordered from
    immediate parent to most distant ancestor.

    Returns an empty list if no hierarchical edges are found or the concept
    has no ancestors.
    """
    rows = (
        session.execute(
            text(
                """
                WITH RECURSIVE ancestors AS (
                    SELECT CAST(:concept_id AS bigint) AS concept_id,
                           CAST(0 AS integer) AS hop_distance

                    UNION ALL

                    SELECT
                        CASE
                            WHEN e.relation_type = 'belongs_to' AND e.src_id = ancestors.concept_id
                                THEN e.tgt_id
                            WHEN e.relation_type = 'has_subtopic' AND e.tgt_id = ancestors.concept_id
                                THEN e.src_id
                        END AS concept_id,
                        ancestors.hop_distance + 1 AS hop_distance
                    FROM ancestors
                    JOIN edges_canon e
                      ON e.workspace_id = :workspace_id
                     AND e.relation_type IN ('belongs_to', 'has_subtopic')
                     AND (
                           (e.relation_type = 'belongs_to' AND e.src_id = ancestors.concept_id)
                           OR
                           (e.relation_type = 'has_subtopic' AND e.tgt_id = ancestors.concept_id)
                         )
                    WHERE ancestors.hop_distance < :max_depth
                ),
                ranked AS (
                    SELECT concept_id, min(hop_distance) AS hop_distance
                    FROM ancestors
                    WHERE concept_id <> CAST(:concept_id AS bigint)
                    GROUP BY concept_id
                )
                SELECT
                    ranked.concept_id,
                    ranked.hop_distance,
                    c.canonical_name,
                    c.description,
                    c.tier
                FROM ranked
                JOIN concepts_canon c
                  ON c.id = ranked.concept_id
                 AND c.workspace_id = :workspace_id
                 AND c.is_active = TRUE
                ORDER BY ranked.hop_distance ASC
                """
            ),
            {"workspace_id": workspace_id, "concept_id": concept_id, "max_depth": max_depth},
        )
        .mappings()
        .all()
    )
    if not rows:
        return []
    return [
        {
            "concept_id": str(row["concept_id"]),
            "canonical_name": str(row["canonical_name"]),
            "description": str(row["description"] or ""),
            "tier": str(row["tier"]) if row["tier"] is not None else None,
        }
        for row in rows
    ]


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
    candidates = (
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
                LIMIT 5
                """
            ),
            {"workspace_id": workspace_id, "concept_id": concept_id, "hop_limit": k_hops},
        )
        .mappings()
        .all()
    )
    if not candidates:
        return None
    return random.choice(candidates)


def _pick_wildcard(session: Session, workspace_id: int, concept_id: int, k_hops: int):
    candidates = (
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
                LIMIT 5
                """
            ),
            {"workspace_id": workspace_id, "concept_id": concept_id, "hop_limit": k_hops},
        )
        .mappings()
        .all()
    )
    if not candidates:
        return None
    return random.choice(candidates)