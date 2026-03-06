"""Tests for graph LLM provider prompt rendering via assets."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from typing import Any

import pytest

from adapters.llm.providers import _BaseGraphLLMClient


class _StubGraphLLMClient(_BaseGraphLLMClient):
    """Minimal stub to test prompt rendering without a real SDK."""

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
    ) -> Mapping[str, Any]:
        # Capture the prompt for assertion
        self._last_messages = messages
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


class TestExtractRawGraphPrompt:
    """Test that extract_raw_graph uses the asset-backed prompt."""

    def test_prompt_contains_chunk_text(self) -> None:
        client = _StubGraphLLMClient(
            response={"concepts": [], "edges": []}
        )
        client.extract_raw_graph(chunk_text="Photosynthesis is the process")
        user_msg = client._last_messages[-1]["content"]
        assert "Photosynthesis is the process" in user_msg

    def test_prompt_uses_asset_structure(self) -> None:
        client = _StubGraphLLMClient(
            response={"concepts": [], "edges": []}
        )
        client.extract_raw_graph(chunk_text="test chunk")
        system_msg = client._last_messages[0]["content"]
        user_msg = client._last_messages[-1]["content"]
        # System message should have the extraction instructions
        assert "knowledge graph" in system_msg.lower()
        # User message should contain the chunk text
        assert "test chunk" in user_msg

    def test_empty_extraction_returns_empty(self) -> None:
        client = _StubGraphLLMClient(
            response={"concepts": [], "edges": []}
        )
        result = client.extract_raw_graph(chunk_text="nothing useful here")
        assert result["concepts"] == []
        assert result["edges"] == []


class TestDisambiguatePrompt:
    """Test that disambiguate uses the asset-backed prompt."""

    def test_prompt_contains_raw_name(self) -> None:
        client = _StubGraphLLMClient(
            response={
                "decision": "CREATE_NEW",
                "confidence": 0.5,
                "merge_into_id": None,
                "alias_to_add": None,
                "proposed_description": None,
            }
        )
        client.disambiguate(
            raw_name="DNA replication",
            context_snippet="copying DNA",
            candidates=[{"id": 1, "canonical_name": "DNA Replication"}],
        )
        user_msg = client._last_messages[-1]["content"]
        assert "DNA replication" in user_msg

    def test_prompt_contains_candidates(self) -> None:
        client = _StubGraphLLMClient(
            response={
                "decision": "MERGE_INTO",
                "confidence": 0.95,
                "merge_into_id": 1,
                "alias_to_add": "dna replication",
                "proposed_description": "DNA copying",
            }
        )
        client.disambiguate(
            raw_name="DNA replication",
            context_snippet=None,
            candidates=[{"id": 1, "canonical_name": "DNA Replication"}],
        )
        user_msg = client._last_messages[-1]["content"]
        assert "DNA Replication" in user_msg

    def test_create_new_bias_in_prompt(self) -> None:
        """Asset system prompt should mention CREATE_NEW as the safe default."""
        client = _StubGraphLLMClient(
            response={
                "decision": "CREATE_NEW",
                "confidence": 0.3,
                "merge_into_id": None,
                "alias_to_add": None,
                "proposed_description": None,
            }
        )
        client.disambiguate(
            raw_name="test",
            context_snippet="test",
            candidates=[],
        )
        system_msg = client._last_messages[0]["content"]
        assert "CREATE_NEW" in system_msg


class _FormatCapturingStub(_BaseGraphLLMClient):
    """Stub that captures the response_format passed to _sdk_call."""

    def __init__(self, *, model: str = "test-model", provider: str = "stub") -> None:
        super().__init__(model=model, timeout_seconds=30.0, provider=provider)
        self._captured_format: dict[str, object] | None = None
        self._captured_messages: list[dict[str, str]] = []

    def _sdk_call(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        response_format: dict[str, object] | None,
    ) -> Mapping[str, Any]:
        self._captured_format = response_format
        self._captured_messages = messages
        return {
            "choices": [
                {"message": {"content": json.dumps({"result": "ok"})}}
            ],
        }

    def _sdk_stream_call(
        self, *, messages: list[dict[str, str]], temperature: float,
    ) -> Iterator[Mapping[str, Any]]:
        return iter([])


class TestJsonSchemaDowngrade:
    """Verify that _chat_json uses json_object for non-OpenAI models."""

    def test_openai_provider_uses_json_schema(self) -> None:
        client = _FormatCapturingStub(model="gpt-4o", provider="openai")
        client._chat_json(
            schema_name="test_schema",
            schema={"type": "object", "properties": {}},
            prompt="test",
        )
        assert client._captured_format is not None
        assert client._captured_format["type"] == "json_schema"

    def test_deepseek_model_uses_json_schema(self) -> None:
        """DeepSeek supports json_schema via litellm runtime check."""
        client = _FormatCapturingStub(
            model="deepseek/deepseek-chat", provider="litellm",
        )
        client._chat_json(
            schema_name="test_schema",
            schema={"type": "object", "properties": {"name": {"type": "string"}}},
            prompt="test",
        )
        assert client._captured_format is not None
        assert client._captured_format["type"] == "json_schema"

    def test_deepseek_model_json_schema_includes_schema(self) -> None:
        """DeepSeek json_schema response includes the schema definition."""
        client = _FormatCapturingStub(
            model="deepseek/deepseek-chat", provider="litellm",
        )
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        client._chat_json(
            schema_name="test_schema",
            schema=schema,
            prompt="test",
        )
        assert client._captured_format is not None
        assert client._captured_format["type"] == "json_schema"
        assert "schema" in client._captured_format["json_schema"]

    def test_openai_prefixed_litellm_model_uses_json_schema(self) -> None:
        client = _FormatCapturingStub(
            model="openai/gpt-4o", provider="litellm",
        )
        client._chat_json(
            schema_name="test_schema",
            schema={"type": "object", "properties": {}},
            prompt="test",
        )
        assert client._captured_format is not None
        assert client._captured_format["type"] == "json_schema"

    def test_unknown_litellm_model_uses_json_object(self) -> None:
        client = _FormatCapturingStub(
            model="anthropic/claude-3", provider="litellm",
        )
        client._chat_json(
            schema_name="test_schema",
            schema={"type": "object", "properties": {}},
            prompt="test",
        )
        assert client._captured_format is not None
        assert client._captured_format["type"] == "json_object"


class _FallbackStub(_BaseGraphLLMClient):
    """Stub that fails the first *fail_count* SDK calls with a format error."""

    def __init__(
        self,
        *,
        model: str = "test-model",
        provider: str = "stub",
        fail_count: int = 0,
        error_msg: str = "response_format type unavailable",
    ) -> None:
        super().__init__(model=model, timeout_seconds=30.0, provider=provider)
        self._fail_count = fail_count
        self._error_msg = error_msg
        self._call_count = 0
        self.captured_formats: list[dict[str, object] | None] = []
        self.captured_messages: list[list[dict[str, str]]] = []

    def _sdk_call(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        response_format: dict[str, object] | None,
    ) -> Mapping[str, Any]:
        self._call_count += 1
        self.captured_formats.append(response_format)
        self.captured_messages.append(list(messages))
        if self._call_count <= self._fail_count:
            raise Exception(self._error_msg)
        return {
            "choices": [{"message": {"content": json.dumps({"result": "ok"})}}],
        }

    def _sdk_stream_call(
        self, *, messages: list[dict[str, str]], temperature: float,
    ) -> Iterator[Mapping[str, Any]]:
        return iter([])


class TestJsonFormatFallback:
    """Verify the runtime fallback chain in _chat_json."""

    _SCHEMA: dict[str, object] = {
        "type": "object",
        "properties": {"x": {"type": "string"}},
    }

    def test_json_schema_model_tries_json_schema_first(self) -> None:
        client = _FallbackStub(model="gpt-4o", provider="openai")
        client._chat_json(schema_name="s", schema=self._SCHEMA, prompt="hi")
        assert len(client.captured_formats) == 1
        assert client.captured_formats[0] is not None
        assert client.captured_formats[0]["type"] == "json_schema"

    def test_non_json_schema_model_tries_json_object_first(self) -> None:
        client = _FallbackStub(
            model="anthropic/claude-3-haiku", provider="litellm",
        )
        client._chat_json(schema_name="s", schema=self._SCHEMA, prompt="hi")
        assert len(client.captured_formats) == 1
        assert client.captured_formats[0] is not None
        assert client.captured_formats[0]["type"] == "json_object"

    def test_fallback_json_schema_to_json_object(self) -> None:
        client = _FallbackStub(
            model="gpt-4o", provider="openai", fail_count=1,
        )
        client._chat_json(schema_name="s", schema=self._SCHEMA, prompt="hi")
        assert len(client.captured_formats) == 2
        assert client.captured_formats[0]["type"] == "json_schema"
        assert client.captured_formats[1]["type"] == "json_object"

    def test_fallback_json_object_to_prompt_only(self) -> None:
        client = _FallbackStub(
            model="anthropic/claude-3-haiku", provider="litellm", fail_count=1,
        )
        client._chat_json(schema_name="s", schema=self._SCHEMA, prompt="hi")
        assert len(client.captured_formats) == 2
        assert client.captured_formats[1] is None

    def test_non_format_error_propagates(self) -> None:
        client = _FallbackStub(
            model="gpt-4o", provider="openai",
            fail_count=1, error_msg="connection timeout",
        )
        with pytest.raises(RuntimeError, match="connection timeout"):
            client._chat_json(schema_name="s", schema=self._SCHEMA, prompt="hi")

    def test_final_fallback_uses_no_response_format(self) -> None:
        client = _FallbackStub(
            model="gpt-4o", provider="openai", fail_count=2,
        )
        client._chat_json(schema_name="s", schema=self._SCHEMA, prompt="hi")
        assert client.captured_formats[-1] is None


class _ContentSequenceStub(_BaseGraphLLMClient):
    """Stub that returns a different content string on each successive call."""

    def __init__(
        self,
        *,
        model: str = "test-model",
        provider: str = "stub",
        contents: list[str],
    ) -> None:
        super().__init__(model=model, timeout_seconds=30.0, provider=provider)
        self._contents = list(contents)
        self._call_count = 0
        self.captured_formats: list[dict[str, object] | None] = []

    def _sdk_call(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        response_format: dict[str, object] | None,
    ) -> Mapping[str, Any]:
        idx = self._call_count
        self._call_count += 1
        self.captured_formats.append(response_format)
        return {
            "choices": [{"message": {"content": self._contents[idx]}}],
        }

    def _sdk_stream_call(
        self, *, messages: list[dict[str, str]], temperature: float,
    ) -> Iterator[Mapping[str, Any]]:
        return iter([])


class TestJsonParseFallback:
    """Verify that malformed/non-dict JSON triggers the parse fallback."""

    _SCHEMA: dict[str, object] = {
        "type": "object",
        "properties": {"x": {"type": "string"}},
    }

    def test_chat_json_parse_error_triggers_fallback(self) -> None:
        """Invalid JSON on first attempt falls back through the chain."""
        client = _ContentSequenceStub(
            model="anthropic/claude-3-haiku",
            provider="litellm",
            contents=[
                "not json at all",
                json.dumps({"x": "good"}),
            ],
        )
        result = client._chat_json(
            schema_name="s", schema=self._SCHEMA, prompt="hi",
        )
        assert result == {"x": "good"}
        # First call used json_object, second used prompt-only (None)
        assert len(client.captured_formats) == 2
        assert client.captured_formats[0]["type"] == "json_object"
        assert client.captured_formats[1] is None

    def test_chat_json_parse_error_on_last_attempt_raises(self) -> None:
        """All attempts returning invalid JSON raises ValueError."""
        client = _ContentSequenceStub(
            model="anthropic/claude-3-haiku",
            provider="litellm",
            contents=[
                "not json",
                "also not json",
            ],
        )
        with pytest.raises((json.JSONDecodeError, ValueError)):
            client._chat_json(
                schema_name="s", schema=self._SCHEMA, prompt="hi",
            )
        assert len(client.captured_formats) == 2

    def test_chat_json_non_dict_response_triggers_fallback(self) -> None:
        """Valid JSON array (non-dict) on first attempt falls back."""
        client = _ContentSequenceStub(
            model="anthropic/claude-3-haiku",
            provider="litellm",
            contents=[
                json.dumps([1, 2, 3]),
                json.dumps({"x": "dict"}),
            ],
        )
        result = client._chat_json(
            schema_name="s", schema=self._SCHEMA, prompt="hi",
        )
        assert result == {"x": "dict"}
        assert len(client.captured_formats) == 2
        assert client.captured_formats[1] is None
