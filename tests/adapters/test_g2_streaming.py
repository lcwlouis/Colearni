"""Unit tests for G2: LLM streaming, trace normalization, and capability gating."""

from __future__ import annotations

import threading
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

import pytest

from core.contracts import TutorTextStream
from core.observability import (
    configure_observability,
    observation_context,
    set_event_sink,
    set_tracer_provider_for_testing,
)
from core.schemas.assistant import GenerationTrace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult


class _InMemoryExporter(SpanExporter):
    """Minimal in-memory span exporter for test assertions."""

    def __init__(self):
        self._spans: list = []
        self._lock = threading.Lock()

    def export(self, spans):
        with self._lock:
            self._spans.extend(spans)
        return SpanExportResult.SUCCESS

    def get_finished_spans(self):
        with self._lock:
            return list(self._spans)

    def shutdown(self):
        pass


@pytest.fixture()
def otel_exporter():
    """Provide an in-memory OTel exporter for span assertions."""
    from core.settings import get_settings

    exporter = _InMemoryExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    set_tracer_provider_for_testing(provider)
    configure_observability(
        get_settings().model_copy(
            update={
                "observability_enabled": True,
                "observability_otlp_endpoint": None,
                "observability_service_name": "colearni-test",
                "observability_record_content": True,
            }
        )
    )
    yield exporter
    set_tracer_provider_for_testing(None)


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


# ── OBS-2: Streaming LLM span tests ─────────────────────────────────


class TestStreamingLLMSpan:
    def _llm_spans(self, exporter):
        """Return spans with LLM kind attribute."""
        return [
            s for s in exporter.get_finished_spans()
            if s.attributes.get("openinference.span.kind") == "LLM"
        ]

    def test_streaming_produces_llm_span(self, otel_exporter) -> None:
        """Streaming generates an LLM span with token counts."""
        chunks = [
            {"choices": [{"delta": {"content": "Hello"}}]},
            {"choices": [{"delta": {"content": " world"}}]},
            {"choices": [{"delta": {}}], "usage": {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15}},
        ]
        client = MockStreamingClient(chunks=chunks)
        stream = client.generate_tutor_text_stream(prompt="test")
        list(stream)

        llm_spans = self._llm_spans(otel_exporter)
        assert len(llm_spans) >= 1
        span = llm_spans[0]
        assert span.attributes.get("llm.token_count.prompt") == 5
        assert span.attributes.get("llm.token_count.completion") == 10
        assert span.attributes.get("llm.token_count.total") == 15

    def test_streaming_span_has_usage_source(self, otel_exporter) -> None:
        """Streaming span includes llm.usage_source = provider_reported."""
        chunks = [
            {"choices": [{"delta": {"content": "x"}}]},
            {"choices": [{"delta": {}}], "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}},
        ]
        client = MockStreamingClient(chunks=chunks)
        list(client.generate_tutor_text_stream(prompt="test"))

        llm_spans = self._llm_spans(otel_exporter)
        assert llm_spans[0].attributes.get("llm.usage_source") == "provider_reported"

    def test_streaming_span_missing_usage_source(self, otel_exporter) -> None:
        """Streaming span with no usage reports llm.usage_source = missing."""
        chunks = [
            {"choices": [{"delta": {"content": "x"}}]},
            {"choices": [{"delta": {}}]},
        ]
        client = MockStreamingClient(chunks=chunks)
        list(client.generate_tutor_text_stream(prompt="test"))

        llm_spans = self._llm_spans(otel_exporter)
        assert llm_spans[0].attributes.get("llm.usage_source") == "missing"

    def test_streaming_emits_event(self, otel_exporter) -> None:
        """Streaming completion emits an llm.call event."""
        events: list[dict] = []
        set_event_sink(events)

        chunks = [
            {"choices": [{"delta": {"content": "hi"}}]},
            {"choices": [{"delta": {}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}},
        ]
        client = MockStreamingClient(chunks=chunks)
        with observation_context(operation="chat.stream"):
            list(client.generate_tutor_text_stream(prompt="test"))

        assert len(events) == 1
        assert events[0]["event_name"] == "llm.call"
        assert events[0]["status"] == "success"
        set_event_sink(None)

    def test_streaming_span_captures_response_text(self, otel_exporter) -> None:
        """Streaming span includes response message preview."""
        chunks = [
            {"choices": [{"delta": {"content": "Hello"}}]},
            {"choices": [{"delta": {"content": " there"}}]},
            {"choices": [{"delta": {}}]},
        ]
        client = MockStreamingClient(chunks=chunks)
        list(client.generate_tutor_text_stream(prompt="test"))

        llm_spans = self._llm_spans(otel_exporter)
        assert llm_spans[0].attributes.get("llm.output_messages.preview") == "Hello there"

    def test_streaming_span_uses_operation_name(self, otel_exporter) -> None:
        """Streaming span name reflects the operation context."""
        chunks = [{"choices": [{"delta": {"content": "x"}}]}, {"choices": [{"delta": {}}]}]
        client = MockStreamingClient(chunks=chunks)
        with observation_context(operation="chat.respond"):
            list(client.generate_tutor_text_stream(prompt="test"))

        llm_spans = self._llm_spans(otel_exporter)
        assert llm_spans[0].name == "llm.chat.respond"
