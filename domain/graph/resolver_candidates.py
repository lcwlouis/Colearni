"""Candidate combination and ranking for concept resolution."""

from __future__ import annotations

from collections.abc import Sequence

from adapters.db import graph_repository
from domain.graph.types import CanonicalCandidate


def combine_candidates(
    *,
    lexical_rows: Sequence[graph_repository.CanonicalCandidateRow],
    vector_rows: Sequence[graph_repository.CanonicalCandidateRow],
    candidate_cap: int,
) -> list[CanonicalCandidate]:
    """Combine lexical and vector candidate rows into a ranked list."""
    by_id: dict[int, CanonicalCandidate] = {}

    for row in lexical_rows:
        by_id[row.id] = CanonicalCandidate(
            concept_id=row.id,
            canonical_name=row.canonical_name,
            description=row.description,
            aliases=tuple(row.aliases),
            lexical_similarity=row.lexical_similarity,
            vector_similarity=None,
        )

    for row in vector_rows:
        existing = by_id.get(row.id)
        if existing is None:
            by_id[row.id] = CanonicalCandidate(
                concept_id=row.id,
                canonical_name=row.canonical_name,
                description=row.description,
                aliases=tuple(row.aliases),
                lexical_similarity=None,
                vector_similarity=row.vector_similarity,
            )
            continue
        by_id[row.id] = CanonicalCandidate(
            concept_id=existing.concept_id,
            canonical_name=existing.canonical_name,
            description=existing.description,
            aliases=existing.aliases,
            lexical_similarity=existing.lexical_similarity,
            vector_similarity=row.vector_similarity,
        )

    ranked_candidates = sorted(
        by_id.values(),
        key=lambda candidate: (
            max(
                candidate.lexical_similarity or 0.0,
                candidate.vector_similarity or 0.0,
            ),
            candidate.lexical_similarity or -1.0,
            candidate.vector_similarity or -1.0,
            -candidate.concept_id,
        ),
        reverse=True,
    )
    return ranked_candidates[:candidate_cap]
