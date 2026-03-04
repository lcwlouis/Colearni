"""Practice novelty engine – fingerprinting and dedup for quiz/flashcard items."""

from __future__ import annotations

import hashlib

from sqlalchemy import text
from sqlalchemy.orm import Session


def fingerprint_text(text_value: str) -> str:
    """Produce a SHA-256 fingerprint for dedup purposes."""
    return hashlib.sha256(text_value.strip().lower().encode("utf-8")).hexdigest()


def load_existing_fingerprints(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    concept_id: int,
    item_type: str,
) -> set[str]:
    """Return fingerprints of items the user has already seen for this concept."""
    rows = session.execute(
        text(
            """
            SELECT fingerprint
            FROM practice_item_history
            WHERE workspace_id = :workspace_id
              AND user_id = :user_id
              AND concept_id = :concept_id
              AND item_type = :item_type
            """
        ),
        {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "concept_id": concept_id,
            "item_type": item_type,
        },
    ).all()
    return {str(row[0]) for row in rows}


def record_item_fingerprints(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    concept_id: int,
    item_type: str,
    fingerprints: list[str],
) -> None:
    """Record fingerprints so future generations avoid duplicates."""
    for fp in fingerprints:
        session.execute(
            text(
                """
                INSERT INTO practice_item_history
                    (workspace_id, user_id, concept_id, item_type, fingerprint)
                VALUES (:workspace_id, :user_id, :concept_id, :item_type, :fingerprint)
                """
            ),
            {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "concept_id": concept_id,
                "item_type": item_type,
                "fingerprint": fp,
            },
        )
