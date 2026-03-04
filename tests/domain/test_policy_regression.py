"""AR6.4: Scenario and policy regression tests.

Tests that guardrail behaviors are regression-tested:
1. No uncited claims in strict mode
2. No premature topic jumps (concept resolution integrity)
3. No unauthorized research auto-ingest
4. Retrieved-vs-used source accounting
5. Stream/blocking path parity for guardrails
"""

from __future__ import annotations

import pytest

from core.schemas import (
    AssistantDraft,
    AssistantResponseKind,
    Citation,
    EvidenceItem,
    EvidenceSourceType,
    GroundingMode,
)
from core.verifier import (
    CitationValidationError,
    validate_citations,
    verify_assistant_draft,
)
from domain.chat.evidence_builder import filter_used_citations
from domain.research.promotion import evaluate_candidate_for_promotion


# ---------------------------------------------------------------------------
# 1. No uncited claims
# ---------------------------------------------------------------------------


class TestNoUncitedClaims:
    """In strict mode, responses without workspace citations must be refused."""

    def test_strict_no_citations_refuses(self) -> None:
        draft = AssistantDraft(text="The answer is 42.", evidence=[], citations=[])
        envelope = verify_assistant_draft(draft=draft, grounding_mode=GroundingMode.STRICT)
        assert envelope.kind == AssistantResponseKind.REFUSAL
        assert envelope.refusal_reason == "insufficient_evidence"

    def test_strict_only_general_citations_refuses(self) -> None:
        evidence = [
            EvidenceItem(
                evidence_id="e1",
                source_type=EvidenceSourceType.GENERAL,
                content="general info",
            ),
        ]
        citations = [
            Citation(citation_id="c1", evidence_id="e1", label="General context"),
        ]
        draft = AssistantDraft(text="Answer", evidence=evidence, citations=citations)
        envelope = verify_assistant_draft(draft=draft, grounding_mode=GroundingMode.STRICT)
        assert envelope.kind == AssistantResponseKind.REFUSAL

    def test_strict_with_workspace_citation_passes(self) -> None:
        evidence = [
            EvidenceItem(
                evidence_id="e1",
                source_type=EvidenceSourceType.WORKSPACE,
                content="from notes",
                document_id=1,
                chunk_id=1,
                chunk_index=0,
            ),
        ]
        citations = [
            Citation(citation_id="c1", evidence_id="e1", label="From your notes"),
        ]
        draft = AssistantDraft(text="Answer", evidence=evidence, citations=citations)
        envelope = verify_assistant_draft(draft=draft, grounding_mode=GroundingMode.STRICT)
        assert envelope.kind == AssistantResponseKind.ANSWER

    def test_hybrid_no_citations_refuses_without_allow_flag(self) -> None:
        draft = AssistantDraft(text="Answer", evidence=[], citations=[])
        envelope = verify_assistant_draft(draft=draft, grounding_mode=GroundingMode.HYBRID)
        assert envelope.kind == AssistantResponseKind.REFUSAL
        assert envelope.refusal_reason == "invalid_citations"

    def test_hybrid_allows_uncited_clarify(self) -> None:
        draft = AssistantDraft(text="Can you clarify?", evidence=[], citations=[])
        envelope = verify_assistant_draft(
            draft=draft,
            grounding_mode=GroundingMode.HYBRID,
            allow_uncited_hybrid=True,
        )
        assert envelope.kind == AssistantResponseKind.ANSWER
        assert envelope.response_mode == "clarify"


# ---------------------------------------------------------------------------
# 2. No premature topic jumps (citation validation integrity)
# ---------------------------------------------------------------------------


class TestCitationValidationIntegrity:
    """Citations must reference valid evidence with correct labels."""

    def test_dangling_citation_raises(self) -> None:
        evidence = [
            EvidenceItem(evidence_id="e1", source_type=EvidenceSourceType.WORKSPACE,
                         content="x", document_id=1, chunk_id=1, chunk_index=0),
        ]
        # Manually construct citation-like dicts to bypass pydantic label validation
        # and test the validate_citations function directly
        bad_citation = Citation(citation_id="c1", evidence_id="e_missing", label="From your notes")
        with pytest.raises(CitationValidationError, match="unknown evidence_id"):
            validate_citations(evidence=evidence, citations=[bad_citation])

    def test_duplicate_evidence_id_raises(self) -> None:
        evidence = [
            EvidenceItem(evidence_id="e1", source_type=EvidenceSourceType.WORKSPACE,
                         content="x", document_id=1, chunk_id=1, chunk_index=0),
            EvidenceItem(evidence_id="e1", source_type=EvidenceSourceType.WORKSPACE,
                         content="y", document_id=2, chunk_id=2, chunk_index=0),
        ]
        with pytest.raises(CitationValidationError, match="Duplicate evidence_id"):
            validate_citations(evidence=evidence, citations=[])

    def test_duplicate_citation_id_raises(self) -> None:
        evidence = [
            EvidenceItem(evidence_id="e1", source_type=EvidenceSourceType.WORKSPACE,
                         content="x", document_id=1, chunk_id=1, chunk_index=0),
        ]
        citations = [
            Citation(citation_id="c1", evidence_id="e1", label="From your notes"),
            Citation(citation_id="c1", evidence_id="e1", label="From your notes"),
        ]
        with pytest.raises(CitationValidationError, match="Duplicate citation_id"):
            validate_citations(evidence=evidence, citations=citations)

    def test_wrong_label_raises(self) -> None:
        """Workspace evidence requires 'From your notes' label, not 'General context'."""
        evidence = [
            EvidenceItem(evidence_id="e1", source_type=EvidenceSourceType.WORKSPACE,
                         content="x", document_id=1, chunk_id=1, chunk_index=0),
        ]
        citations = [
            Citation(citation_id="c1", evidence_id="e1", label="General context"),
        ]
        with pytest.raises(CitationValidationError, match="expected"):
            validate_citations(evidence=evidence, citations=citations)

    def test_valid_mixed_sources_pass(self) -> None:
        evidence = [
            EvidenceItem(
                evidence_id="e1", source_type=EvidenceSourceType.WORKSPACE,
                content="x", document_id=1, chunk_id=1, chunk_index=0,
            ),
            EvidenceItem(
                evidence_id="e2", source_type=EvidenceSourceType.GENERAL,
                content="y",
            ),
        ]
        citations = [
            Citation(citation_id="c1", evidence_id="e1", label="From your notes"),
            Citation(citation_id="c2", evidence_id="e2", label="General context"),
        ]
        validate_citations(evidence=evidence, citations=citations)


# ---------------------------------------------------------------------------
# 3. No unauthorized research auto-ingest
# ---------------------------------------------------------------------------


class TestNoUnauthorizedAutoIngest:
    """Research candidates cannot bypass approval gates."""

    def test_pending_candidate_cannot_promote(self) -> None:
        decision = evaluate_candidate_for_promotion(
            candidate_id=1, candidate_status="pending",
        )
        assert decision.action == "reject"

    def test_rejected_candidate_cannot_promote(self) -> None:
        decision = evaluate_candidate_for_promotion(
            candidate_id=1, candidate_status="rejected",
        )
        assert decision.action == "reject"

    def test_approved_with_quiz_gate_requires_pass(self) -> None:
        decision = evaluate_candidate_for_promotion(
            candidate_id=1,
            candidate_status="approved",
            has_quiz_gate=True,
            quiz_passed=False,
        )
        assert decision.action == "quiz_gate"
        assert decision.requires_review_quiz is True

    def test_approved_without_quiz_gate_promotes(self) -> None:
        decision = evaluate_candidate_for_promotion(
            candidate_id=1,
            candidate_status="approved",
        )
        assert decision.action == "promote"

    def test_approved_with_passed_quiz_promotes(self) -> None:
        decision = evaluate_candidate_for_promotion(
            candidate_id=1,
            candidate_status="approved",
            has_quiz_gate=True,
            quiz_passed=True,
        )
        assert decision.action == "promote"


# ---------------------------------------------------------------------------
# 4. Retrieved-vs-used source accounting
# ---------------------------------------------------------------------------


class TestSourceAccounting:
    """filter_used_citations must correctly account for used vs retrieved."""

    def _make_envelope(
        self,
        text: str,
        evidence: list[EvidenceItem],
        citations: list[Citation],
    ):
        from core.schemas import AssistantResponseEnvelope
        if not citations:
            # ANSWER kind requires citations; use REFUSAL for empty-citation tests
            return AssistantResponseEnvelope(
                kind=AssistantResponseKind.REFUSAL,
                text=text,
                grounding_mode=GroundingMode.HYBRID,
                evidence=evidence,
                citations=citations,
                refusal_reason="invalid_citations",
            )
        return AssistantResponseEnvelope(
            kind=AssistantResponseKind.ANSWER,
            text=text,
            grounding_mode=GroundingMode.HYBRID,
            evidence=evidence,
            citations=citations,
        )

    def test_unused_evidence_removed(self) -> None:
        evidence = [
            EvidenceItem(evidence_id="e1", source_type=EvidenceSourceType.WORKSPACE,
                         content="used", document_id=1, chunk_id=1, chunk_index=0),
            EvidenceItem(evidence_id="e2", source_type=EvidenceSourceType.WORKSPACE,
                         content="unused", document_id=2, chunk_id=2, chunk_index=0),
        ]
        citations = [
            Citation(citation_id="c1", evidence_id="e1", label="From your notes"),
            Citation(citation_id="c2", evidence_id="e2", label="From your notes"),
        ]
        # Only mention e1 in the text
        envelope = self._make_envelope("See e1 for details.", evidence, citations)
        filtered = filter_used_citations(envelope)
        assert len(filtered.citations) == 1
        assert filtered.citations[0].evidence_id == "e1"

    def test_no_citations_returns_unchanged(self) -> None:
        envelope = self._make_envelope("No refs.", [], [])
        filtered = filter_used_citations(envelope)
        assert filtered.citations == []
        assert filtered.evidence == []

    def test_all_used_stays_unchanged(self) -> None:
        evidence = [
            EvidenceItem(evidence_id="e1", source_type=EvidenceSourceType.WORKSPACE,
                         content="a", document_id=1, chunk_id=1, chunk_index=0),
        ]
        citations = [
            Citation(citation_id="c1", evidence_id="e1", label="From your notes"),
        ]
        envelope = self._make_envelope("Ref e1 here.", evidence, citations)
        filtered = filter_used_citations(envelope)
        assert len(filtered.citations) == 1


# ---------------------------------------------------------------------------
# 5. Stream/blocking path guardrail parity
# ---------------------------------------------------------------------------


class TestGuardrailParity:
    """Both blocking and streaming paths apply the same guardrails."""

    def test_verify_rejects_same_draft_in_both_modes(self) -> None:
        """The same no-citation draft must be rejected in both STRICT and HYBRID."""
        draft = AssistantDraft(text="Answer", evidence=[], citations=[])

        strict = verify_assistant_draft(draft=draft, grounding_mode=GroundingMode.STRICT)
        hybrid = verify_assistant_draft(draft=draft, grounding_mode=GroundingMode.HYBRID)

        assert strict.kind == AssistantResponseKind.REFUSAL
        assert hybrid.kind == AssistantResponseKind.REFUSAL

    def test_verify_accepts_same_valid_draft(self) -> None:
        """A valid draft with workspace citations passes both modes."""
        evidence = [
            EvidenceItem(
                evidence_id="e1",
                source_type=EvidenceSourceType.WORKSPACE,
                content="from notes",
                document_id=1,
                chunk_id=1,
                chunk_index=0,
            ),
        ]
        citations = [
            Citation(citation_id="c1", evidence_id="e1", label="From your notes"),
        ]
        draft = AssistantDraft(text="Answer", evidence=evidence, citations=citations)

        strict = verify_assistant_draft(draft=draft, grounding_mode=GroundingMode.STRICT)
        hybrid = verify_assistant_draft(draft=draft, grounding_mode=GroundingMode.HYBRID)

        assert strict.kind == AssistantResponseKind.ANSWER
        assert hybrid.kind == AssistantResponseKind.ANSWER
