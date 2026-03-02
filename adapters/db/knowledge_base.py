"""Knowledge-base persistence layer – document listing and cascade deletion."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def list_documents_with_counts(
    db: Session,
    *,
    workspace_id: int,
) -> list[dict[str, Any]]:
    """List all documents in a workspace with chunk and graph concept counts."""
    rows = (
        db.execute(
            text(
                """
                SELECT
                    d.id,
                    d.public_id,
                    d.title,
                    d.summary,
                    d.source_uri,
                    d.created_at,
                    d.ingestion_status,
                    d.graph_status,
                    d.error_message,
                    COUNT(DISTINCT c.id) AS chunk_count,
                    COUNT(DISTINCT CASE WHEN p.target_type = 'concept' THEN p.target_id END) AS graph_concept_count,
                    COUNT(DISTINCT CASE WHEN p.target_type = 'concept' AND cc.tier = 'umbrella' THEN p.target_id END) AS tier_umbrella_count,
                    COUNT(DISTINCT CASE WHEN p.target_type = 'concept' AND cc.tier = 'topic' THEN p.target_id END) AS tier_topic_count,
                    COUNT(DISTINCT CASE WHEN p.target_type = 'concept' AND cc.tier = 'subtopic' THEN p.target_id END) AS tier_subtopic_count,
                    COUNT(DISTINCT CASE WHEN p.target_type = 'concept' AND cc.tier = 'granular' THEN p.target_id END) AS tier_granular_count
                FROM documents d
                LEFT JOIN chunks c ON c.document_id = d.id AND c.workspace_id = d.workspace_id
                LEFT JOIN provenance p ON p.chunk_id = c.id AND p.workspace_id = d.workspace_id
                LEFT JOIN concepts_canon cc ON p.target_type = 'concept' AND cc.id = p.target_id AND cc.workspace_id = d.workspace_id
                WHERE d.workspace_id = :workspace_id
                GROUP BY d.id
                ORDER BY d.created_at DESC
                """
            ),
            {"workspace_id": workspace_id},
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


def document_exists(
    db: Session,
    *,
    document_id: int,
    workspace_id: int,
) -> bool:
    """Check if a document exists in the workspace."""
    row = (
        db.execute(
            text(
                """
                SELECT id FROM documents
                WHERE id = :document_id AND workspace_id = :workspace_id
                LIMIT 1
                """
            ),
            {"document_id": document_id, "workspace_id": workspace_id},
        )
        .mappings()
        .first()
    )
    return row is not None


def cascade_delete_document(
    db: Session,
    *,
    document_id: int,
    workspace_id: int,
) -> None:
    """Delete a document and all dependent rows (edges_raw, concepts_raw, provenance, chunks)."""
    db.execute(
        text(
            "DELETE FROM edges_raw WHERE workspace_id = :wid AND chunk_id IN "
            "(SELECT id FROM chunks WHERE document_id = :did AND workspace_id = :wid)"
        ),
        {"wid": workspace_id, "did": document_id},
    )
    db.execute(
        text(
            "DELETE FROM concepts_raw WHERE workspace_id = :wid AND chunk_id IN "
            "(SELECT id FROM chunks WHERE document_id = :did AND workspace_id = :wid)"
        ),
        {"wid": workspace_id, "did": document_id},
    )
    db.execute(
        text(
            "DELETE FROM provenance WHERE workspace_id = :wid AND chunk_id IN "
            "(SELECT id FROM chunks WHERE document_id = :did AND workspace_id = :wid)"
        ),
        {"wid": workspace_id, "did": document_id},
    )
    db.execute(
        text("DELETE FROM chunks WHERE document_id = :did AND workspace_id = :wid"),
        {"did": document_id, "wid": workspace_id},
    )
    db.execute(
        text("DELETE FROM documents WHERE id = :did AND workspace_id = :wid"),
        {"did": document_id, "wid": workspace_id},
    )
