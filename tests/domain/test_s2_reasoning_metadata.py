"""Tests for S2: safe reasoning metadata on GenerationTrace."""

from __future__ import annotations

import pytest
from core.contracts import TutorTextStream
from core.schemas.assistant import GenerationTrace


class TestGenerationTraceReasoningFields:
    """S2: reasoning_requested/supported/used are explicit and nullable."""

    def test_defaults_to_none(self) -> None:
        trace = GenerationTrace()
        assert trace.reasoning_requested is None
        assert trace.reasoning_supported is None
        assert trace.reasoning_used is None
        assert trace.reasoning_tokens is None

    def test_all_false(self) -> None:
        trace = GenerationTrace(
            reasoning_requested=False,
            reasoning_supported=False,
            reasoning_used=False,
        )
        assert trace.reasoning_requested is False
        assert trace.reasoning_supported is False
        assert trace.reasoning_used is False

    def test_requested_but_not_supported(self) -> None:
        trace = GenerationTrace(
            reasoning_requested=True,
            reasoning_supported=False,
            reasoning_used=False,
            reasoning_tokens=None,
        )
        assert trace.reasoning_requested is True
        assert trace.reasoning_used is False

    def test_fully_used(self) -> None:
        trace = GenerationTrace(
            reasoning_requested=True,
            reasoning_supported=True,
            reasoning_used=True,
            reasoning_tokens=512,
        )
        assert trace.reasoning_used is True
        assert trace.reasoning_tokens == 512

    def test_serialization_includes_reasoning_fields(self) -> None:
        trace = GenerationTrace(
            reasoning_requested=True,
            reasoning_supported=True,
            reasoning_used=False,
        )
        data = trace.model_dump(mode="json")
        assert "reasoning_requested" in data
        assert "reasoning_supported" in data
        assert "reasoning_used" in data
        assert data["reasoning_requested"] is True
        assert data["reasoning_used"] is False


class TestTutorTextStreamReasoningMetadata:
    """S2: TutorTextStream propagates reasoning metadata to trace."""

    def test_stream_carries_reasoning_metadata(self) -> None:
        stream = TutorTextStream(
            iter(["hello"]),
            provider="openai",
            model="o3-mini",
            reasoning_requested=True,
            reasoning_supported=True,
            reasoning_used=True,
        )
        # Consume the stream
        list(stream)
        assert stream.trace.reasoning_requested is True
        assert stream.trace.reasoning_supported is True
        assert stream.trace.reasoning_used is True

    def test_stream_defaults_reasoning_false(self) -> None:
        stream = TutorTextStream(
            iter(["hello"]),
            provider="openai",
            model="gpt-4o",
        )
        list(stream)
        assert stream.trace.reasoning_requested is False
        assert stream.trace.reasoning_supported is False
        assert stream.trace.reasoning_used is False

    def test_usage_preserves_reasoning_fields(self) -> None:
        stream = TutorTextStream(
            iter([]),
            provider="openai",
            model="o3-mini",
            reasoning_requested=True,
            reasoning_supported=True,
            reasoning_used=True,
        )
        list(stream)
        stream.set_usage(
            prompt_tokens=100,
            completion_tokens=50,
            reasoning_tokens=30,
        )
        assert stream.trace.reasoning_requested is True
        assert stream.trace.reasoning_used is True
        assert stream.trace.reasoning_tokens == 30
