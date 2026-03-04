"""Merge-map and merge-log operations."""

from __future__ import annotations

from collections.abc import Sequence

from domain.graph.types import normalize_alias
from sqlalchemy import text
from sqlalchemy.orm import Session


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
