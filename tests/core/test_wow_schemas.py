"""Unit tests for WOW Release schemas – new types and envelope extensions."""

from __future__ import annotations

import pytest
from core.schemas import (
    ActionCTA,
    AssessmentCard,
    AssistantResponseEnvelope,
    AssistantResponseKind,
    Citation,
    FlashcardRateRequest,
    GroundingMode,
    KBDocumentSummary,
    ReadinessTopicState,
    ResearchCandidateSummary,
    ResearchSourceCreate,
    StatefulFlashcard,
)


class TestEnvelopeExtensions:
    def test_envelope_accepts_response_mode(self) -> None:
        env = AssistantResponseEnvelope(
            kind=AssistantResponseKind.ANSWER,
            text="Hello!",
            grounding_mode=GroundingMode.HYBRID,
            evidence=[],
            citations=[],
            response_mode="social",
            actions=[],
        )
        assert env.response_mode == "social"
        assert env.actions == []

    def test_envelope_grounded_requires_citations(self) -> None:
        """Grounded (default) mode still requires at least one citation."""
        with pytest.raises(Exception):
            AssistantResponseEnvelope(
                kind=AssistantResponseKind.ANSWER,
                text="Hello!",
                grounding_mode=GroundingMode.HYBRID,
                evidence=[],
                citations=[],
            )

    def test_envelope_with_actions(self) -> None:
        env = AssistantResponseEnvelope(
            kind=AssistantResponseKind.ANSWER,
            text="Try this quiz.",
            grounding_mode=GroundingMode.HYBRID,
            evidence=[],
            citations=[],
            response_mode="social",
            actions=[
                {"action_type": "quiz_cta", "label": "Review: Algebra", "concept_id": 5}
            ],
        )
        assert len(env.actions) == 1
        assert env.actions[0]["action_type"] == "quiz_cta"

    def test_envelope_clarify_mode_allows_no_citations(self) -> None:
        env = AssistantResponseEnvelope(
            kind=AssistantResponseKind.ANSWER,
            text="Can you share which part you want to focus on?",
            grounding_mode=GroundingMode.HYBRID,
            evidence=[],
            citations=[],
            response_mode="clarify",
            actions=[],
        )
        assert env.response_mode == "clarify"


class TestAssessmentCard:
    def test_valid_card(self) -> None:
        card = AssessmentCard(
            card_type="quiz_result",
            quiz_id=1,
            concept_id=5,
            concept_name="Linear Algebra",
            score=0.75,
            passed=True,
            summary="4/5 correct.",
        )
        assert card.card_type == "quiz_result"
        assert card.score == 0.75


class TestActionCTA:
    def test_quiz_cta(self) -> None:
        cta = ActionCTA(
            action_type="quiz_cta",
            label="Review: Derivatives",
            concept_id=3,
            concept_name="Derivatives",
        )
        assert cta.action_type == "quiz_cta"

    def test_quiz_offer_action(self) -> None:
        cta = ActionCTA(
            action_type="quiz_offer",
            label="Ready for a quiz?",
            concept_id=5,
            concept_name="Photosynthesis",
        )
        assert cta.action_type == "quiz_offer"
        assert cta.concept_id == 5

    def test_quiz_start_action(self) -> None:
        cta = ActionCTA(
            action_type="quiz_start",
            label="Start quiz now",
            concept_id=7,
            concept_name="Algebra",
        )
        assert cta.action_type == "quiz_start"
        assert cta.concept_name == "Algebra"

    def test_quiz_actions_serialize_in_envelope(self) -> None:
        env = AssistantResponseEnvelope(
            kind="answer",
            text="Great work!",
            grounding_mode="hybrid",
            citations=[Citation(citation_id="c1", evidence_id="e1", label="From your notes")],
            actions=[
                {"action_type": "quiz_offer", "label": "Ready for a quiz?", "concept_id": 5},
            ],
        )
        payload = env.model_dump(mode="json")
        assert payload["actions"][0]["action_type"] == "quiz_offer"
        restored = AssistantResponseEnvelope.model_validate(payload)
        assert restored.actions[0]["action_type"] == "quiz_offer"


class TestKBDocumentSummary:
    def test_valid_summary(self) -> None:
        doc = KBDocumentSummary(
            document_id=1,
            public_id="abc-123",
            title="Lecture notes",
            source_uri="file://notes.pdf",
            chunk_count=42,
            ingestion_status="ingested",
            graph_status="extracted",
            graph_concept_count=5,
            created_at="2026-01-01T00:00:00Z",
        )
        assert doc.chunk_count == 42


class TestReadinessTopicState:
    def test_valid_state(self) -> None:
        state = ReadinessTopicState(
            concept_id=1,
            concept_name="Calculus",
            readiness_score=0.65,
            recommend_quiz=False,
        )
        assert state.readiness_score == 0.65


class TestStatefulFlashcard:
    def test_unrated_flashcard(self) -> None:
        fc = StatefulFlashcard(
            flashcard_id="fc-1",
            front="What is 2+2?",
            back="4",
            hint="Simple addition",
        )
        assert fc.self_rating is None
        assert fc.passed is False


class TestFlashcardRateRequest:
    def test_valid_rate(self) -> None:
        req = FlashcardRateRequest(flashcard_id="fc-1", self_rating="good")
        assert req.self_rating == "good"


class TestResearchSourceCreate:
    def test_valid_source(self) -> None:
        src = ResearchSourceCreate(url="https://example.com/paper.pdf", label="Paper")
        assert src.url == "https://example.com/paper.pdf"


class TestResearchCandidateSummary:
    def test_valid_candidate(self) -> None:
        c = ResearchCandidateSummary(
            candidate_id=1,
            source_url="https://example.com",
            title="Example",
            snippet="preview...",
            status="pending",
        )
        assert c.status == "pending"
