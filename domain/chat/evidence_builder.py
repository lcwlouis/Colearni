"""Evidence and citation assembly from ranked chunks."""

from __future__ import annotations

import re

from adapters.db.documents import DocumentRow, get_document_by_id
from core.schemas import (
    CITATION_LABEL_FROM_NOTES,
    AssistantResponseEnvelope,
    Citation,
    EvidenceItem,
    EvidenceSourceType,
)
from domain.retrieval.types import RankedChunk
from sqlalchemy.orm import Session


def build_workspace_evidence(
    *,
    session: Session,
    workspace_id: int,
    chunks: list[RankedChunk],
) -> list[EvidenceItem]:
    """Convert ranked chunks into evidence items with document metadata."""
    documents_by_id: dict[int, DocumentRow | None] = {}
    evidence_items: list[EvidenceItem] = []

    for index, chunk in enumerate(chunks, start=1):
        if chunk.document_id not in documents_by_id:
            documents_by_id[chunk.document_id] = get_document_by_id(
                session,
                workspace_id=workspace_id,
                document_id=chunk.document_id,
            )
        document = documents_by_id[chunk.document_id]
        content = chunk.text.strip() or chunk.text

        evidence_items.append(
            EvidenceItem(
                evidence_id=f"e{index}",
                source_type=EvidenceSourceType.WORKSPACE,
                content=content,
                document_id=chunk.document_id,
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                document_title=document.title if document is not None else None,
                source_uri=document.source_uri if document is not None else None,
                score=_clamp_score(chunk.score),
            )
        )

    return evidence_items


def build_workspace_citations(evidence: list[EvidenceItem]) -> list[Citation]:
    """Build citation list from evidence items."""
    citations: list[Citation] = []
    for index, item in enumerate(evidence, start=1):
        citations.append(
            Citation(
                citation_id=f"c{index}",
                evidence_id=item.evidence_id,
                label=CITATION_LABEL_FROM_NOTES,
                quote=_truncate(_single_line(item.content), limit=180),
            )
        )
    return citations


_EVIDENCE_REF_RE = re.compile(r"\be(\d+)\b", re.IGNORECASE)


def filter_used_citations(envelope: AssistantResponseEnvelope) -> AssistantResponseEnvelope:
    """Keep only citations/evidence whose IDs are mentioned in the response text."""
    if not envelope.citations or not envelope.evidence:
        return envelope
    referenced_ids = set(_EVIDENCE_REF_RE.findall(envelope.text))
    if not referenced_ids:
        return envelope
    used_evidence_ids = {f"e{n}" for n in referenced_ids}
    filtered_evidence = [e for e in envelope.evidence if e.evidence_id in used_evidence_ids]
    filtered_citations = [c for c in envelope.citations if c.evidence_id in used_evidence_ids]
    if not filtered_citations:
        return envelope
    return envelope.model_copy(
        update={"evidence": filtered_evidence, "citations": filtered_citations}
    )


def build_document_summaries_context(
    *,
    session: Session,
    workspace_id: int,
    chunks: list[RankedChunk],
    expanded_document_ids: list[int] | None = None,
) -> str:
    """Build a context string of document summaries referenced by retrieved chunks.

    When *expanded_document_ids* is provided (from the evidence planner),
    those IDs are merged ahead of chunk-derived IDs so planner-selected
    documents influence tutor context even when they have no matching chunks.
    """
    chunk_doc_ids = list(dict.fromkeys(c.document_id for c in chunks))
    # Merge planner-expanded IDs first, then chunk-derived, dedup, cap at 5
    if expanded_document_ids:
        merged: list[int] = list(expanded_document_ids)
        for did in chunk_doc_ids:
            if did not in merged:
                merged.append(did)
        doc_ids = merged[:5]
    else:
        doc_ids = chunk_doc_ids[:5]
    if not doc_ids:
        return ""
    summaries: list[str] = []
    for doc_id in doc_ids:
        doc = get_document_by_id(session, workspace_id=workspace_id, document_id=doc_id)
        if doc and doc.summary:
            summaries.append(f"- {doc.title}: {doc.summary}")
    return "\n".join(summaries)


def _truncate(value: str, *, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def _single_line(value: str) -> str:
    return " ".join(value.split())


def _clamp_score(score: float) -> float:
    return max(0.0, min(1.0, score))
