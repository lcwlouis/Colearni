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
            "domain.chat.retrieval_context.retrieve_ranked_chunks",
            lambda session, **kwargs: [fake_chunk],
        )
        monkeypatch.setattr(
            "domain.chat.retrieval_context.workspace_has_no_chunks",
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
        monkeypatch.setenv("APP_INCLUDE_DEV_STATS", "true")
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


class TestPlannerTraceFields:
    """AR1.4: Verify planner trace metadata on GenerationTrace."""

    def test_plan_fields_default_to_none(self) -> None:
        trace = GenerationTrace()
        assert trace.plan_intent is None
        assert trace.plan_strategy is None
        assert trace.plan_needs_retrieval is None
        assert trace.plan_concept_hint is None
        assert trace.plan_should_offer_quiz is None
        assert trace.plan_should_start_quiz is None

    def test_plan_fields_set_and_serialize(self) -> None:
        trace = GenerationTrace(
            provider="openai",
            model="gpt-4o",
            plan_intent="teach",
            plan_strategy="socratic",
            plan_needs_retrieval=True,
            plan_concept_hint="photosynthesis",
            plan_should_offer_quiz=False,
            plan_should_start_quiz=False,
        )
        assert trace.plan_intent == "teach"
        assert trace.plan_strategy == "socratic"
        assert trace.plan_needs_retrieval is True
        assert trace.plan_concept_hint == "photosynthesis"

        payload = trace.model_dump(mode="json")
        assert payload["plan_intent"] == "teach"
        assert payload["plan_strategy"] == "socratic"
        assert payload["plan_needs_retrieval"] is True
        assert payload["plan_concept_hint"] == "photosynthesis"
        assert payload["plan_should_offer_quiz"] is False
        assert payload["plan_should_start_quiz"] is False

    def test_plan_fields_round_trip_through_envelope(self) -> None:
        from core.schemas import Citation

        trace = GenerationTrace(
            plan_intent="clarify",
            plan_strategy="clarify",
            plan_needs_retrieval=False,
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
        restored = AssistantResponseEnvelope.model_validate(payload)
        assert restored.generation_trace is not None
        assert restored.generation_trace.plan_intent == "clarify"
        assert restored.generation_trace.plan_strategy == "clarify"
        assert restored.generation_trace.plan_needs_retrieval is False

    def test_model_copy_merges_plan_fields(self) -> None:
        base = GenerationTrace(provider="openai", model="gpt-4o", timing_ms=100.0)
        enriched = base.model_copy(update={
            "plan_intent": "teach",
            "plan_strategy": "direct",
            "plan_needs_retrieval": True,
            "plan_should_offer_quiz": True,
            "plan_should_start_quiz": False,
        })
        assert enriched.provider == "openai"
        assert enriched.timing_ms == 100.0
        assert enriched.plan_intent == "teach"
        assert enriched.plan_strategy == "direct"
        assert enriched.plan_should_offer_quiz is True


class TestBackgroundTraceFields:
    """AR6.3: Verify background observability trace fields on GenerationTrace."""

    def test_bg_fields_default_to_none(self) -> None:
        trace = GenerationTrace()
        assert trace.bg_digest_available is None
        assert trace.bg_frontier_suggestion_count is None
        assert trace.bg_research_candidate_pending is None
        assert trace.bg_research_candidate_approved is None

    def test_bg_fields_set_and_serialize(self) -> None:
        trace = GenerationTrace(
            bg_digest_available=True,
            bg_frontier_suggestion_count=3,
            bg_research_candidate_pending=5,
            bg_research_candidate_approved=2,
        )
        assert trace.bg_digest_available is True
        assert trace.bg_frontier_suggestion_count == 3

        payload = trace.model_dump(mode="json")
        assert payload["bg_digest_available"] is True
        assert payload["bg_frontier_suggestion_count"] == 3
        assert payload["bg_research_candidate_pending"] == 5
        assert payload["bg_research_candidate_approved"] == 2

    def test_bg_fields_round_trip_through_envelope(self) -> None:
        from core.schemas import Citation

        trace = GenerationTrace(
            bg_digest_available=True,
            bg_frontier_suggestion_count=2,
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
        restored = AssistantResponseEnvelope.model_validate(payload)
        assert restored.generation_trace is not None
        assert restored.generation_trace.bg_digest_available is True
        assert restored.generation_trace.bg_frontier_suggestion_count == 2
