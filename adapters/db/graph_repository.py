"""Postgres query helpers for graph extraction/resolution persistence.

This module is now a thin facade that re-exports everything from
``adapters.db.graph``. Existing ``from adapters.db.graph_repository import X``
statements continue to work unchanged.
"""

from adapters.db.graph import (  # noqa: F401
    CanonicalCandidateRow,
    CanonicalConceptRow,
    CanonicalEdgeRepointRow,
    CanonicalEdgeRow,
    create_canonical_concept,
    deactivate_canonical_concept,
    ensure_aliases_map_to_concept,
    find_alias_match,
    find_canonical_by_name_ci,
    get_canonical_concept,
    insert_concept_merge_log_idempotent,
    insert_provenance,
    insert_raw_concepts,
    insert_raw_edges,
    list_gardener_seed_concepts,
    list_lexical_candidates,
    list_neighbor_names,
    list_null_tier_concepts,
    list_vector_candidates,
    repoint_alias_map,
    repoint_edges_for_merge,
    set_canonical_concept_dirty,
    update_canonical_concept,
    upsert_canonical_edge,
    upsert_concept_merge_map,
)
