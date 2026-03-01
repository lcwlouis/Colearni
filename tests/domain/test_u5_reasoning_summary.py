"""Tests for U5: ephemeral reasoning summary transport."""

from __future__ import annotations

from typing import Any
from collections.abc import Iterator

from core.schemas.assistant import GenerationTrace
from core.schemas.chat import ChatStreamReasoningSummaryEvent


class TestReasoningSummaryEvent:
    """U5: stream-only reasoning summary event."""

    def test_event_type(self) -> None:
        event = ChatStreamReasoningSummaryEvent(summary="Reasoned for 512 tokens")
        assert event.event == "reasoning_summary"
        assert event.summary == "Reasoned for 512 tokens"

    def test_serialization(self) -> None:
        event = ChatStreamReasoningSummaryEvent(summary="test summary")
        data = event.model_dump(mode="json")
        assert data["event"] == "reasoning_summary"
        assert data["summary"] == "test summary"

    def test_not_on_envelope(self) -> None:
        """Reasoning summaries must NOT be persisted on the envelope."""
        from core.schemas.assistant import AssistantResponseEnvelope

        fields = AssistantResponseEnvelope.model_fields
        assert "reasoning_summary" not in fields, (
            "reasoning_summary must not be a field on AssistantResponseEnvelope"
        )


def _stub_stream_monkeypatches(monkeypatch: Any) -> None:
    """Apply the common monkeypatches for stream tests."""
    monkeypatch.setattr("domain.chat.stream.try_social_response", lambda **kw: None)
    monkeypatch.setattr("domain.chat.stream.load_history_text", lambda s, session_id: "")
    monkeypatch.setattr("domain.chat.stream.load_assessment_context", lambda s, session_id: "")
    monkeypatch.setattr(
        "domain.chat.stream.resolve_concept_for_turn",
        lambda s, **kw: type("R", (), {
            "resolved_concept": None, "confidence": 0.0,
            "requires_clarification": False,
            "switch_suggestion": None, "clarification_prompt": None,
        })(),
    )
    monkeypatch.setattr(
        "domain.chat.retrieval_context.retrieve_ranked_chunks",
        lambda s, **kw: [type("C", (), {
            "chunk_id": 1, "text": "hello", "score": 0.9,
            "document_id": 1, "concept_ids": [],
        })()],
    )
    monkeypatch.setattr("domain.chat.retrieval_context.workspace_has_no_chunks", lambda s, workspace_id: False)
    monkeypatch.setattr("domain.chat.stream.build_workspace_evidence", lambda **kw: [])
    monkeypatch.setattr("domain.chat.stream.build_workspace_citations", lambda ev: [])
    monkeypatch.setattr("domain.chat.stream.resolve_mastery_status", lambda **kw: None)
    monkeypatch.setattr("domain.chat.retrieval_context.apply_concept_bias", lambda s, **kw: [])
    monkeypatch.setattr("domain.chat.stream.build_readiness_actions", lambda s, **kw: [])
    monkeypatch.setattr("domain.chat.stream.build_document_summaries_context", lambda **kw: "")
    monkeypatch.setattr("domain.chat.stream.build_quiz_context", lambda **kw: "")
    monkeypatch.setattr("domain.chat.stream.load_flashcard_progress", lambda s, **kw: None)
    monkeypatch.setattr("domain.chat.stream.resolve_tutor_style", lambda **kw: "balanced")
    monkeypatch.setattr("domain.chat.stream.get_persona", lambda name: "You are a tutor.")
    monkeypatch.setattr("domain.chat.stream.build_full_tutor_prompt_with_meta", lambda **kw: ("fake prompt", None))
    monkeypatch.setattr("domain.chat.stream.persist_turn", lambda *a, **kw: None)


class TestReasoningSummaryStreamTiming:
    """U5: reasoning summary appears at the right point in the stream."""

    def _make_request(self) -> "ChatRespondRequest":
        from core.schemas import ChatRespondRequest, GroundingMode
        return ChatRespondRequest(
            workspace_id=1, user_id=1, query="test",
            session_id=1, grounding_mode=GroundingMode.HYBRID,
        )

    def _collect(self, events: Iterator) -> list[dict[str, Any]]:
        return [e.model_dump(mode="json") for e in events]

    def test_summary_emitted_after_deltas_before_final(self, monkeypatch: Any) -> None:
        """When enabled + reasoning used, summary appears between trace and final."""
        from core.settings import Settings
        from domain.chat.stream import generate_chat_response_stream

        _stub_stream_monkeypatches(monkeypatch)

        trace = GenerationTrace(
            reasoning_requested=True, reasoning_supported=True,
            reasoning_used=True, reasoning_tokens=256,
            reasoning_effort="medium", reasoning_effort_source="settings",
        )

        class FakeStream:
            def __init__(self):
                self.trace = trace
            def __iter__(self):
                yield "Hello"
                yield " world"

        class FakeLLM:
            def generate_tutor_text_stream(self, prompt, prompt_meta=None, **kwargs):
                return FakeStream()

        monkeypatch.setattr("domain.chat.stream.build_tutor_llm_client", lambda settings: FakeLLM())

        settings = Settings(_env_file=None)
        monkeypatch.setattr(settings, "reasoning_summary_enabled", True)

        events = self._collect(
            generate_chat_response_stream(session=object(), request=self._make_request(), settings=settings)
        )

        event_types = [e["event"] for e in events]
        assert "reasoning_summary" in event_types, "summary event should be emitted"

        summary_idx = event_types.index("reasoning_summary")
        last_delta_idx = max(i for i, e in enumerate(events) if e.get("event") == "delta")
        final_idx = event_types.index("final")

        assert summary_idx > last_delta_idx, "summary must come after last delta"
        assert summary_idx < final_idx, "summary must come before final"

    def test_summary_not_emitted_when_disabled(self, monkeypatch: Any) -> None:
        """When reasoning_summary_enabled=False, no summary event."""
        from core.settings import Settings
        from domain.chat.stream import generate_chat_response_stream

        _stub_stream_monkeypatches(monkeypatch)

        trace = GenerationTrace(
            reasoning_requested=True, reasoning_supported=True,
            reasoning_used=True, reasoning_tokens=256,
        )

        class FakeStream:
            def __init__(self):
                self.trace = trace
            def __iter__(self):
                yield "Hello"

        class FakeLLM:
            def generate_tutor_text_stream(self, prompt, prompt_meta=None, **kwargs):
                return FakeStream()

        monkeypatch.setattr("domain.chat.stream.build_tutor_llm_client", lambda settings: FakeLLM())

        settings = Settings(_env_file=None)
        monkeypatch.setattr(settings, "reasoning_summary_enabled", False)

        events = self._collect(
            generate_chat_response_stream(session=object(), request=self._make_request(), settings=settings)
        )

        event_types = [e["event"] for e in events]
        assert "reasoning_summary" not in event_types

    def test_summary_not_on_final_envelope(self, monkeypatch: Any) -> None:
        """Final envelope must not carry reasoning summary text."""
        from core.settings import Settings
        from domain.chat.stream import generate_chat_response_stream

        _stub_stream_monkeypatches(monkeypatch)

        trace = GenerationTrace(
            reasoning_requested=True, reasoning_supported=True,
            reasoning_used=True, reasoning_tokens=256,
            reasoning_effort="medium", reasoning_effort_source="settings",
        )

        class FakeStream:
            def __init__(self):
                self.trace = trace
            def __iter__(self):
                yield "Hello"

        class FakeLLM:
            def generate_tutor_text_stream(self, prompt, prompt_meta=None, **kwargs):
                return FakeStream()

        monkeypatch.setattr("domain.chat.stream.build_tutor_llm_client", lambda settings: FakeLLM())

        settings = Settings(_env_file=None)
        monkeypatch.setattr(settings, "reasoning_summary_enabled", True)

        events = self._collect(
            generate_chat_response_stream(session=object(), request=self._make_request(), settings=settings)
        )

        final_events = [e for e in events if e.get("event") == "final"]
        assert len(final_events) == 1
        envelope = final_events[0]["envelope"]
        assert "reasoning_summary" not in envelope

    def test_summary_emitted_for_provider_reasoning_without_explicit_request(self, monkeypatch: Any) -> None:
        """When provider reports reasoning_tokens but app didn't request reasoning,
        summary should still be emitted (different wording)."""
        from core.settings import Settings
        from domain.chat.stream import generate_chat_response_stream

        _stub_stream_monkeypatches(monkeypatch)

        # Provider reported reasoning tokens, but app did NOT request explicit reasoning
        trace = GenerationTrace(
            reasoning_requested=False, reasoning_supported=True,
            reasoning_used=False, reasoning_tokens=512,
            reasoning_effort=None, reasoning_effort_source=None,
        )

        class FakeStream:
            def __init__(self):
                self.trace = trace
            def __iter__(self):
                yield "Hello"

        class FakeLLM:
            def generate_tutor_text_stream(self, prompt, prompt_meta=None, **kwargs):
                return FakeStream()

        monkeypatch.setattr("domain.chat.stream.build_tutor_llm_client", lambda settings: FakeLLM())

        settings = Settings(_env_file=None)
        monkeypatch.setattr(settings, "reasoning_summary_enabled", True)

        events = self._collect(
            generate_chat_response_stream(session=object(), request=self._make_request(), settings=settings)
        )

        event_types = [e["event"] for e in events]
        assert "reasoning_summary" in event_types, (
            "summary should fire for provider-reported reasoning even without explicit request"
        )

        summary_event = next(e for e in events if e["event"] == "reasoning_summary")
        assert "Provider reasoning" in summary_event["summary"]
        assert "512" in summary_event["summary"]
