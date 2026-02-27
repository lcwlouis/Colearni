"""Postgres query helpers for graph extraction/resolution persistence."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass

from domain.graph.types import (
    ExtractedConcept,
    ExtractedEdge,
    dedupe_keywords,
    normalize_alias,
    truncate_text,
)
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session


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


def insert_raw_concepts(
    session: Session,
    *,
    workspace_id: int,
    chunk_id: int,
    concepts: Sequence[ExtractedConcept],
) -> int:
    """Insert raw concepts for a chunk and return inserted count."""
    if not concepts:
        return 0

    rows = [
        {
            "workspace_id": workspace_id,
            "chunk_id": chunk_id,
            "name": concept.name,
            "context_snippet": concept.context_snippet,
            "extracted_json": json.dumps({"description": concept.description}),
        }
        for concept in concepts
    ]
    session.execute(
        text(
            """
            INSERT INTO concepts_raw (
                workspace_id,
                chunk_id,
                name,
                context_snippet,
                extracted_json
            )
            VALUES (
                :workspace_id,
                :chunk_id,
                :name,
                :context_snippet,
                CAST(:extracted_json AS jsonb)
            )
            """
        ),
        rows,
    )
    return len(rows)


def insert_raw_edges(
    session: Session,
    *,
    workspace_id: int,
    chunk_id: int,
    edges: Sequence[ExtractedEdge],
) -> int:
    """Insert raw edges for a chunk and return inserted count."""
    if not edges:
        return 0

    rows = [
        {
            "workspace_id": workspace_id,
            "chunk_id": chunk_id,
            "src_name": edge.src_name,
            "tgt_name": edge.tgt_name,
            "relation_type": edge.relation_type,
            "description": edge.description,
            "keywords": edge.keywords,
            "weight": edge.weight,
        }
        for edge in edges
    ]
    session.execute(
        text(
            """
            INSERT INTO edges_raw (
                workspace_id,
                chunk_id,
                src_name,
                tgt_name,
                relation_type,
                description,
                keywords,
                weight
            )
            VALUES (
                :workspace_id,
                :chunk_id,
                :src_name,
                :tgt_name,
                :relation_type,
                :description,
                :keywords,
                :weight
            )
            """
        ),
        rows,
    )
    return len(rows)


def find_alias_match(
    session: Session,
    *,
    workspace_id: int,
    alias: str,
) -> CanonicalConceptRow | None:
    """Return exact alias-map hit for one normalized alias."""
    row = (
        session.execute(
            text(
                """
                SELECT
                    c.id,
                    c.workspace_id,
                    c.canonical_name,
                    c.description,
                    c.aliases,
                    c.embedding,
                    c.is_active,
                    c.dirty
                FROM concept_merge_map m
                JOIN concepts_canon c ON c.id = m.canon_concept_id
                WHERE m.workspace_id = :workspace_id
                  AND m.alias = :alias
                  AND c.is_active = TRUE
                LIMIT 1
                """
            ),
            {"workspace_id": workspace_id, "alias": alias},
        )
        .mappings()
        .first()
    )
    return _to_canonical_concept(row)


def find_canonical_by_name_ci(
    session: Session,
    *,
    workspace_id: int,
    canonical_name: str,
) -> CanonicalConceptRow | None:
    """Find canonical concept by case-insensitive canonical_name."""
    row = (
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
                    dirty
                FROM concepts_canon
                WHERE workspace_id = :workspace_id
                  AND is_active = TRUE
                  AND lower(canonical_name) = lower(:canonical_name)
                ORDER BY id ASC
                LIMIT 1
                """
            ),
            {"workspace_id": workspace_id, "canonical_name": canonical_name},
        )
        .mappings()
        .first()
    )
    return _to_canonical_concept(row)


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
                    dirty
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


def set_canonical_concept_dirty(
    session: Session,
    *,
    workspace_id: int,
    concept_id: int,
    dirty: bool,
) -> None:
    """Set dirty flag for one canonical concept."""
    session.execute(
        text(
            """
            UPDATE concepts_canon
            SET
                dirty = :dirty,
                updated_at = now()
            WHERE workspace_id = :workspace_id
              AND id = :concept_id
            """
        ),
        {"workspace_id": workspace_id, "concept_id": concept_id, "dirty": dirty},
    )


def insert_concept_merge_log_idempotent(
    session: Session,
    *,
    workspace_id: int,
    from_id: int,
    to_id: int,
    reason: str,
    method: str,
    confidence: float,
) -> bool:
    """Insert merge log row at most once per workspace/from/to tuple."""
    if from_id == to_id:
        return False

    inserted = session.execute(
        text(
            """
            INSERT INTO concept_merge_log (
                workspace_id,
                from_id,
                to_id,
                reason,
                method,
                confidence
            )
            SELECT
                :workspace_id,
                :from_id,
                :to_id,
                :reason,
                :method,
                :confidence
            WHERE NOT EXISTS (
                SELECT 1
                FROM concept_merge_log
                WHERE workspace_id = :workspace_id
                  AND from_id = :from_id
                  AND to_id = :to_id
            )
            RETURNING id
            """
        ),
        {
            "workspace_id": workspace_id,
            "from_id": from_id,
            "to_id": to_id,
            "reason": reason,
            "method": method,
            "confidence": confidence,
        },
    ).scalar_one_or_none()
    return inserted is not None


def deactivate_canonical_concept(
    session: Session,
    *,
    workspace_id: int,
    concept_id: int,
) -> bool:
    """Deactivate one canonical concept; returns True when state changed."""
    result = session.execute(
        text(
            """
            UPDATE concepts_canon
            SET
                is_active = FALSE,
                dirty = FALSE,
                updated_at = now()
            WHERE workspace_id = :workspace_id
              AND id = :concept_id
              AND is_active = TRUE
            """
        ),
        {"workspace_id": workspace_id, "concept_id": concept_id},
    )
    return bool(result.rowcount and result.rowcount > 0)


def repoint_alias_map(
    session: Session,
    *,
    workspace_id: int,
    from_id: int,
    to_id: int,
) -> int:
    """Repoint alias rows from one canonical concept id to another."""
    if from_id == to_id:
        return 0
    result = session.execute(
        text(
            """
            UPDATE concept_merge_map
            SET
                canon_concept_id = :to_id,
                updated_at = now()
            WHERE workspace_id = :workspace_id
              AND canon_concept_id = :from_id
            """
        ),
        {"workspace_id": workspace_id, "from_id": from_id, "to_id": to_id},
    )
    return int(result.rowcount or 0)


def ensure_aliases_map_to_concept(
    session: Session,
    *,
    workspace_id: int,
    aliases: Sequence[str],
    canon_concept_id: int,
    confidence: float,
    method: str,
) -> int:
    """Ensure each alias points at canon_concept_id through merge-map upsert."""
    upserts = 0
    seen: set[str] = set()
    for alias in aliases:
        alias_norm = normalize_alias(alias)
        if not alias_norm or alias_norm in seen:
            continue
        seen.add(alias_norm)
        upsert_concept_merge_map(
            session,
            workspace_id=workspace_id,
            alias=alias_norm,
            canon_concept_id=canon_concept_id,
            confidence=confidence,
            method=method,
        )
        upserts += 1
    return upserts


def repoint_edges_for_merge(
    session: Session,
    *,
    workspace_id: int,
    from_id: int,
    to_id: int,
    weight_cap: float,
    edge_description_max_chars: int,
) -> int:
    """Move all edges touching from_id to to_id, deduping via canonical edge upsert."""
    if from_id == to_id:
        return 0

    rows = (
        session.execute(
            text(
                """
                SELECT
                    id,
                    src_id,
                    tgt_id,
                    relation_type,
                    description,
                    keywords,
                    weight
                FROM edges_canon
                WHERE workspace_id = :workspace_id
                  AND (src_id = :from_id OR tgt_id = :from_id)
                ORDER BY id ASC
                """
            ),
            {"workspace_id": workspace_id, "from_id": from_id},
        )
        .mappings()
        .all()
    )
    edges = [
        CanonicalEdgeRepointRow(
            id=int(row["id"]),
            src_id=int(row["src_id"]),
            tgt_id=int(row["tgt_id"]),
            relation_type=str(row["relation_type"]),
            description=str(row["description"] or ""),
            keywords=[str(keyword) for keyword in (row["keywords"] or [])],
            weight=float(row["weight"]),
        )
        for row in rows
    ]
    if not edges:
        return 0

    session.execute(
        text("DELETE FROM edges_canon WHERE id IN :edge_ids").bindparams(
            bindparam("edge_ids", expanding=True)
        ),
        {"edge_ids": [edge.id for edge in edges]},
    )

    upserts = 0
    for edge in edges:
        new_src = to_id if edge.src_id == from_id else edge.src_id
        new_tgt = to_id if edge.tgt_id == from_id else edge.tgt_id
        if new_src == new_tgt:
            continue
        upsert_canonical_edge(
            session,
            workspace_id=workspace_id,
            src_id=new_src,
            tgt_id=new_tgt,
            relation_type=edge.relation_type,
            description=edge.description,
            keywords=edge.keywords,
            delta_weight=edge.weight,
            weight_cap=weight_cap,
            edge_description_max_chars=edge_description_max_chars,
        )
        upserts += 1
    return upserts


def get_canonical_concept(
    session: Session,
    *,
    workspace_id: int,
    concept_id: int,
) -> CanonicalConceptRow | None:
    """Fetch one canonical concept row by workspace+id."""
    row = (
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
                    dirty
                FROM concepts_canon
                WHERE workspace_id = :workspace_id
                  AND id = :concept_id
                """
            ),
            {"workspace_id": workspace_id, "concept_id": concept_id},
        )
        .mappings()
        .first()
    )
    return _to_canonical_concept(row)


def create_canonical_concept(
    session: Session,
    *,
    workspace_id: int,
    canonical_name: str,
    description: str,
    aliases: Sequence[str],
    embedding: Sequence[float] | None,
) -> CanonicalConceptRow:
    """Create canonical concept row (dirty=true) and return it."""
    if embedding is None:
        row = (
            session.execute(
                text(
                    """
                    INSERT INTO concepts_canon (
                        workspace_id,
                        canonical_name,
                        description,
                        aliases,
                        embedding,
                        is_active,
                        dirty
                    )
                    VALUES (
                        :workspace_id,
                        :canonical_name,
                        :description,
                        :aliases,
                        NULL,
                        TRUE,
                        TRUE
                    )
                    ON CONFLICT (workspace_id, canonical_name)
                    DO UPDATE
                    SET updated_at = now()
                    RETURNING
                        id,
                        workspace_id,
                        canonical_name,
                        description,
                        aliases,
                        embedding,
                        is_active,
                        dirty
                    """
                ),
                {
                    "workspace_id": workspace_id,
                    "canonical_name": canonical_name,
                    "description": description,
                    "aliases": list(aliases),
                },
            )
            .mappings()
            .one()
        )
        return _to_canonical_concept_required(row)

    row = (
        session.execute(
            text(
                """
                INSERT INTO concepts_canon (
                    workspace_id,
                    canonical_name,
                    description,
                    aliases,
                    embedding,
                    is_active,
                    dirty
                )
                VALUES (
                    :workspace_id,
                    :canonical_name,
                    :description,
                    :aliases,
                    CAST(:embedding AS vector),
                    TRUE,
                    TRUE
                )
                ON CONFLICT (workspace_id, canonical_name)
                DO UPDATE
                SET updated_at = now()
                RETURNING
                    id,
                    workspace_id,
                    canonical_name,
                    description,
                    aliases,
                    embedding,
                    is_active,
                    dirty
                """
            ),
            {
                "workspace_id": workspace_id,
                "canonical_name": canonical_name,
                "description": description,
                "aliases": list(aliases),
                "embedding": _vector_literal(embedding),
            },
        )
        .mappings()
        .one()
    )
    return _to_canonical_concept_required(row)


def update_canonical_concept(
    session: Session,
    *,
    workspace_id: int,
    concept_id: int,
    description: str,
    aliases: Sequence[str],
    embedding: Sequence[float] | None,
    mark_dirty: bool,
) -> CanonicalConceptRow:
    """Update canonical concept fields and return latest row."""
    if embedding is None:
        row = (
            session.execute(
                text(
                    """
                    UPDATE concepts_canon
                    SET
                        description = :description,
                        aliases = :aliases,
                        dirty = :mark_dirty,
                        updated_at = now()
                    WHERE workspace_id = :workspace_id
                      AND id = :concept_id
                    RETURNING
                        id,
                        workspace_id,
                        canonical_name,
                        description,
                        aliases,
                        embedding,
                        is_active,
                        dirty
                    """
                ),
                {
                    "workspace_id": workspace_id,
                    "concept_id": concept_id,
                    "description": description,
                    "aliases": list(aliases),
                    "mark_dirty": mark_dirty,
                },
            )
            .mappings()
            .one()
        )
        return _to_canonical_concept_required(row)

    row = (
        session.execute(
            text(
                """
                UPDATE concepts_canon
                SET
                    description = :description,
                    aliases = :aliases,
                    embedding = CAST(:embedding AS vector),
                    dirty = :mark_dirty,
                    updated_at = now()
                WHERE workspace_id = :workspace_id
                  AND id = :concept_id
                RETURNING
                    id,
                    workspace_id,
                    canonical_name,
                    description,
                    aliases,
                    embedding,
                    is_active,
                    dirty
                """
            ),
            {
                "workspace_id": workspace_id,
                "concept_id": concept_id,
                "description": description,
                "aliases": list(aliases),
                "embedding": _vector_literal(embedding),
                "mark_dirty": mark_dirty,
            },
        )
        .mappings()
        .one()
    )
    return _to_canonical_concept_required(row)


def upsert_concept_merge_map(
    session: Session,
    *,
    workspace_id: int,
    alias: str,
    canon_concept_id: int,
    confidence: float,
    method: str,
) -> None:
    """Upsert alias -> canonical mapping with confidence + method."""
    session.execute(
        text(
            """
            INSERT INTO concept_merge_map (
                workspace_id,
                alias,
                canon_concept_id,
                confidence,
                method
            )
            VALUES (
                :workspace_id,
                :alias,
                :canon_concept_id,
                :confidence,
                :method
            )
            ON CONFLICT (workspace_id, alias)
            DO UPDATE
            SET
                canon_concept_id = EXCLUDED.canon_concept_id,
                confidence = EXCLUDED.confidence,
                method = EXCLUDED.method,
                updated_at = now()
            """
        ),
        {
            "workspace_id": workspace_id,
            "alias": alias,
            "canon_concept_id": canon_concept_id,
            "confidence": confidence,
            "method": method,
        },
    )


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


def upsert_canonical_edge(
    session: Session,
    *,
    workspace_id: int,
    src_id: int,
    tgt_id: int,
    relation_type: str,
    description: str,
    keywords: Sequence[str],
    delta_weight: float,
    weight_cap: float,
    edge_description_max_chars: int,
) -> int:
    """Upsert canonical edge, merging keywords/description/weight deterministically."""
    existing_row = (
        session.execute(
            text(
                """
                SELECT id, description, keywords, weight
                FROM edges_canon
                WHERE workspace_id = :workspace_id
                  AND src_id = :src_id
                  AND tgt_id = :tgt_id
                  AND relation_type = :relation_type
                """
            ),
            {
                "workspace_id": workspace_id,
                "src_id": src_id,
                "tgt_id": tgt_id,
                "relation_type": relation_type,
            },
        )
        .mappings()
        .first()
    )
    incoming_description = truncate_text(description, edge_description_max_chars)
    incoming_keywords = dedupe_keywords(list(keywords))
    incoming_weight = max(0.0, float(delta_weight))

    if existing_row is None:
        edge_id = int(
            session.execute(
                text(
                    """
                    INSERT INTO edges_canon (
                        workspace_id,
                        src_id,
                        tgt_id,
                        relation_type,
                        description,
                        keywords,
                        weight
                    )
                    VALUES (
                        :workspace_id,
                        :src_id,
                        :tgt_id,
                        :relation_type,
                        :description,
                        :keywords,
                        :weight
                    )
                    RETURNING id
                    """
                ),
                {
                    "workspace_id": workspace_id,
                    "src_id": src_id,
                    "tgt_id": tgt_id,
                    "relation_type": relation_type,
                    "description": incoming_description,
                    "keywords": incoming_keywords,
                    "weight": min(incoming_weight, weight_cap),
                },
            ).scalar_one()
        )
        return edge_id

    existing = CanonicalEdgeRow(
        id=int(existing_row["id"]),
        description=str(existing_row["description"] or ""),
        keywords=[str(keyword) for keyword in (existing_row["keywords"] or [])],
        weight=float(existing_row["weight"]),
    )
    merged_description = (
        incoming_description
        if len(incoming_description) > len(existing.description)
        else existing.description
    )
    merged_keywords = dedupe_keywords(existing.keywords + incoming_keywords)
    merged_weight = min(existing.weight + incoming_weight, weight_cap)

    session.execute(
        text(
            """
            UPDATE edges_canon
            SET
                description = :description,
                keywords = :keywords,
                weight = :weight,
                updated_at = now()
            WHERE id = :edge_id
            """
        ),
        {
            "edge_id": existing.id,
            "description": merged_description,
            "keywords": merged_keywords,
            "weight": merged_weight,
        },
    )
    return existing.id


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
        import json
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass
    if not isinstance(value, (list, tuple)):
        return None
    return [float(item) for item in value]
