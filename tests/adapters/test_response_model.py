"""Tests for the ``response_model`` parameter on ``complete_messages_json``."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from typing import Any

import pytest
from pydantic import ValidationError

from adapters.llm.providers import _BaseGraphLLMClient
from core.llm_messages import MessageBuilder
from core.llm_schemas import QueryAnalysisResponse

# ── Stub client ──────────────────────────────────────────────────────


class _StubGraphLLMClient(_BaseGraphLLMClient):
    """Minimal stub returning a canned JSON response."""

    def __init__(self, *, response: dict[str, Any]) -> None:
        super().__init__(
            model="test-model",
            timeout_seconds=30.0,
            provider="stub",
        )
        self._response = response

    def _sdk_call(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        response_format: dict[str, object] | None,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
    ) -> Mapping[str, Any]:
        self._last_messages = messages
        self._last_response_format = response_format
        return {
            "choices": [
                {"message": {"content": json.dumps(self._response)}}
            ],
        }

    def _sdk_stream_call(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
    ) -> Iterator[Mapping[str, Any]]:
        return iter([])


# ── Helpers ──────────────────────────────────────────────────────────

_VALID_QA_RESPONSE: dict[str, Any] = {
    "intent": "learn",
    "requested_mode": "direct",
    "needs_retrieval": True,
    "should_offer_level_up": False,
    "high_level_keywords": ["python"],
    "low_level_keywords": ["decorators"],
    "concept_hints": ["decorator"],
}

_MESSAGES = MessageBuilder().system("You are a test assistant.").user("hi").build()


# ── Tests ────────────────────────────────────────────────────────────


class TestResponseModelOnly:
    """response_model provided, schema/schema_name omitted."""

    def test_auto_generates_schema_and_validates(self) -> None:
        client = _StubGraphLLMClient(response=_VALID_QA_RESPONSE)
        result = client.complete_messages_json(
            _MESSAGES,
            response_model=QueryAnalysisResponse,
        )
        assert isinstance(result, QueryAnalysisResponse)
        assert result.intent == "learn"

    def test_schema_name_derived_from_model(self) -> None:
        client = _StubGraphLLMClient(response=_VALID_QA_RESPONSE)
        client.complete_messages_json(
            _MESSAGES,
            response_model=QueryAnalysisResponse,
        )
        # The stub model uses json_object fallback (no json_schema support),
        # so the schema hint is injected into the system message.
        system_content = client._last_messages[0]["content"]
        # Content may be structured blocks after _prepare_messages
        if isinstance(system_content, list):
            system_msg = "\n".join(b["text"] for b in system_content if isinstance(b, dict) and "text" in b)
        else:
            system_msg = system_content
        assert "intent" in system_msg


class TestSchemaOnly:
    """Backward-compatible path — explicit schema_name + schema, no response_model."""

    def test_existing_callers_work(self) -> None:
        client = _StubGraphLLMClient(response=_VALID_QA_RESPONSE)
        schema = QueryAnalysisResponse.model_json_schema()
        result = client.complete_messages_json(
            _MESSAGES,
            schema_name="QueryAnalysisResponse",
            schema=schema,
        )
        assert isinstance(result, dict)
        assert result["intent"] == "learn"


class TestBothProvided:
    """When both response_model AND schema are given, explicit schema wins."""

    def test_explicit_schema_takes_precedence(self) -> None:
        custom_schema: dict[str, object] = {
            "type": "object",
            "properties": {
                "intent": {"type": "string"},
                "requested_mode": {"type": "string"},
                "needs_retrieval": {"type": "boolean"},
                "should_offer_level_up": {"type": "boolean"},
                "high_level_keywords": {"type": "array", "items": {"type": "string"}},
                "low_level_keywords": {"type": "array", "items": {"type": "string"}},
                "concept_hints": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "intent", "requested_mode", "needs_retrieval",
                "should_offer_level_up", "high_level_keywords",
                "low_level_keywords", "concept_hints",
            ],
            "additionalProperties": False,
        }
        client = _StubGraphLLMClient(response=_VALID_QA_RESPONSE)
        result = client.complete_messages_json(
            _MESSAGES,
            schema_name="CustomName",
            schema=custom_schema,
            response_model=QueryAnalysisResponse,
        )
        assert isinstance(result, QueryAnalysisResponse)
        # Explicit schema takes precedence — the hint embedded in the
        # messages should contain the custom schema, not the model-derived one.
        last_content = client._last_messages[-1]["content"]
        if isinstance(last_content, list):
            last_user = "\n".join(b["text"] for b in last_content if isinstance(b, dict) and "text" in b)
        else:
            last_user = last_content
        # custom_schema doesn't have the pydantic $defs key; verify it was used
        assert "$defs" not in last_user


class TestNeitherProvided:
    """Omitting both response_model and schema must raise ValueError."""

    def test_raises_value_error(self) -> None:
        client = _StubGraphLLMClient(response={})
        with pytest.raises(ValueError, match="response_model.*schema"):
            client.complete_messages_json(_MESSAGES)


class TestValidationFailure:
    """response_model validation should propagate when LLM returns invalid data."""

    def test_invalid_response_raises_validation_error(self) -> None:
        bad_response: dict[str, Any] = {
            "intent": "INVALID_INTENT",
            "requested_mode": "direct",
            "needs_retrieval": True,
            "should_offer_level_up": False,
            "high_level_keywords": ["python"],
            "low_level_keywords": ["decorators"],
            "concept_hints": ["decorator"],
        }
        client = _StubGraphLLMClient(response=bad_response)
        with pytest.raises(ValidationError):
            client.complete_messages_json(
                _MESSAGES,
                response_model=QueryAnalysisResponse,
            )
