"""Tests for query analyzer – prompt rendering and JSON parsing."""

from __future__ import annotations

import json

from domain.chat.query_analyzer import (
    build_query_analysis_prompt,
    parse_query_analysis,
)


class TestBuildPrompt:
    """Test prompt rendering from the query_analyzer_v1 asset."""

    def test_renders_with_query(self) -> None:
        prompt, meta = build_query_analysis_prompt(query="Explain DNA replication")
        assert "Explain DNA replication" in prompt
        assert "query analysis" in prompt.lower()

    def test_renders_with_history(self) -> None:
        prompt, meta = build_query_analysis_prompt(
            query="Continue", history_summary="User asked about mitosis."
        )
        assert "User asked about mitosis." in prompt
        assert "Continue" in prompt

    def test_renders_without_history(self) -> None:
        prompt, meta = build_query_analysis_prompt(query="What is a cell?")
        assert "(none)" in prompt


class TestParseQueryAnalysis:
    """Test JSON parsing with validation and fallback behavior."""

    def test_valid_learn_intent(self) -> None:
        raw = json.dumps({
            "intent": "learn",
            "requested_mode": "socratic",
            "needs_retrieval": True,
            "should_offer_level_up": False,
            "high_level_keywords": ["biology", "cell"],
            "low_level_keywords": ["mitosis", "division"],
            "concept_hints": ["cell division"],
        })
        result = parse_query_analysis(raw)
        assert result.intent == "learn"
        assert result.requested_mode == "socratic"
        assert result.needs_retrieval is True
        assert result.should_offer_level_up is False
        assert result.high_level_keywords == ["biology", "cell"]
        assert result.low_level_keywords == ["mitosis", "division"]
        assert result.concept_hints == ["cell division"]

    def test_practice_intent(self) -> None:
        raw = json.dumps({
            "intent": "practice",
            "requested_mode": "unknown",
            "needs_retrieval": True,
            "should_offer_level_up": False,
            "high_level_keywords": ["chemistry"],
            "low_level_keywords": [],
            "concept_hints": ["chemical bonding"],
        })
        result = parse_query_analysis(raw)
        assert result.intent == "practice"

    def test_level_up_intent(self) -> None:
        raw = json.dumps({
            "intent": "level_up",
            "requested_mode": "unknown",
            "needs_retrieval": False,
            "should_offer_level_up": True,
            "high_level_keywords": [],
            "low_level_keywords": [],
            "concept_hints": ["photosynthesis"],
        })
        result = parse_query_analysis(raw)
        assert result.intent == "level_up"
        assert result.should_offer_level_up is True
        assert result.needs_retrieval is False

    def test_social_intent(self) -> None:
        raw = json.dumps({
            "intent": "social",
            "requested_mode": "unknown",
            "needs_retrieval": False,
            "should_offer_level_up": False,
            "high_level_keywords": [],
            "low_level_keywords": [],
            "concept_hints": [],
        })
        result = parse_query_analysis(raw)
        assert result.intent == "social"
        assert result.needs_retrieval is False
        assert result.concept_hints == []

    def test_vague_returns_clarify(self) -> None:
        raw = json.dumps({
            "intent": "clarify",
            "requested_mode": "unknown",
            "needs_retrieval": False,
            "should_offer_level_up": False,
            "high_level_keywords": [],
            "low_level_keywords": [],
            "concept_hints": [],
        })
        result = parse_query_analysis(raw)
        assert result.intent == "clarify"
        assert result.high_level_keywords == []

    def test_invalid_json_returns_fallback(self) -> None:
        result = parse_query_analysis("not json at all")
        assert result.intent == "clarify"
        assert result.needs_retrieval is False

    def test_empty_string_returns_fallback(self) -> None:
        result = parse_query_analysis("")
        assert result.intent == "clarify"

    def test_unknown_intent_normalized_to_clarify(self) -> None:
        raw = json.dumps({"intent": "banana", "requested_mode": "unknown"})
        result = parse_query_analysis(raw)
        assert result.intent == "clarify"

    def test_unknown_mode_normalized(self) -> None:
        raw = json.dumps({"intent": "learn", "requested_mode": "freestyle"})
        result = parse_query_analysis(raw)
        assert result.requested_mode == "unknown"

    def test_non_list_keywords_coerced(self) -> None:
        raw = json.dumps({
            "intent": "learn",
            "high_level_keywords": "not a list",
            "low_level_keywords": 42,
        })
        result = parse_query_analysis(raw)
        assert result.high_level_keywords == []
        assert result.low_level_keywords == []

    def test_non_dict_returns_fallback(self) -> None:
        result = parse_query_analysis(json.dumps([1, 2, 3]))
        assert result.intent == "clarify"

    def test_partial_data_uses_defaults(self) -> None:
        raw = json.dumps({"intent": "explore"})
        result = parse_query_analysis(raw)
        assert result.intent == "explore"
        assert result.requested_mode == "unknown"
        assert result.needs_retrieval is True
        assert result.concept_hints == []
