"""Graph repository sub-package – split by concern.

Shared types live here; sub-modules import them from this package.
The original ``adapters.db.graph_repository`` module re-exports everything
so existing imports are unaffected.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CanonicalConceptRow:
    """Projected canonical concept row."""

    id: int
    workspace_id: int
    canonical_name: str
    description: str
    aliases: list[str]
    embedding: list[float] | None
    is_active: bool
    dirty: bool
    tier: str | None = None


@dataclass(frozen=True, slots=True)
class CanonicalCandidateRow:
    """Projected canonical candidate row with optional score signals."""

    id: int
    canonical_name: str
    description: str
    aliases: list[str]
    lexical_similarity: float | None = None
    vector_similarity: float | None = None


@dataclass(frozen=True, slots=True)
class CanonicalEdgeRow:
    """Projected canonical edge row."""

    id: int
    description: str
    keywords: list[str]
    weight: float


@dataclass(frozen=True, slots=True)
class CanonicalEdgeRepointRow:
    """Edge row used during merge repoint operations."""

    id: int
    src_id: int
    tgt_id: int
    relation_type: str
    description: str
    keywords: list[str]
    weight: float


def _vector_literal(values: Sequence[float]) -> str:
    """Serialize an embedding vector to pgvector text format."""
    if not values:
        raise ValueError("Embedding vector cannot be empty")
    return "[" + ",".join(f"{float(value):.12g}" for value in values) + "]"


def _to_canonical_concept(row: dict[str, object] | None) -> CanonicalConceptRow | None:
    if row is None:
        return None
    return CanonicalConceptRow(
        id=int(row["id"]),
        workspace_id=int(row["workspace_id"]),
        canonical_name=str(row["canonical_name"]),
        description=str(row["description"] or ""),
        aliases=[str(alias_item) for alias_item in (row["aliases"] or [])],
        embedding=_coerce_embedding(row["embedding"]),
        is_active=bool(row["is_active"]),
        dirty=bool(row["dirty"]),
        tier=str(row["tier"]) if row["tier"] is not None else None,
    )


def _to_canonical_concept_required(row: dict[str, object]) -> CanonicalConceptRow:
    concept = _to_canonical_concept(row)
    if concept is None:
        raise RuntimeError("Expected canonical concept row")
    return concept


def _coerce_embedding(value: object) -> list[float] | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass
    if not isinstance(value, (list, tuple)):
        return None
    return [float(item) for item in value]


# Re-export sub-module public functions for convenience.
from adapters.db.graph.concepts import (  # noqa: E402, F401
    create_canonical_concept,
    deactivate_canonical_concept,
    find_alias_match,
    find_canonical_by_name_ci,
    get_canonical_concept,
    insert_raw_concepts,
    set_canonical_concept_dirty,
    update_canonical_concept,
)
from adapters.db.graph.edges import (  # noqa: E402, F401
    insert_raw_edges,
    repoint_edges_for_merge,
    upsert_canonical_edge,
)
from adapters.db.graph.merge_map import (  # noqa: E402, F401
    ensure_aliases_map_to_concept,
    insert_concept_merge_log_idempotent,
    repoint_alias_map,
    upsert_concept_merge_map,
)
from adapters.db.graph.provenance import insert_provenance  # noqa: E402, F401
from adapters.db.graph.candidates import (  # noqa: E402, F401
    list_lexical_candidates,
    list_neighbors_for_concepts,
    list_vector_candidates,
)
from adapters.db.graph.gardener import list_gardener_seed_concepts, list_null_tier_concepts, list_neighbor_names  # noqa: E402, F401
