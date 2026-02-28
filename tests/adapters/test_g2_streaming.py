"""Unit tests for G2: LLM streaming, trace normalization, and capability gating."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Any

import pytest

from core.contracts import TutorTextStream
from core.schemas.assistant import GenerationTrace


# ── TutorTextStream unit tests ───────────────────────────────────────


class TestTutorTextStream:
    def test_yields_deltas_and_captures_timing(self) -> None:
        deltas = iter(["Hello", " world"])
        stream = TutorTextStream(deltas, provider="openai", model="gpt-4.1")
        collected = list(stream)
        assert collected == ["Hello", " world"]
        assert stream.trace.provider == "openai"
        assert stream.trace.model == "gpt-4.1"
        assert stream.trace.timing_ms is not None
        assert stream.trace.timing_ms >= 0

    def test_set_usage_populates_trace(self) -> None:
        stream = TutorTextStream(iter([]), provider="litellm", model="claude")
        list(stream)  # exhaust
        stream.set_usage(prompt_tokens=10, completion_tokens=20, reasoning_tokens=5)
        assert stream.trace.prompt_tokens == 10
        assert stream.trace.completion_tokens == 20
        assert stream.trace.total_tokens == 30  # auto-calculated
        assert stream.trace.reasoning_tokens == 5

    def test_empty_stream_produces_valid_trace(self) -> None:
        stream = TutorTextStream(iter([]), provider="mock", model="test")
        list(stream)
        assert stream.trace.provider == "mock"
        assert stream.trace.timing_ms is not None

    def test_set_usage_with_explicit_total(self) -> None:
        stream = TutorTextStream(iter([]), provider="mock", model="test")
        list(stream)
        stream.set_usage(prompt_tokens=5, completion_tokens=10, total_tokens=20)
        assert stream.trace.total_tokens == 20  # explicit total wins

    def test_set_usage_with_no_data(self) -> None:
        stream = TutorTextStream(iter([]), provider="mock", model="test")
        list(stream)
        stream.set_usage()
        assert stream.trace.prompt_tokens is None
        assert stream.trace.total_tokens is None


# ── Mock streaming provider ──────────────────────────────────────────

from adapters.llm.providers import _BaseGraphLLMClient  # noqa: E402


class MockStreamingClient(_BaseGraphLLMClient):
    """Test double that simulates streaming with configurable chunks."""

    def __init__(
        self,
        *,
        chunks: list[dict[str, Any]],
        blocking_response: dict[str, Any] | None = None,
        reasoning_enabled: bool = False,
    ) -> None:
        super().__init__(
            model="mock-model",
            timeout_seconds=10.0,
            provider="mock",
            reasoning_enabled=reasoning_enabled,
        )
        self._chunks = chunks
        self._blocking_response = blocking_response or {
            "choices": [{"message": {"content": "blocking text"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    def _sdk_call(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        response_format: dict[str, object] | None,
    ) -> Mapping[str, Any]:
        return self._blocking_response

    def _sdk_stream_call(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
    ) -> Iterator[Mapping[str, Any]]:
        yield from self._chunks


class TestMockStreamingProvider:
    def test_stream_yields_text_deltas(self) -> None:
        chunks = [
            {"choices": [{"delta": {"content": "Hello"}}]},
            {"choices": [{"delta": {"content": " world"}}]},
            {"choices": [{"delta": {}}], "usage": {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15}},
        ]
        client = MockStreamingClient(chunks=chunks)
        stream = client.generate_tutor_text_stream(prompt="test")
        collected = list(stream)
        assert collected == ["Hello", " world"]
        assert stream.trace.prompt_tokens == 5
        assert stream.trace.completion_tokens == 10
        assert stream.trace.total_tokens == 15
        assert stream.trace.provider == "mock"
        assert stream.trace.model == "mock-model"
        assert stream.trace.timing_ms is not None

    def test_stream_with_missing_usage(self) -> None:
        chunks = [
            {"choices": [{"delta": {"content": "hi"}}]},
            {"choices": [{"delta": {}}]},
        ]
        client = MockStreamingClient(chunks=chunks)
        stream = client.generate_tutor_text_stream(prompt="test")
        collected = list(stream)
        assert collected == ["hi"]
        assert stream.trace.prompt_tokens is None
        assert stream.trace.total_tokens is None

    def test_stream_with_reasoning_tokens(self) -> None:
        chunks = [
            {"choices": [{"delta": {"content": "thought"}}]},
            {
                "choices": [{"delta": {}}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                    "completion_tokens_details": {"reasoning_tokens": 8},
                },
            },
        ]
        client = MockStreamingClient(chunks=chunks)
        stream = client.generate_tutor_text_stream(prompt="test")
        list(stream)
        assert stream.trace.reasoning_tokens == 8

    def test_empty_chunks_still_produces_trace(self) -> None:
        client = MockStreamingClient(chunks=[])
        stream = client.generate_tutor_text_stream(prompt="test")
        collected = list(stream)
        assert collected == []
        assert stream.trace.provider == "mock"

    def test_both_providers_produce_same_trace_shape(self) -> None:
        """OpenAI-mock and LiteLLM-mock should produce identical trace shapes."""
        chunks = [
            {"choices": [{"delta": {"content": "x"}}]},
            {"choices": [{"delta": {}}], "usage": {"prompt_tokens": 1, "completion_tokens": 2}},
        ]
        openai_client = MockStreamingClient(chunks=chunks)
        openai_client._provider = "openai"
        litellm_client = MockStreamingClient(chunks=chunks)
        litellm_client._provider = "litellm"

        openai_stream = openai_client.generate_tutor_text_stream(prompt="test")
        litellm_stream = litellm_client.generate_tutor_text_stream(prompt="test")

        list(openai_stream)
        list(litellm_stream)

        # Same shape, different provider name
        assert openai_stream.trace.prompt_tokens == litellm_stream.trace.prompt_tokens
        assert openai_stream.trace.completion_tokens == litellm_stream.trace.completion_tokens
        assert openai_stream.trace.total_tokens == litellm_stream.trace.total_tokens


# ── Capability gating tests ──────────────────────────────────────────


class TestReasoningCapabilityGating:
    def test_reasoning_enabled_on_supported_model(self) -> None:
        client = MockStreamingClient(chunks=[], reasoning_enabled=True)
        client._model = "o3-mini"
        kwargs = client._build_reasoning_kwargs()
        assert "reasoning_effort" in kwargs

    def test_reasoning_enabled_on_unsupported_model(self) -> None:
        client = MockStreamingClient(chunks=[], reasoning_enabled=True)
        client._model = "gpt-4.1"
        kwargs = client._build_reasoning_kwargs()
        assert kwargs == {}

    def test_reasoning_disabled_skips_params(self) -> None:
        client = MockStreamingClient(chunks=[], reasoning_enabled=False)
        client._model = "o3-mini"
        kwargs = client._build_reasoning_kwargs()
        assert kwargs == {}

    def test_model_supports_reasoning_prefixes(self) -> None:
        client = MockStreamingClient(chunks=[])
        for model in ("o1-preview", "o3-mini", "o4-mini"):
            client._model = model
            assert client._model_supports_reasoning()
        for model in ("gpt-4.1", "claude-sonnet", "llama-3"):
            client._model = model
            assert not client._model_supports_reasoning()
