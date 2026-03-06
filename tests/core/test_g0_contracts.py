"""Unit tests for G0: generation_trace schema, stream-event schemas, and feature flag."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from core.schemas.assistant import (
    AssistantResponseEnvelope,
    AssistantResponseKind,
    GenerationTrace,
    GroundingMode,
)
from core.schemas.chat import (
    ChatPhase,
    ChatStreamDeltaEvent,
    ChatStreamErrorEvent,
    ChatStreamEvent,
    ChatStreamFinalEvent,
    ChatStreamStatusEvent,
    ChatStreamTraceEvent,
)
from core.settings import Settings


# ── GenerationTrace ──────────────────────────────────────────────────


class TestGenerationTrace:
    def test_all_null_is_valid(self) -> None:
        trace = GenerationTrace()
        assert trace.provider is None
        assert trace.total_tokens is None
        assert trace.reasoning_tokens is None

    def test_full_trace(self) -> None:
        trace = GenerationTrace(
            provider="openai",
            model="gpt-4.1",
            timing_ms=1234.5,
            prompt_tokens=100,
            completion_tokens=200,
            total_tokens=300,
            reasoning_tokens=50,
        )
        assert trace.provider == "openai"
        assert trace.total_tokens == 300

    def test_negative_timing_rejected(self) -> None:
        with pytest.raises(ValidationError, match="timing_ms"):
            GenerationTrace(timing_ms=-1)

    def test_negative_tokens_rejected(self) -> None:
        with pytest.raises(ValidationError, match="prompt_tokens"):
            GenerationTrace(prompt_tokens=-5)

    def test_serialization_roundtrip(self) -> None:
        trace = GenerationTrace(provider="litellm", model="claude-sonnet", timing_ms=500.0)
        data = trace.model_dump()
        restored = GenerationTrace.model_validate(data)
        assert restored == trace

    def test_learner_profile_fields_default_none(self) -> None:
        trace = GenerationTrace()
        assert trace.learner_weak_topic_count is None
        assert trace.learner_strong_topic_count is None
        assert trace.learner_frontier_count is None
        assert trace.learner_review_count is None
        assert trace.learner_profile_summary is None

    def test_learner_profile_fields_populated(self) -> None:
        trace = GenerationTrace(
            learner_weak_topic_count=2,
            learner_strong_topic_count=1,
            learner_frontier_count=3,
            learner_review_count=1,
            learner_profile_summary="Weak topics: Math, Physics",
        )
        assert trace.learner_weak_topic_count == 2
        assert trace.learner_profile_summary == "Weak topics: Math, Physics"


# ── Envelope additive compatibility ──────────────────────────────────


class TestEnvelopeTraceField:
    def test_envelope_without_trace_is_valid(self) -> None:
        env = AssistantResponseEnvelope(
            kind=AssistantResponseKind.ANSWER,
            text="Hello!",
            grounding_mode=GroundingMode.HYBRID,
            response_mode="social",
        )
        assert env.generation_trace is None

    def test_envelope_with_trace(self) -> None:
        trace = GenerationTrace(provider="openai", model="gpt-4.1", total_tokens=100)
        env = AssistantResponseEnvelope(
            kind=AssistantResponseKind.ANSWER,
            text="Hello!",
            grounding_mode=GroundingMode.HYBRID,
            response_mode="social",
            generation_trace=trace,
        )
        assert env.generation_trace is not None
        assert env.generation_trace.provider == "openai"

    def test_envelope_serialization_includes_trace(self) -> None:
        trace = GenerationTrace(provider="openai", total_tokens=42)
        env = AssistantResponseEnvelope(
            kind=AssistantResponseKind.ANSWER,
            text="Hi",
            grounding_mode=GroundingMode.HYBRID,
            response_mode="social",
            generation_trace=trace,
        )
        data = env.model_dump()
        assert data["generation_trace"]["provider"] == "openai"
        assert data["generation_trace"]["total_tokens"] == 42

    def test_envelope_serialization_omits_trace_when_none(self) -> None:
        env = AssistantResponseEnvelope(
            kind=AssistantResponseKind.ANSWER,
            text="Hi",
            grounding_mode=GroundingMode.HYBRID,
            response_mode="social",
        )
        data = env.model_dump()
        assert data["generation_trace"] is None


# ── ChatPhase enum ───────────────────────────────────────────────────


class TestChatPhase:
    def test_phase_values(self) -> None:
        assert ChatPhase.THINKING.value == "thinking"
        assert ChatPhase.SEARCHING.value == "searching"
        assert ChatPhase.RESPONDING.value == "responding"
        assert ChatPhase.FINALIZING.value == "finalizing"

    def test_four_phases(self) -> None:
        assert len(ChatPhase) == 4


# ── Stream event schemas ─────────────────────────────────────────────


class TestStreamEvents:
    def test_status_event(self) -> None:
        evt = ChatStreamStatusEvent(phase=ChatPhase.THINKING)
        assert evt.event == "status"
        assert evt.phase == ChatPhase.THINKING
        assert evt.activity is None
        assert evt.step_label is None

    def test_status_event_with_activity(self) -> None:
        evt = ChatStreamStatusEvent(
            phase=ChatPhase.SEARCHING,
            activity="retrieving_chunks",
            step_label="Searching knowledge base",
        )
        assert evt.phase == ChatPhase.SEARCHING
        assert evt.activity == "retrieving_chunks"
        assert evt.step_label == "Searching knowledge base"

    def test_delta_event(self) -> None:
        evt = ChatStreamDeltaEvent(text="Hello ")
        assert evt.event == "delta"
        assert evt.text == "Hello "

    def test_trace_event(self) -> None:
        trace = GenerationTrace(provider="openai")
        evt = ChatStreamTraceEvent(trace=trace)
        assert evt.event == "trace"
        assert evt.trace.provider == "openai"

    def test_final_event(self) -> None:
        env = AssistantResponseEnvelope(
            kind=AssistantResponseKind.ANSWER,
            text="done",
            grounding_mode=GroundingMode.HYBRID,
            response_mode="social",
        )
        evt = ChatStreamFinalEvent(envelope=env)
        assert evt.event == "final"
        assert evt.envelope.text == "done"

    def test_error_event(self) -> None:
        evt = ChatStreamErrorEvent(message="something failed", phase=ChatPhase.SEARCHING)
        assert evt.event == "error"
        assert evt.phase == ChatPhase.SEARCHING

    def test_error_event_null_phase(self) -> None:
        evt = ChatStreamErrorEvent(message="unknown")
        assert evt.phase is None

    def test_discriminated_union_parsing(self) -> None:
        adapter = TypeAdapter(ChatStreamEvent)

        status = adapter.validate_python({"event": "status", "phase": "thinking"})
        assert isinstance(status, ChatStreamStatusEvent)

        delta = adapter.validate_python({"event": "delta", "text": "hi"})
        assert isinstance(delta, ChatStreamDeltaEvent)

        error = adapter.validate_python({"event": "error", "message": "fail"})
        assert isinstance(error, ChatStreamErrorEvent)

    def test_discriminated_union_with_activity(self) -> None:
        adapter = TypeAdapter(ChatStreamEvent)
        parsed = adapter.validate_python({
            "event": "status",
            "phase": "searching",
            "activity": "expanding_graph",
            "step_label": "Finding related concepts",
        })
        assert isinstance(parsed, ChatStreamStatusEvent)
        assert parsed.activity == "expanding_graph"
        assert parsed.step_label == "Finding related concepts"


# ── Feature flag ─────────────────────────────────────────────────────


class TestChatStreamingFlag:
    def test_default_enabled(self, monkeypatch) -> None:
        monkeypatch.delenv("APP_CHAT_STREAMING_ENABLED", raising=False)
        monkeypatch.delenv("CHAT_STREAMING_ENABLED", raising=False)
        settings = Settings(_env_file=None)
        assert settings.chat_streaming_enabled is True

    def test_enabled_via_env(self, monkeypatch) -> None:
        monkeypatch.setenv("APP_CHAT_STREAMING_ENABLED", "true")
        settings = Settings(_env_file=None)
        assert settings.chat_streaming_enabled is True

    def test_alias_works(self, monkeypatch) -> None:
        monkeypatch.delenv("APP_CHAT_STREAMING_ENABLED", raising=False)
        monkeypatch.setenv("CHAT_STREAMING_ENABLED", "1")
        settings = Settings(_env_file=None)
        assert settings.chat_streaming_enabled is True
