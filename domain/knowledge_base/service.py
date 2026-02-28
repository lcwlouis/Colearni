"""Knowledge-base domain service – document listing, deletion, reprocessing."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from adapters.db import knowledge_base as kb_db
from adapters.db.documents import update_document_status
from core.schemas.knowledge_base import KBDocumentListResponse, KBDocumentSummary
from domain.graph.orphan_pruner import prune_orphan_graph_nodes

_log = logging.getLogger("colearni.domain.knowledge_base")


class DocumentNotFoundError(Exception):
    """Raised when a document lookup fails."""


def list_documents(
    db: Session,
    *,
    workspace_id: int,
    graph_enabled: bool = False,
) -> KBDocumentListResponse:
    """List KB documents with chunk counts and effective graph status."""
    rows = kb_db.list_documents_with_counts(db, workspace_id=workspace_id)

    def _effective_graph_status(row_status: str | None) -> str:
        if not graph_enabled:
            return "disabled"
        return row_status or "pending"

    return KBDocumentListResponse(
        workspace_id=workspace_id,
        documents=[
            KBDocumentSummary(
                document_id=int(row["id"]),
                public_id=str(row["public_id"]),
                title=str(row["title"]) if row["title"] else None,
                summary=str(row["summary"]) if row["summary"] else None,
                source_uri=str(row["source_uri"]) if row["source_uri"] else None,
                chunk_count=int(row["chunk_count"]),
                ingestion_status=row["ingestion_status"] or "pending",
                graph_status=_effective_graph_status(row.get("graph_status")),
                graph_concept_count=int(row["graph_concept_count"]),
                created_at=row["created_at"],
                error_message=str(row["error_message"]) if row.get("error_message") else None,
            )
            for row in rows
        ],
    )


def delete_document(
    db: Session,
    *,
    document_id: int,
    workspace_id: int,
    prune_orphan_graph: bool = False,
) -> None:
    """Delete a document and cascade. Raises DocumentNotFoundError if missing."""
    if not kb_db.document_exists(db, document_id=document_id, workspace_id=workspace_id):
        raise DocumentNotFoundError

    kb_db.cascade_delete_document(db, document_id=document_id, workspace_id=workspace_id)

    if prune_orphan_graph:
        prune_orphan_graph_nodes(db, workspace_id=workspace_id)

    db.commit()


def reset_document_for_reprocess(
    db: Session,
    *,
    document_id: int,
    workspace_id: int,
) -> None:
    """Reset a document's graph status to prepare for reprocessing.

    Raises DocumentNotFoundError if the document is missing.
    """
    if not kb_db.document_exists(db, document_id=document_id, workspace_id=workspace_id):
        raise DocumentNotFoundError

    update_document_status(
        db,
        workspace_id=workspace_id,
        document_id=document_id,
        graph_status="pending",
        error_message="",
    )
    db.commit()
