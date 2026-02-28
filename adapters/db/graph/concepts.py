"""Canonical concept CRUD operations."""

from __future__ import annotations

import json
from collections.abc import Sequence

from domain.graph.types import ExtractedConcept
from sqlalchemy import text
from sqlalchemy.orm import Session

from adapters.db.graph import (
    CanonicalConceptRow,
    _to_canonical_concept,
    _to_canonical_concept_required,
    _vector_literal,
)


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
