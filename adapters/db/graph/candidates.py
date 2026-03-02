"""Candidate listing for resolution (lexical + vector)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from adapters.db.graph import CanonicalCandidateRow, _vector_literal


def list_lexical_candidates(
    session: Session,
    *,
    workspace_id: int,
    alias: str,
    top_k: int,
) -> list[CanonicalCandidateRow]:
    """Return lexical top-k candidates by trigram similarity."""
    if top_k < 1:
        raise ValueError("top_k must be >= 1")

    rows = (
        session.execute(
            text(
                """
                SELECT
                    c.id,
                    c.canonical_name,
                    c.description,
                    c.aliases,
                    GREATEST(
                        similarity(c.canonical_name, :alias),
                        COALESCE(
                            (
                                SELECT max(similarity(alias_item, :alias))
                                FROM unnest(c.aliases) AS alias_item
                            ),
                            0
                        )
                    ) AS lexical_similarity
                FROM concepts_canon c
                WHERE c.workspace_id = :workspace_id
                  AND c.is_active = TRUE
                ORDER BY lexical_similarity DESC, c.id ASC
                LIMIT :top_k
                """
            ),
            {"workspace_id": workspace_id, "alias": alias, "top_k": top_k},
        )
        .mappings()
        .all()
    )
    return [
        CanonicalCandidateRow(
            id=int(row["id"]),
            canonical_name=str(row["canonical_name"]),
            description=str(row["description"] or ""),
            aliases=[str(alias_item) for alias_item in (row["aliases"] or [])],
            lexical_similarity=float(row["lexical_similarity"]),
            vector_similarity=None,
        )
        for row in rows
    ]


def list_vector_candidates(
    session: Session,
    *,
    workspace_id: int,
    query_embedding: Sequence[float],
    top_k: int,
) -> list[CanonicalCandidateRow]:
    """Return vector top-k candidates by cosine similarity."""
    if top_k < 1:
        raise ValueError("top_k must be >= 1")

    rows = (
        session.execute(
            text(
                """
                SELECT
                    id,
                    canonical_name,
                    description,
                    aliases,
                    (1 - (embedding <=> CAST(:query_embedding AS vector))) AS vector_similarity
                FROM concepts_canon
                WHERE workspace_id = :workspace_id
                  AND is_active = TRUE
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:query_embedding AS vector), id ASC
                LIMIT :top_k
                """
            ),
            {
                "workspace_id": workspace_id,
                "query_embedding": _vector_literal(query_embedding),
                "top_k": top_k,
            },
        )
        .mappings()
        .all()
    )
    return [
        CanonicalCandidateRow(
            id=int(row["id"]),
            canonical_name=str(row["canonical_name"]),
            description=str(row["description"] or ""),
            aliases=[str(alias_item) for alias_item in (row["aliases"] or [])],
            lexical_similarity=None,
            vector_similarity=float(row["vector_similarity"]),
        )
        for row in rows
    ]


def list_neighbors_for_concepts(
    session: Session,
    *,
    workspace_id: int,
    concept_ids: list[int],
    max_neighbors: int = 10,
) -> dict[int, list[str]]:
    """Return {concept_id: [neighbor_name, ...]} for each concept."""
    if not concept_ids:
        return {}

    result: dict[int, list[str]] = defaultdict(list)
    rows = (
        session.execute(
            text(
                """
                SELECT
                    q.concept_id,
                    c2.canonical_name
                FROM (
                    SELECT :workspace_id AS workspace_id,
                           unnest(CAST(:concept_ids AS int[])) AS concept_id
                ) q
                JOIN LATERAL (
                    SELECT DISTINCT c2.canonical_name
                    FROM edges_canon e
                    JOIN concepts_canon c2
                      ON c2.workspace_id = e.workspace_id
                      AND (
                        (c2.id = e.src_id AND e.tgt_id = q.concept_id)
                        OR (c2.id = e.tgt_id AND e.src_id = q.concept_id)
                      )
                    WHERE e.workspace_id = q.workspace_id
                      AND c2.is_active = TRUE
                    LIMIT :max_neighbors
                ) c2 ON TRUE
                """
            ),
            {
                "workspace_id": workspace_id,
                "concept_ids": concept_ids,
                "max_neighbors": max_neighbors,
            },
        )
        .mappings()
        .all()
    )
    for row in rows:
        result[int(row["concept_id"])].append(str(row["canonical_name"]))
    return dict(result)
