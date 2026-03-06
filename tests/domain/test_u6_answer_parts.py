"""Tests for U6: structured answer-parts contract."""

from __future__ import annotations

from core.schemas.assistant import AnswerParts, AssistantResponseEnvelope, AssistantResponseKind
from core.schemas.chat import ChatStreamAnswerPartEvent
from domain.chat.answer_parts import split_answer_parts
from core.llm_messages import MessageBuilder


class TestAnswerPartsSchema:
    """U6: AnswerParts model basics."""

    def test_body_only(self) -> None:
        parts = AnswerParts(body="Hello world")
        assert parts.body == "Hello world"
        assert parts.hint is None

    def test_body_and_hint(self) -> None:
        parts = AnswerParts(body="Main answer", hint="Think about it")
        assert parts.body == "Main answer"
        assert parts.hint == "Think about it"

    def test_serialization(self) -> None:
        parts = AnswerParts(body="Body", hint="Hint text")
        data = parts.model_dump(mode="json")
        assert data == {"body": "Body", "hint": "Hint text"}


class TestSplitAnswerParts:
    """U6: backend answer splitter."""

    def test_no_hint(self) -> None:
        result = split_answer_parts("This is a normal answer about derivatives.")
        assert result.body == "This is a normal answer about derivatives."
        assert result.hint is None

    def test_plain_hint_header(self) -> None:
        result = split_answer_parts("Main body here.\n\nHint: Think about the chain rule.")
        assert result.body == "Main body here."
        assert result.hint == "Think about the chain rule."

    def test_bold_hint_header(self) -> None:
        result = split_answer_parts("Main body.\n\n**Hint:** Consider the base case.")
        assert result.body == "Main body."
        assert result.hint == "Consider the base case."

    def test_emoji_hint(self) -> None:
        result = split_answer_parts("Body text.\n\n💡 Hint: Remember the formula.")
        assert result.body == "Body text."
        assert result.hint is not None

    def test_thinking_out_loud(self) -> None:
        result = split_answer_parts(
            "Great question!\n\nOne way to think about it is to consider what happens at the boundary."
        )
        assert result.body == "Great question!"
        assert result.hint is not None
        assert "consider" in result.hint.lower()

    def test_empty_text(self) -> None:
        result = split_answer_parts("")
        assert result.body == ""
        assert result.hint is None

    def test_whitespace_only(self) -> None:
        result = split_answer_parts("   ")
        assert result.body.strip() == ""
        assert result.hint is None

    def test_no_hint_in_prose(self) -> None:
        """Natural prose without hint markers should return full text as body."""
        text = "Let me guide you through this. What do you think happens when you increase the input?"
        result = split_answer_parts(text)
        assert result.body == text.strip()
        assert result.hint is None

    def test_hint_at_start_returns_no_hint(self) -> None:
        """If hint marker is at the very start, body would be empty → no split."""
        result = split_answer_parts("Hint: Just a hint with no body")
        assert result.hint is None  # empty body → no split


class TestChatStreamAnswerPartEvent:
    """U6: stream event for answer parts."""

    def test_event_type(self) -> None:
        parts = AnswerParts(body="Body", hint="Hint")
        event = ChatStreamAnswerPartEvent(parts=parts)
        assert event.event == "answer_parts"
        assert event.parts.body == "Body"

    def test_serialization(self) -> None:
        event = ChatStreamAnswerPartEvent(parts=AnswerParts(body="B"))
        data = event.model_dump(mode="json")
        assert data["event"] == "answer_parts"
        assert data["parts"]["body"] == "B"
        assert data["parts"]["hint"] is None


class TestEnvelopeAnswerParts:
    """U6: answer_parts on AssistantResponseEnvelope."""

    def test_envelope_without_answer_parts(self) -> None:
        """Backward compat: envelope without answer_parts is valid."""
        envelope = AssistantResponseEnvelope(
            kind=AssistantResponseKind.ANSWER,
            text="Hello",
            grounding_mode="hybrid",
            citations=[{
                "citation_id": "c1",
                "evidence_id": "e1",
                "label": "From your notes",
            }],
            evidence=[{
                "evidence_id": "e1",
                "source_type": "workspace",
                "content": "evidence",
                "document_id": 1,
                "chunk_id": 1,
                "chunk_index": 0,
            }],
        )
        assert envelope.answer_parts is None

    def test_envelope_with_answer_parts(self) -> None:
        envelope = AssistantResponseEnvelope(
            kind=AssistantResponseKind.ANSWER,
            text="Body\n\nHint: Think about it",
            grounding_mode="hybrid",
            citations=[{
                "citation_id": "c1",
                "evidence_id": "e1",
                "label": "From your notes",
            }],
            evidence=[{
                "evidence_id": "e1",
                "source_type": "workspace",
                "content": "evidence",
                "document_id": 1,
                "chunk_id": 1,
                "chunk_index": 0,
            }],
            answer_parts=AnswerParts(body="Body", hint="Think about it"),
        )
        assert envelope.answer_parts is not None
        assert envelope.answer_parts.hint == "Think about it"


class TestAnswerPartsStreamOrdering:
    """U7/U8: answer_parts event appears at the right point in the stream."""

    def test_answer_parts_after_deltas_before_final(self, monkeypatch) -> None:
        """answer_parts event appears after text deltas but before final."""
        from typing import Any
        from collections.abc import Iterator

        from core.schemas.assistant import GenerationTrace
        from core.settings import Settings
        from domain.chat.stream import generate_chat_response_stream
        from core.schemas import ChatRespondRequest, GroundingMode

        # Apply common monkeypatches
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
        monkeypatch.setattr("domain.chat.stream.build_tutor_messages", lambda **kw: (MessageBuilder().system("fake system").user("fake user"), None))
        monkeypatch.setattr("domain.chat.stream.persist_turn", lambda *a, **kw: None)
        monkeypatch.setattr("domain.chat.stream.persist_user_message", lambda s, **kw: 1)
        monkeypatch.setattr("domain.chat.stream.create_assistant_placeholder", lambda s, **kw: 1)
        monkeypatch.setattr("domain.chat.stream.finalize_assistant_message", lambda s, **kw: True)
        monkeypatch.setattr("domain.chat.stream._session_title_and_compact", lambda s, **kw: None)

        class FakeStream:
            def __init__(self):
                self.trace = GenerationTrace()
            def __iter__(self):
                yield "Main body."
                yield "\n\nHint: Think about it."

        class FakeLLM:
            def stream_messages(self, messages, *, prompt_meta=None, **kwargs):
                return FakeStream()

        monkeypatch.setattr("domain.chat.stream.build_tutor_llm_client", lambda settings: FakeLLM())

        request = ChatRespondRequest(
            workspace_id=1, user_id=1, query="test",
            session_id=1, grounding_mode=GroundingMode.HYBRID,
        )
        events = [e.model_dump(mode="json") for e in
                  generate_chat_response_stream(session=type("S", (), {"commit": lambda s: None, "rollback": lambda s: None})(), request=request)]

        event_types = [e["event"] for e in events]
        assert "answer_parts" in event_types, "answer_parts event should be emitted"

        ap_idx = event_types.index("answer_parts")
        last_delta_idx = max(i for i, e in enumerate(events) if e.get("event") == "delta")
        final_idx = event_types.index("final")

        assert ap_idx > last_delta_idx, "answer_parts must come after last delta"
        assert ap_idx < final_idx, "answer_parts must come before final"

        # Verify the answer_parts event has the right structure
        ap_event = events[ap_idx]
        assert ap_event["parts"]["body"] is not None
        # Hint should be detected from the "Hint:" pattern
        assert ap_event["parts"]["hint"] is not None
