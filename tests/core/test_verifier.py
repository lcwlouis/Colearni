"""Unit tests for citation verification policy."""

from core.schemas import (
    CITATION_LABEL_FROM_NOTES,
    CITATION_LABEL_GENERAL_CONTEXT,
    AssistantDraft,
    AssistantResponseKind,
    Citation,
    EvidenceItem,
    EvidenceSourceType,
    GroundingMode,
)
from core.verifier import verify_assistant_draft


def test_strict_mode_accepts_workspace_citations() -> None:
    """Strict mode accepts answers grounded in workspace evidence."""
    draft = AssistantDraft(
        text="grounded response",
        evidence=[
            EvidenceItem(
                evidence_id="e1",
                source_type=EvidenceSourceType.WORKSPACE,
                content="workspace snippet",
                document_id=1,
                chunk_id=2,
                chunk_index=0,
            )
        ],
        citations=[
            Citation(
                citation_id="c1",
                evidence_id="e1",
                label=CITATION_LABEL_FROM_NOTES,
            )
        ],
    )

    envelope = verify_assistant_draft(draft=draft, grounding_mode=GroundingMode.STRICT)

    assert envelope.kind == AssistantResponseKind.ANSWER
    assert envelope.refusal_reason is None
    assert envelope.grounding_mode == GroundingMode.STRICT


def test_strict_mode_refuses_without_workspace_citations() -> None:
    """Strict mode refuses if only general-context citations are present."""
    draft = AssistantDraft(
        text="general response",
        evidence=[
            EvidenceItem(
                evidence_id="e1",
                source_type=EvidenceSourceType.GENERAL,
                content="general context snippet",
            )
        ],
        citations=[
            Citation(
                citation_id="c1",
                evidence_id="e1",
                label=CITATION_LABEL_GENERAL_CONTEXT,
            )
        ],
    )

    envelope = verify_assistant_draft(draft=draft, grounding_mode=GroundingMode.STRICT)

    assert envelope.kind == AssistantResponseKind.REFUSAL
    assert envelope.refusal_reason == "insufficient_evidence"


def test_strict_mode_refuses_when_citations_are_missing() -> None:
    """Strict mode refuses uncited drafts as insufficient evidence."""
    draft = AssistantDraft(
        text="response without citations",
        evidence=[],
        citations=[],
    )

    envelope = verify_assistant_draft(draft=draft, grounding_mode=GroundingMode.STRICT)

    assert envelope.kind == AssistantResponseKind.REFUSAL
    assert envelope.refusal_reason == "insufficient_evidence"


def test_hybrid_mode_allows_general_context_citations() -> None:
    """Hybrid mode permits general-context evidence when it is labeled correctly."""
    draft = AssistantDraft(
        text="general-context response",
        evidence=[
            EvidenceItem(
                evidence_id="e1",
                source_type=EvidenceSourceType.GENERAL,
                content="general context snippet",
            )
        ],
        citations=[
            Citation(
                citation_id="c1",
                evidence_id="e1",
                label=CITATION_LABEL_GENERAL_CONTEXT,
            )
        ],
    )

    envelope = verify_assistant_draft(draft=draft, grounding_mode=GroundingMode.HYBRID)

    assert envelope.kind == AssistantResponseKind.ANSWER
    assert envelope.refusal_reason is None


def test_invalid_citation_reference_returns_refusal() -> None:
    """Verifier should refuse when a citation points to missing evidence."""
    draft = AssistantDraft(
        text="bad citations",
        evidence=[
            EvidenceItem(
                evidence_id="e1",
                source_type=EvidenceSourceType.WORKSPACE,
                content="workspace snippet",
                document_id=1,
                chunk_id=2,
                chunk_index=0,
            )
        ],
        citations=[
            Citation(
                citation_id="c1",
                evidence_id="missing",
                label=CITATION_LABEL_FROM_NOTES,
            )
        ],
    )

    envelope = verify_assistant_draft(draft=draft, grounding_mode=GroundingMode.HYBRID)

    assert envelope.kind == AssistantResponseKind.REFUSAL
    assert envelope.refusal_reason == "invalid_citations"


def test_label_source_mismatch_returns_refusal() -> None:
    """Verifier should refuse if citation label doesn't match evidence source type."""
    draft = AssistantDraft(
        text="mismatched labels",
        evidence=[
            EvidenceItem(
                evidence_id="e1",
                source_type=EvidenceSourceType.WORKSPACE,
                content="workspace snippet",
                document_id=1,
                chunk_id=2,
                chunk_index=0,
            )
        ],
        citations=[
            Citation(
                citation_id="c1",
                evidence_id="e1",
                label=CITATION_LABEL_GENERAL_CONTEXT,
            )
        ],
    )

    envelope = verify_assistant_draft(draft=draft, grounding_mode=GroundingMode.HYBRID)

    assert envelope.kind == AssistantResponseKind.REFUSAL
    assert envelope.refusal_reason == "invalid_citations"
