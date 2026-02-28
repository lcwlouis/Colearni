"""Candidate listing for resolution (lexical + vector)."""

from __future__ import annotations

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
