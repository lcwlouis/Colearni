"""Tests for G5: trace capture on blocking path and persistence round-trip."""

from __future__ import annotations

import json

from core.schemas.assistant import AssistantResponseEnvelope, GenerationTrace


class TestTraceOnBlockingEnvelope:
    """Verify the blocking path attaches generation_trace to the envelope."""

    def test_trace_included_on_grounded_response(self, monkeypatch) -> None:
        from core.schemas import Citation, EvidenceItem, EvidenceSourceType
        from core.settings import Settings
        from domain.retrieval.types import RankedChunk

        fake_trace = GenerationTrace(
            provider="openai",
            model="gpt-4o",
            timing_ms=123.45,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )

        monkeypatch.setattr(
            "domain.chat.respond.try_social_response",
            lambda **kwargs: None,
        )
        monkeypatch.setattr(
            "domain.chat.respond.build_tutor_llm_client",
            lambda settings: None,
        )
        monkeypatch.setattr(
            "domain.chat.respond.load_history_text",
            lambda session, session_id: "",
        )
        monkeypatch.setattr(
            "domain.chat.respond.load_assessment_context",
            lambda session, session_id: "",
        )
        monkeypatch.setattr(
            "domain.chat.respond.resolve_concept_for_turn",
            lambda session, **kwargs: type(
                "R", (), {
                    "resolved_concept": None,
                    "confidence": 0.0,
                    "requires_clarification": False,
                    "switch_suggestion": None,
                    "clarification_prompt": None,
                }
            )(),
        )

        fake_chunk = RankedChunk(
            workspace_id=1, chunk_id=1, document_id=1,
            chunk_index=0, text="test", score=0.9,
            retrieval_method="hybrid",
        )
        monkeypatch.setattr(
            "domain.chat.respond.retrieve_ranked_chunks",
            lambda session, **kwargs: [fake_chunk],
        )
        monkeypatch.setattr(
            "domain.chat.respond.workspace_has_no_chunks",
            lambda session, workspace_id: False,
        )
        monkeypatch.setattr(
            "domain.chat.respond.build_workspace_evidence",
            lambda **kwargs: [EvidenceItem(
                evidence_id="e1",
                source_type=EvidenceSourceType.WORKSPACE,
                content="test", document_id=1, chunk_id=1, chunk_index=0,
            )],
        )
        monkeypatch.setattr(
            "domain.chat.respond.build_workspace_citations",
            lambda evidence: [Citation(citation_id="c1", evidence_id="e1", label="From your notes")],
        )
        monkeypatch.setattr(
            "domain.chat.respond.resolve_mastery_status",
            lambda **kwargs: None,
        )
        monkeypatch.setattr(
            "domain.chat.respond.build_quiz_context",
            lambda **kwargs: "",
        )
        monkeypatch.setattr(
            "domain.chat.respond.load_flashcard_progress",
            lambda session, **kwargs: "",
        )
        monkeypatch.setattr(
            "domain.chat.respond.generate_tutor_text",
            lambda **kwargs: ("SOCRATIC: answer", fake_trace),
        )
        monkeypatch.setattr(
            "domain.chat.respond.build_document_summaries_context",
            lambda **kwargs: "",
        )
        monkeypatch.setattr(
            "domain.chat.respond.build_readiness_actions",
            lambda session, **kwargs: [],
        )

        persisted: dict = {}

        def capture_persist(*args, **kwargs):
            persisted.update(kwargs)

        monkeypatch.setattr(
            "domain.chat.respond.persist_turn",
            capture_persist,
        )

        from core.schemas import ChatRespondRequest
        from domain.chat.respond import generate_chat_response

        req = ChatRespondRequest(workspace_id=1, query="explain linear maps")
        result = generate_chat_response(
            object(),  # type: ignore[arg-type]
            request=req,
            settings=Settings(_env_file=None),
        )

        # Trace is attached to envelope
        assert result.generation_trace is not None
        assert result.generation_trace.provider == "openai"
        assert result.generation_trace.model == "gpt-4o"
        assert result.generation_trace.timing_ms == 123.45
        assert result.generation_trace.prompt_tokens == 100

    def test_trace_absent_for_social_path(self, monkeypatch) -> None:
        from core.schemas import AssistantResponseKind, GroundingMode
        from core.settings import Settings

        social_env = AssistantResponseEnvelope(
            kind=AssistantResponseKind.ANSWER,
            text="Hi!",
            grounding_mode=GroundingMode.HYBRID,
            response_mode="social",
        )
        monkeypatch.setattr(
            "domain.chat.respond.try_social_response",
            lambda **kwargs: social_env,
        )
        monkeypatch.setattr(
            "domain.chat.respond.build_tutor_llm_client",
            lambda settings: None,
        )
        monkeypatch.setattr(
            "domain.chat.respond.persist_turn",
            lambda *args, **kwargs: None,
        )

        from core.schemas import ChatRespondRequest
        from domain.chat.respond import generate_chat_response

        req = ChatRespondRequest(workspace_id=1, query="hello")
        result = generate_chat_response(
            object(),  # type: ignore[arg-type]
            request=req,
            settings=Settings(_env_file=None),
        )
        assert result.generation_trace is None


class TestTracePersistenceRoundTrip:
    """Verify that generation_trace survives JSON serialization (persist_turn stores model_dump)."""

    def test_trace_serializes_and_deserializes(self) -> None:
        from core.schemas import Citation

        trace = GenerationTrace(
            provider="litellm",
            model="qwen/qwen3-30b-a3b",
            timing_ms=456.78,
            prompt_tokens=200,
            completion_tokens=100,
            total_tokens=300,
            reasoning_tokens=50,
        )
        envelope = AssistantResponseEnvelope(
            kind="answer",
            text="Test",
            grounding_mode="hybrid",
            generation_trace=trace,
            evidence=[],
            citations=[Citation(citation_id="c1", evidence_id="e1", label="From your notes")],
        )

        payload = envelope.model_dump(mode="json")
        assert "generation_trace" in payload
        assert payload["generation_trace"]["provider"] == "litellm"
        assert payload["generation_trace"]["reasoning_tokens"] == 50

        restored = AssistantResponseEnvelope.model_validate(payload)
        assert restored.generation_trace is not None
        assert restored.generation_trace.provider == "litellm"
        assert restored.generation_trace.timing_ms == 456.78

    def test_null_trace_round_trips(self) -> None:
        from core.schemas import Citation

        envelope = AssistantResponseEnvelope(
            kind="answer",
            text="Test",
            grounding_mode="hybrid",
            evidence=[],
            citations=[Citation(citation_id="c1", evidence_id="e1", label="From your notes")],
        )
        payload = envelope.model_dump(mode="json")
        assert payload["generation_trace"] is None

        restored = AssistantResponseEnvelope.model_validate(payload)
        assert restored.generation_trace is None
