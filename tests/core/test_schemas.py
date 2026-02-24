"""Unit tests for response schema validation."""

import pytest
from core.schemas import (
    AssistantResponseEnvelope,
    AssistantResponseKind,
    EvidenceItem,
    EvidenceSourceType,
    GroundingMode,
)
from pydantic import ValidationError


def test_workspace_evidence_requires_document_chunk_metadata() -> None:
    """Workspace evidence must include document/chunk provenance IDs."""
    with pytest.raises(ValidationError, match="workspace evidence requires"):
        EvidenceItem(
            evidence_id="e1",
            source_type=EvidenceSourceType.WORKSPACE,
            content="supporting snippet",
        )


def test_general_evidence_forbids_document_chunk_metadata() -> None:
    """General context evidence must not be tied to workspace chunk IDs."""
    with pytest.raises(ValidationError, match="general evidence must not include"):
        EvidenceItem(
            evidence_id="e1",
            source_type=EvidenceSourceType.GENERAL,
            content="background context",
            document_id=10,
        )


def test_answer_envelope_requires_at_least_one_citation() -> None:
    """Answer envelopes are invalid without citations."""
    with pytest.raises(ValidationError, match="at least one citation"):
        AssistantResponseEnvelope(
            kind=AssistantResponseKind.ANSWER,
            text="grounded answer",
            grounding_mode=GroundingMode.HYBRID,
            evidence=[],
            citations=[],
        )


def test_refusal_envelope_requires_refusal_reason() -> None:
    """Refusal envelopes must include an explicit refusal reason."""
    with pytest.raises(ValidationError, match="must include refusal_reason"):
        AssistantResponseEnvelope(
            kind=AssistantResponseKind.REFUSAL,
            text="cannot answer",
            grounding_mode=GroundingMode.STRICT,
            evidence=[],
            citations=[],
        )
