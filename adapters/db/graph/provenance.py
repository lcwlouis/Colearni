"""Provenance recording."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


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
