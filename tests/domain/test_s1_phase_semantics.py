"""Tests for S1: responding phase is emitted only after first visible delta."""

from __future__ import annotations

from typing import Any
from collections.abc import Iterator

import pytest
from core.schemas.chat import ChatPhase, ChatStreamEvent
from domain.chat.stream import generate_chat_response_stream
from core.schemas import ChatRespondRequest, GroundingMode


def _make_request(**overrides: Any) -> ChatRespondRequest:
    defaults = dict(
        workspace_id=1,
        user_id=1,
        query="explain tensors",
        session_id=1,
        grounding_mode=GroundingMode.HYBRID,
    )
    defaults.update(overrides)
    return ChatRespondRequest(**defaults)


def _collect_events(
    events: Iterator[ChatStreamEvent],
) -> list[dict[str, Any]]:
    return [e.model_dump(mode="json") for e in events]


def _extract_phases(events: list[dict[str, Any]]) -> list[str]:
    return [e["phase"] for e in events if e.get("event") == "status"]


class TestRespondingPhaseSemantics:
    """S1: ``responding`` must only appear after first visible text delta."""

    def test_social_path_skips_responding(self, monkeypatch: Any) -> None:
        """Social fast-path: thinking → finalizing (no responding)."""
        from core.schemas import AssistantResponseEnvelope, AssistantResponseKind

        social_env = AssistantResponseEnvelope(
            kind=AssistantResponseKind.ANSWER,
            text="Hey!",
            grounding_mode=GroundingMode.HYBRID,
            response_mode="social",
        )
        monkeypatch.setattr("domain.chat.stream.try_social_response", lambda **kw: social_env)
        monkeypatch.setattr("domain.chat.stream.build_tutor_llm_client", lambda settings: None)
        monkeypatch.setattr("domain.chat.stream.persist_turn", lambda *a, **kw: None)

        events = _collect_events(
            generate_chat_response_stream(session=object(), request=_make_request())
        )
        phases = _extract_phases(events)
        assert "responding" not in phases
        assert phases == ["thinking", "finalizing"]

    def test_onboarding_path_skips_responding(self, monkeypatch: Any) -> None:
        """No-docs fast-path: thinking → searching → finalizing (no responding)."""
        monkeypatch.setattr("domain.chat.stream.try_social_response", lambda **kw: None)
        monkeypatch.setattr("domain.chat.stream.build_tutor_llm_client", lambda settings: None)
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
        monkeypatch.setattr("domain.chat.retrieval_context.retrieve_ranked_chunks", lambda s, **kw: [])
        monkeypatch.setattr("domain.chat.retrieval_context.workspace_has_no_chunks", lambda s, workspace_id: True)
        monkeypatch.setattr("domain.chat.stream.persist_turn", lambda *a, **kw: None)

        events = _collect_events(
            generate_chat_response_stream(session=object(), request=_make_request())
        )
        phases = _extract_phases(events)
        assert "responding" not in phases
        assert phases == ["thinking", "searching", "finalizing"]

    def test_streaming_path_responding_after_first_delta(self, monkeypatch: Any) -> None:
        """When LLM streams, responding appears after first non-empty delta."""
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
        # Return some chunks so it doesn't hit the no-docs fast-path
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

        # Create a fake streaming LLM client
        class FakeStream:
            trace = None
            def __init__(self):
                self._deltas = ["Hello", " world", "!"]
            def __iter__(self):
                return iter(self._deltas)

        class FakeLLM:
            def generate_tutor_text_stream(self, prompt: str, prompt_meta=None, **kwargs) -> FakeStream:
                return FakeStream()

        monkeypatch.setattr("domain.chat.stream.build_tutor_llm_client", lambda settings: FakeLLM())

        events = _collect_events(
            generate_chat_response_stream(session=object(), request=_make_request())
        )

        phases = _extract_phases(events)
        assert "responding" in phases, "responding phase should be emitted"

        # Find the position of the responding event and first delta
        responding_idx = next(i for i, e in enumerate(events) if e.get("phase") == "responding")
        first_delta_idx = next(i for i, e in enumerate(events) if e.get("event") == "delta")

        # responding must be emitted at or before the first delta, not before LLM call
        assert responding_idx <= first_delta_idx, (
            f"responding (idx={responding_idx}) should appear at or before first delta (idx={first_delta_idx})"
        )

        # responding must NOT appear before searching
        searching_idx = next(i for i, e in enumerate(events) if e.get("phase") == "searching")
        assert responding_idx > searching_idx

        # Phase sequence should be: thinking, searching, responding, finalizing
        assert phases == ["thinking", "searching", "responding", "finalizing"]

    def test_responding_not_emitted_for_empty_stream(self, monkeypatch: Any) -> None:
        """If LLM streams only empty deltas, responding is skipped."""
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

        class EmptyStream:
            trace = None
            def __iter__(self):
                return iter(["", "", ""])

        class FakeLLM:
            def generate_tutor_text_stream(self, prompt: str, prompt_meta=None, **kwargs) -> EmptyStream:
                return EmptyStream()

        monkeypatch.setattr("domain.chat.stream.build_tutor_llm_client", lambda settings: FakeLLM())

        events = _collect_events(
            generate_chat_response_stream(session=object(), request=_make_request())
        )
        phases = _extract_phases(events)
        # Empty stream = no visible content = no responding phase
        assert "responding" not in phases
