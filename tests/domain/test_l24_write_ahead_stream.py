"""Tests for L2.4: write-ahead + finalize pattern in streaming."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from core.llm_messages import MessageBuilder
from core.schemas import ChatRespondRequest, GroundingMode
from core.schemas.chat import ChatPhase, ChatStreamEvent, ChatStreamFinalEvent
from domain.chat.stream import generate_chat_response_stream


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


def _fake_session() -> Any:
    return type(
        "FakeSession", (), {"commit": lambda self: None, "rollback": lambda self: None}
    )()


def _collect_events(events) -> list[dict[str, Any]]:
    return [e.model_dump(mode="json") for e in events]


def _apply_streaming_patches(monkeypatch: Any) -> None:
    """Common monkeypatches for streaming tests (non-social path)."""
    monkeypatch.setattr("domain.chat.stream.try_social_response", lambda **kw: None)
    monkeypatch.setattr("domain.chat.stream.load_history_text", lambda s, session_id: "")
    monkeypatch.setattr("domain.chat.stream.load_history_turns", lambda s, session_id: ("", []))
    monkeypatch.setattr("domain.chat.stream.load_assessment_context", lambda s, session_id: "")
    monkeypatch.setattr("domain.chat.stream.persist_turn", lambda *a, **kw: None)
    monkeypatch.setattr("domain.chat.stream._session_title_and_compact", lambda s, **kw: None)
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
    monkeypatch.setattr(
        "domain.chat.stream.build_tutor_messages",
        lambda **kw: (MessageBuilder().system("fake").user("fake"), None),
    )

    class FakeStream:
        trace = None
        def __iter__(self):
            return iter(["Hello", " world!"])

    class FakeLLM:
        def stream_messages(self, messages, *, prompt_meta=None, **kw):
            return FakeStream()

    monkeypatch.setattr("domain.chat.stream.build_tutor_llm_client", lambda settings: FakeLLM())


class TestWriteAheadPersistence:
    """L2.4: user message + placeholder exist before streaming completes."""

    def test_user_message_persisted_before_streaming(self, monkeypatch: Any) -> None:
        """persist_user_message is called before any LLM delta is emitted."""
        calls: list[str] = []

        def fake_persist_user(s, **kw):
            calls.append("persist_user_message")
            return 1

        def fake_create_placeholder(s, **kw):
            calls.append("create_assistant_placeholder")
            return 42

        def fake_finalize(s, **kw):
            calls.append("finalize_assistant_message")
            return True

        _apply_streaming_patches(monkeypatch)
        monkeypatch.setattr("domain.chat.stream.persist_user_message", fake_persist_user)
        monkeypatch.setattr("domain.chat.stream.create_assistant_placeholder", fake_create_placeholder)
        monkeypatch.setattr("domain.chat.stream.finalize_assistant_message", fake_finalize)

        events = _collect_events(
            generate_chat_response_stream(session=_fake_session(), request=_make_request())
        )
        # User message + placeholder created before any delta
        first_delta_idx = next(
            (i for i, e in enumerate(events) if e.get("event") == "delta"), None
        )
        assert first_delta_idx is not None, "should emit deltas"
        assert "persist_user_message" in calls
        assert "create_assistant_placeholder" in calls
        assert calls.index("persist_user_message") < calls.index("create_assistant_placeholder")

    def test_finalize_called_on_success(self, monkeypatch: Any) -> None:
        """finalize_assistant_message is called with the envelope payload."""
        finalize_calls: list[dict[str, Any]] = []

        def fake_finalize(s, *, message_id, payload):
            finalize_calls.append({"message_id": message_id, "payload": payload})
            return True

        _apply_streaming_patches(monkeypatch)
        monkeypatch.setattr("domain.chat.stream.persist_user_message", lambda s, **kw: 1)
        monkeypatch.setattr("domain.chat.stream.create_assistant_placeholder", lambda s, **kw: 99)
        monkeypatch.setattr("domain.chat.stream.finalize_assistant_message", fake_finalize)

        events = _collect_events(
            generate_chat_response_stream(session=_fake_session(), request=_make_request())
        )
        assert len(finalize_calls) == 1
        assert finalize_calls[0]["message_id"] == 99
        assert "text" in finalize_calls[0]["payload"]

    def test_fail_called_on_error(self, monkeypatch: Any) -> None:
        """fail_assistant_message is called when an exception occurs during streaming."""
        fail_calls: list[dict[str, Any]] = []

        def fake_fail(s, *, message_id, partial_text=""):
            fail_calls.append({"message_id": message_id, "partial_text": partial_text})
            return True

        _apply_streaming_patches(monkeypatch)
        monkeypatch.setattr("domain.chat.stream.persist_user_message", lambda s, **kw: 1)
        monkeypatch.setattr("domain.chat.stream.create_assistant_placeholder", lambda s, **kw: 77)
        monkeypatch.setattr("domain.chat.stream.finalize_assistant_message", lambda s, **kw: True)
        monkeypatch.setattr("domain.chat.stream.fail_assistant_message", fake_fail)

        # Make verification raise to trigger error path
        monkeypatch.setattr(
            "domain.chat.stream.verify_assistant_draft",
            lambda **kw: (_ for _ in ()).throw(RuntimeError("LLM boom")),
        )

        events = _collect_events(
            generate_chat_response_stream(session=_fake_session(), request=_make_request())
        )
        error_events = [e for e in events if e.get("event") == "error"]
        assert len(error_events) == 1
        assert len(fail_calls) == 1
        assert fail_calls[0]["message_id"] == 77

    def test_placeholder_failure_continues_streaming(self, monkeypatch: Any) -> None:
        """If create_assistant_placeholder fails, streaming continues with persist_turn fallback."""
        persist_turn_calls: list[bool] = []

        def fake_persist_turn(*a, **kw):
            persist_turn_calls.append(True)

        _apply_streaming_patches(monkeypatch)
        monkeypatch.setattr("domain.chat.stream.persist_user_message", lambda s, **kw: 1)
        monkeypatch.setattr(
            "domain.chat.stream.create_assistant_placeholder",
            lambda s, **kw: (_ for _ in ()).throw(RuntimeError("DB error")),
        )
        monkeypatch.setattr("domain.chat.stream.persist_turn", fake_persist_turn)

        events = _collect_events(
            generate_chat_response_stream(session=_fake_session(), request=_make_request())
        )
        final_events = [e for e in events if e.get("event") == "final"]
        assert len(final_events) == 1, "should still emit final event"
        assert len(persist_turn_calls) == 1, "should fall back to persist_turn"

    def test_social_path_skips_write_ahead(self, monkeypatch: Any) -> None:
        """Social fast-path does NOT call write-ahead functions."""
        from core.schemas import AssistantResponseEnvelope, AssistantResponseKind

        calls: list[str] = []

        social_env = AssistantResponseEnvelope(
            kind=AssistantResponseKind.ANSWER,
            text="Hey!",
            grounding_mode=GroundingMode.HYBRID,
            response_mode="social",
        )
        monkeypatch.setattr("domain.chat.stream.try_social_response", lambda **kw: social_env)
        monkeypatch.setattr("domain.chat.stream.build_tutor_llm_client", lambda settings: None)
        monkeypatch.setattr("domain.chat.stream.persist_turn", lambda *a, **kw: None)
        monkeypatch.setattr(
            "domain.chat.stream.persist_user_message",
            lambda s, **kw: calls.append("persist") or 1,
        )
        monkeypatch.setattr(
            "domain.chat.stream.create_assistant_placeholder",
            lambda s, **kw: calls.append("placeholder") or 1,
        )

        events = _collect_events(
            generate_chat_response_stream(session=_fake_session(), request=_make_request())
        )
        assert "persist" not in calls
        assert "placeholder" not in calls

    def test_no_write_ahead_when_session_id_none(self, monkeypatch: Any) -> None:
        """Write-ahead is skipped when session_id is None."""
        calls: list[str] = []

        _apply_streaming_patches(monkeypatch)
        monkeypatch.setattr(
            "domain.chat.stream.persist_user_message",
            lambda s, **kw: calls.append("persist") or 1,
        )
        monkeypatch.setattr(
            "domain.chat.stream.create_assistant_placeholder",
            lambda s, **kw: calls.append("placeholder") or 1,
        )

        request = _make_request(session_id=None)
        events = _collect_events(
            generate_chat_response_stream(session=_fake_session(), request=request)
        )
        assert "persist" not in calls
        assert "placeholder" not in calls
