"""Tests for query analyzer – prompt rendering, JSON parsing, and runtime wiring."""

from __future__ import annotations

import json

from domain.chat.query_analyzer import (
    QueryAnalysis,
    build_query_analysis_messages,
    build_query_analysis_prompt,
    parse_query_analysis,
    run_query_analysis,
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


class TestBuildQueryAnalysisMessages:
    """Test multi-message builder."""

    def test_returns_message_builder(self) -> None:
        from core.llm_messages import MessageBuilder

        builder = build_query_analysis_messages(query="Explain DNA")
        assert isinstance(builder, MessageBuilder)

    def test_builds_system_and_user(self) -> None:
        msgs = build_query_analysis_messages(query="Explain DNA").build()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"
        assert "Explain DNA" in msgs[1]["content"]

    def test_includes_history_summary(self) -> None:
        msgs = build_query_analysis_messages(
            query="Continue",
            history_summary="Discussed mitosis",
        ).build()
        assert "Discussed mitosis" in msgs[1]["content"]


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
        assert result.needs_retrieval is True

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


class _FakeLLM:
    """Minimal LLM stub for run_query_analysis tests."""

    def __init__(self, response: str | Exception) -> None:
        self._response = response

    def complete_messages_json(
        self, messages: list, *, schema_name: str, schema: dict
    ) -> dict:
        if isinstance(self._response, Exception):
            raise self._response
        return json.loads(self._response)


class TestRunQueryAnalysis:
    """Tests for the runtime entrypoint that calls the LLM."""

    def test_returns_fallback_when_no_client(self) -> None:
        result = run_query_analysis(query="hello", llm_client=None)
        assert result.intent == "clarify"
        assert result.needs_retrieval is True

    def test_success_learn_intent(self) -> None:
        payload = json.dumps({
            "intent": "learn",
            "requested_mode": "socratic",
            "needs_retrieval": True,
            "should_offer_level_up": False,
            "high_level_keywords": ["biology"],
            "low_level_keywords": [],
            "concept_hints": ["mitosis"],
        })
        result = run_query_analysis(
            query="Explain mitosis",
            llm_client=_FakeLLM(payload),
        )
        assert result.intent == "learn"
        assert result.requested_mode == "socratic"
        assert result.needs_retrieval is True
        assert result.concept_hints == ["mitosis"]

    def test_returns_fallback_on_runtime_error(self) -> None:
        result = run_query_analysis(
            query="anything",
            llm_client=_FakeLLM(RuntimeError("timeout")),
        )
        assert result.intent == "clarify"
        assert result.needs_retrieval is True

    def test_returns_fallback_on_value_error(self) -> None:
        result = run_query_analysis(
            query="anything",
            llm_client=_FakeLLM(ValueError("bad")),
        )
        assert result.intent == "clarify"

    def test_returns_fallback_on_unexpected_error(self) -> None:
        result = run_query_analysis(
            query="anything",
            llm_client=_FakeLLM(TypeError("surprise")),
        )
        assert result.intent == "clarify"

    def test_returns_fallback_on_garbage_response(self) -> None:
        result = run_query_analysis(
            query="anything",
            llm_client=_FakeLLM("this is not json"),
        )
        assert result.intent == "clarify"
        assert result.needs_retrieval is True

    def test_passes_history_summary(self) -> None:
        """History summary is forwarded through to the prompt builder."""
        payload = json.dumps({
            "intent": "learn",
            "requested_mode": "unknown",
            "needs_retrieval": True,
        })
        result = run_query_analysis(
            query="continue",
            history_summary="discussed photosynthesis",
            llm_client=_FakeLLM(payload),
        )
        assert result.intent == "learn"


class TestPydanticValidation:
    """Tests verifying Pydantic schema validation catches bad data."""

    def test_extra_fields_rejected(self) -> None:
        """Pydantic extra='forbid' catches unexpected fields that manual parsing ignored."""
        raw = json.dumps({
            "intent": "learn",
            "requested_mode": "socratic",
            "needs_retrieval": True,
            "should_offer_level_up": False,
            "high_level_keywords": [],
            "low_level_keywords": [],
            "concept_hints": [],
            "rogue_field": "should not be here",
        })
        result = parse_query_analysis(raw)
        assert result.intent == "clarify"  # falls back

    def test_wrong_type_for_bool_field_rejected(self) -> None:
        """Pydantic catches non-boolean values for bool fields."""
        raw = json.dumps({
            "intent": "learn",
            "requested_mode": "socratic",
            "needs_retrieval": [1, 2],
        })
        result = parse_query_analysis(raw)
        assert result.intent == "clarify"  # falls back

    def test_accepts_dict_directly(self) -> None:
        """parse_query_analysis accepts a dict (from complete_messages_json)."""
        data = {
            "intent": "explore",
            "requested_mode": "direct",
            "needs_retrieval": False,
            "should_offer_level_up": False,
            "high_level_keywords": ["math"],
            "low_level_keywords": [],
            "concept_hints": ["algebra"],
        }
        result = parse_query_analysis(data)
        assert result.intent == "explore"
        assert result.requested_mode == "direct"
        assert result.concept_hints == ["algebra"]
        assert result.needs_web_search is True


class TestNeedsWebSearch:
    """needs_web_search is derived from intent == 'explore'."""

    def test_explore_intent_enables_web_search(self) -> None:
        data = {"intent": "explore"}
        result = parse_query_analysis(data)
        assert result.needs_web_search is True

    def test_learn_intent_disables_web_search(self) -> None:
        data = {"intent": "learn"}
        result = parse_query_analysis(data)
        assert result.needs_web_search is False

    def test_clarify_intent_disables_web_search(self) -> None:
        data = {"intent": "clarify"}
        result = parse_query_analysis(data)
        assert result.needs_web_search is False

    def test_fallback_disables_web_search(self) -> None:
        result = parse_query_analysis("invalid json")
        assert result.needs_web_search is False
