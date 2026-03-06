"""Tests for core.llm_schemas — Pydantic response models for LLM structured output."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.llm_schemas import (
    DisambiguationBatchResponse,
    DisambiguationResponse,
    QueryAnalysisResponse,
    QuizGradingItem,
    QuizGradingResponse,
    RawConceptItem,
    RawEdgeItem,
    RawGraphResponse,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _valid_concept(**overrides: object) -> dict:
    base = {"name": "Recursion", "context_snippet": "a snippet", "description": "desc", "tier": "topic"}
    return {**base, **overrides}


def _valid_edge(**overrides: object) -> dict:
    base = {
        "src_name": "A",
        "tgt_name": "B",
        "relation_type": "prerequisite",
        "description": None,
        "keywords": ["k1"],
        "weight": 5,
    }
    return {**base, **overrides}


def _valid_disambiguation(**overrides: object) -> dict:
    base = {
        "decision": "CREATE_NEW",
        "confidence": 0.9,
        "merge_into_id": None,
        "merge_into_name": None,
        "alias_to_add": None,
        "proposed_description": "new concept",
        "link_to_id": None,
        "link_to_name": None,
        "link_relation_type": None,
        "proposed_tier": "topic",
    }
    return {**base, **overrides}


def _valid_query_analysis(**overrides: object) -> dict:
    base = {
        "intent": "learn",
        "requested_mode": "socratic",
        "needs_retrieval": True,
        "should_offer_level_up": False,
        "high_level_keywords": ["ML"],
        "low_level_keywords": ["gradient"],
        "concept_hints": ["backpropagation"],
    }
    return {**base, **overrides}


def _valid_grading_item(**overrides: object) -> dict:
    base = {"item_id": 1, "score": 0.75, "critical_misconception": False, "feedback": "Good answer."}
    return {**base, **overrides}


def _valid_grading_response(**overrides: object) -> dict:
    base = {"items": [_valid_grading_item()], "overall_feedback": "Well done overall."}
    return {**base, **overrides}


# ===================================================================
# RawGraphResponse
# ===================================================================


class TestRawGraphResponse:
    def test_valid(self):
        data = {"concepts": [_valid_concept()], "edges": [_valid_edge()]}
        model = RawGraphResponse.model_validate(data)
        assert len(model.concepts) == 1
        assert model.concepts[0].tier == "topic"
        assert model.edges[0].weight == 5

    def test_nullable_fields(self):
        concept = _valid_concept(context_snippet=None, description=None, tier=None)
        model = RawGraphResponse.model_validate({"concepts": [concept], "edges": []})
        assert model.concepts[0].tier is None

    def test_all_tiers(self):
        for tier in ("umbrella", "topic", "subtopic", "granular", None):
            concept = _valid_concept(tier=tier)
            item = RawConceptItem.model_validate(concept)
            assert item.tier == tier

    def test_extra_field_rejected_concept(self):
        with pytest.raises(ValidationError, match="extra"):
            RawConceptItem.model_validate({**_valid_concept(), "extra": 1})

    def test_extra_field_rejected_edge(self):
        with pytest.raises(ValidationError, match="extra"):
            RawEdgeItem.model_validate({**_valid_edge(), "extra": 1})

    def test_extra_field_rejected_top(self):
        with pytest.raises(ValidationError, match="extra"):
            RawGraphResponse.model_validate(
                {"concepts": [], "edges": [], "extra": True}
            )

    def test_invalid_tier(self):
        with pytest.raises(ValidationError):
            RawConceptItem.model_validate(_valid_concept(tier="invalid"))

    def test_schema_structure(self):
        schema = RawGraphResponse.model_json_schema()
        assert "concepts" in schema["properties"]
        assert "edges" in schema["properties"]
        assert set(schema["required"]) == {"concepts", "edges"}


# ===================================================================
# DisambiguationResponse
# ===================================================================


class TestDisambiguationResponse:
    def test_valid(self):
        model = DisambiguationResponse.model_validate(_valid_disambiguation())
        assert model.decision == "CREATE_NEW"
        assert model.confidence == 0.9

    def test_all_decisions(self):
        for decision in ("MERGE_INTO", "CREATE_NEW", "LINK_ONLY"):
            m = DisambiguationResponse.model_validate(_valid_disambiguation(decision=decision))
            assert m.decision == decision

    def test_invalid_decision(self):
        with pytest.raises(ValidationError):
            DisambiguationResponse.model_validate(_valid_disambiguation(decision="DELETE"))

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError, match="extra"):
            DisambiguationResponse.model_validate({**_valid_disambiguation(), "bonus": 1})

    def test_schema_required_fields(self):
        schema = DisambiguationResponse.model_json_schema()
        assert "decision" in schema["required"]
        assert "confidence" in schema["required"]


# ===================================================================
# DisambiguationBatchResponse
# ===================================================================


class TestDisambiguationBatchResponse:
    def test_valid(self):
        data = {
            "decisions": [
                {"concept_ref": "ML", "operations": [_valid_disambiguation()]},
            ]
        }
        model = DisambiguationBatchResponse.model_validate(data)
        assert len(model.decisions) == 1
        assert model.decisions[0].concept_ref == "ML"

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError, match="extra"):
            DisambiguationBatchResponse.model_validate(
                {"decisions": [], "extra": True}
            )

    def test_schema_structure(self):
        schema = DisambiguationBatchResponse.model_json_schema()
        assert "decisions" in schema["properties"]


# ===================================================================
# QueryAnalysisResponse
# ===================================================================


class TestQueryAnalysisResponse:
    def test_valid(self):
        model = QueryAnalysisResponse.model_validate(_valid_query_analysis())
        assert model.intent == "learn"
        assert model.needs_retrieval is True

    def test_all_intents(self):
        for intent in ("learn", "practice", "level_up", "explore", "social", "clarify"):
            m = QueryAnalysisResponse.model_validate(_valid_query_analysis(intent=intent))
            assert m.intent == intent

    def test_all_modes(self):
        for mode in ("socratic", "direct", "unknown"):
            m = QueryAnalysisResponse.model_validate(_valid_query_analysis(requested_mode=mode))
            assert m.requested_mode == mode

    def test_invalid_intent(self):
        with pytest.raises(ValidationError):
            QueryAnalysisResponse.model_validate(_valid_query_analysis(intent="invalid"))

    def test_invalid_mode(self):
        with pytest.raises(ValidationError):
            QueryAnalysisResponse.model_validate(_valid_query_analysis(requested_mode="lazy"))

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError, match="extra"):
            QueryAnalysisResponse.model_validate({**_valid_query_analysis(), "x": 1})

    def test_schema_required_fields(self):
        schema = QueryAnalysisResponse.model_json_schema()
        expected = {
            "intent", "requested_mode", "needs_retrieval",
            "should_offer_level_up", "high_level_keywords",
            "low_level_keywords", "concept_hints",
        }
        assert set(schema["required"]) == expected


# ===================================================================
# QuizGradingResponse
# ===================================================================


class TestQuizGradingResponse:
    def test_valid(self):
        model = QuizGradingResponse.model_validate(_valid_grading_response())
        assert len(model.items) == 1
        assert model.items[0].score == 0.75

    def test_score_boundaries(self):
        QuizGradingItem.model_validate(_valid_grading_item(score=0.0))
        QuizGradingItem.model_validate(_valid_grading_item(score=1.0))

    def test_score_too_low(self):
        with pytest.raises(ValidationError):
            QuizGradingItem.model_validate(_valid_grading_item(score=-0.1))

    def test_score_too_high(self):
        with pytest.raises(ValidationError):
            QuizGradingItem.model_validate(_valid_grading_item(score=1.1))

    def test_empty_feedback_rejected(self):
        with pytest.raises(ValidationError, match="feedback must not be empty"):
            QuizGradingItem.model_validate(_valid_grading_item(feedback="   "))

    def test_empty_overall_feedback_rejected(self):
        with pytest.raises(ValidationError, match="overall_feedback must not be empty"):
            QuizGradingResponse.model_validate(_valid_grading_response(overall_feedback="  "))

    def test_extra_field_rejected_item(self):
        with pytest.raises(ValidationError, match="extra"):
            QuizGradingItem.model_validate({**_valid_grading_item(), "extra": 1})

    def test_extra_field_rejected_response(self):
        with pytest.raises(ValidationError, match="extra"):
            QuizGradingResponse.model_validate({**_valid_grading_response(), "extra": 1})

    def test_schema_structure(self):
        schema = QuizGradingResponse.model_json_schema()
        assert "items" in schema["properties"]
        assert "overall_feedback" in schema["properties"]
