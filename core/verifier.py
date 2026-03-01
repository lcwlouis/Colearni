"""Citation validation and grounding policy enforcement."""

from __future__ import annotations

from core.schemas import (
    CITATION_LABEL_FROM_NOTES,
    CITATION_LABEL_GENERAL_CONTEXT,
    AssistantDraft,
    AssistantResponseEnvelope,
    AssistantResponseKind,
    Citation,
    EvidenceItem,
    EvidenceSourceType,
    GroundingMode,
)


class CitationValidationError(ValueError):
    """Raised when citations cannot be validated against evidence."""


def _expected_label(source_type: EvidenceSourceType) -> str:
    if source_type == EvidenceSourceType.WORKSPACE:
        return CITATION_LABEL_FROM_NOTES
    return CITATION_LABEL_GENERAL_CONTEXT


def validate_citations(evidence: list[EvidenceItem], citations: list[Citation]) -> None:
    """Validate citation references and source labels."""
    evidence_by_id: dict[str, EvidenceItem] = {}
    for item in evidence:
        if item.evidence_id in evidence_by_id:
            raise CitationValidationError(f"Duplicate evidence_id: {item.evidence_id}")
        evidence_by_id[item.evidence_id] = item

    seen_citation_ids: set[str] = set()
    for citation in citations:
        if citation.citation_id in seen_citation_ids:
            raise CitationValidationError(f"Duplicate citation_id: {citation.citation_id}")
        seen_citation_ids.add(citation.citation_id)

        evidence_item = evidence_by_id.get(citation.evidence_id)
        if evidence_item is None:
            raise CitationValidationError(
                f"Citation '{citation.citation_id}' references unknown evidence_id "
                f"'{citation.evidence_id}'"
            )

        expected = _expected_label(evidence_item.source_type)
        if citation.label != expected:
            raise CitationValidationError(
                f"Citation '{citation.citation_id}' has label '{citation.label}' but expected "
                f"'{expected}' for source_type '{evidence_item.source_type.value}'"
            )


def verify_assistant_draft(
    draft: AssistantDraft,
    grounding_mode: GroundingMode,
    *,
    allow_uncited_hybrid: bool = False,
) -> AssistantResponseEnvelope:
    """Convert a draft into a policy-compliant response envelope."""
    if allow_uncited_hybrid and grounding_mode == GroundingMode.HYBRID and not draft.citations:
        return AssistantResponseEnvelope(
            kind=AssistantResponseKind.ANSWER,
            text=draft.text,
            grounding_mode=grounding_mode,
            evidence=draft.evidence,
            citations=draft.citations,
            response_mode="clarify",
        )

    if not draft.citations:
        if grounding_mode == GroundingMode.STRICT:
            return _build_insufficient_evidence_refusal(
                grounding_mode=grounding_mode,
                evidence=draft.evidence,
            )
        return _build_invalid_citations_refusal(
            grounding_mode=grounding_mode,
            evidence=draft.evidence,
        )

    try:
        validate_citations(evidence=draft.evidence, citations=draft.citations)
    except CitationValidationError:
        return _build_invalid_citations_refusal(
            grounding_mode=grounding_mode,
            evidence=draft.evidence,
        )

    evidence_by_id = {item.evidence_id: item for item in draft.evidence}
    if grounding_mode == GroundingMode.STRICT:
        has_workspace_citation = any(
            evidence_by_id[citation.evidence_id].source_type == EvidenceSourceType.WORKSPACE
            for citation in draft.citations
        )
        if not has_workspace_citation:
            return _build_insufficient_evidence_refusal(
                grounding_mode=grounding_mode,
                evidence=draft.evidence,
            )

    return AssistantResponseEnvelope(
        kind=AssistantResponseKind.ANSWER,
        text=draft.text,
        grounding_mode=grounding_mode,
        evidence=draft.evidence,
        citations=draft.citations,
    )


def _build_insufficient_evidence_refusal(
    *,
    grounding_mode: GroundingMode,
    evidence: list[EvidenceItem],
) -> AssistantResponseEnvelope:
    return AssistantResponseEnvelope(
        kind=AssistantResponseKind.REFUSAL,
        text=(
            "I do not have enough cited material from your notes to answer in strict grounded "
            "mode. Upload relevant documents or point me to a source in your workspace."
        ),
        grounding_mode=grounding_mode,
        evidence=evidence,
        citations=[],
        refusal_reason="insufficient_evidence",
    )


def _build_invalid_citations_refusal(
    *,
    grounding_mode: GroundingMode,
    evidence: list[EvidenceItem],
) -> AssistantResponseEnvelope:
    return AssistantResponseEnvelope(
        kind=AssistantResponseKind.REFUSAL,
        text=(
            "I could not validate citations for this response. Please retry with valid, "
            "source-linked evidence."
        ),
        grounding_mode=grounding_mode,
        evidence=evidence,
        citations=[],
        refusal_reason="invalid_citations",
    )


__all__ = ["CitationValidationError", "validate_citations", "verify_assistant_draft"]
