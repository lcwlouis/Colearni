"""Unit tests for G1: domain lifecycle progress extraction."""

from __future__ import annotations

from core.schemas.chat import ChatPhase
from domain.chat.progress import ProgressSink, noop_sink


class RecordingSink:
    """Test double that records emitted phases in order."""

    def __init__(self) -> None:
        self.phases: list[ChatPhase] = []

    def on_phase(self, phase: ChatPhase) -> None:
        self.phases.append(phase)


class TestProgressSinkProtocol:
    def test_noop_sink_satisfies_protocol(self) -> None:
        sink: ProgressSink = noop_sink()
        sink.on_phase(ChatPhase.THINKING)

    def test_noop_is_singleton(self) -> None:
        assert noop_sink() is noop_sink()

    def test_recording_sink_captures_phases(self) -> None:
        sink = RecordingSink()
        sink.on_phase(ChatPhase.THINKING)
        sink.on_phase(ChatPhase.SEARCHING)
        sink.on_phase(ChatPhase.RESPONDING)
        sink.on_phase(ChatPhase.FINALIZING)
        assert sink.phases == [
            ChatPhase.THINKING,
            ChatPhase.SEARCHING,
            ChatPhase.RESPONDING,
            ChatPhase.FINALIZING,
        ]


class TestOrchestrationPhaseOrder:
    """Verify generate_chat_response() emits phases in correct order."""

    def test_social_path_emits_thinking_then_finalizing(self, monkeypatch) -> None:
        """Social fast-path should emit thinking -> finalizing."""
        from core.schemas import AssistantResponseEnvelope, AssistantResponseKind, GroundingMode
        from core.settings import Settings

        social_env = AssistantResponseEnvelope(
            kind=AssistantResponseKind.ANSWER,
            text="Hey there!",
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
        sink = RecordingSink()
        result = generate_chat_response(
            object(),  # type: ignore[arg-type]
            request=req,
            settings=Settings(_env_file=None),
            progress=sink,
        )

        assert result.response_mode == "social"
        assert sink.phases == [ChatPhase.THINKING, ChatPhase.FINALIZING]

    def test_onboarding_path_emits_thinking_searching_finalizing(self, monkeypatch) -> None:
        """Empty workspace path should emit thinking -> searching -> finalizing."""
        from core.settings import Settings
        from domain.chat.query_analyzer import QueryAnalysis

        monkeypatch.setattr(
            "domain.chat.respond.try_social_response",
            lambda **kwargs: None,
        )
        monkeypatch.setattr(
            "domain.chat.respond.build_tutor_llm_client",
            lambda settings: None,
        )
        monkeypatch.setattr(
            "domain.chat.respond.run_query_analysis",
            lambda **kwargs: QueryAnalysis(intent="clarify", needs_retrieval=True),
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
        monkeypatch.setattr(
            "domain.chat.retrieval_context.retrieve_ranked_chunks",
            lambda session, **kwargs: [],
        )
        monkeypatch.setattr(
            "domain.chat.retrieval_context.workspace_has_no_chunks",
            lambda session, workspace_id: True,
        )
        monkeypatch.setattr(
            "domain.chat.respond.persist_turn",
            lambda *args, **kwargs: None,
        )

        from core.schemas import ChatRespondRequest
        from domain.chat.respond import generate_chat_response

        req = ChatRespondRequest(workspace_id=1, query="hello")
        sink = RecordingSink()
        result = generate_chat_response(
            object(),  # type: ignore[arg-type]
            request=req,
            settings=Settings(_env_file=None),
            progress=sink,
        )

        assert result.response_mode == "onboarding"
        assert sink.phases == [ChatPhase.THINKING, ChatPhase.SEARCHING, ChatPhase.FINALIZING]

    def test_grounded_path_emits_all_four_phases(self, monkeypatch) -> None:
        """Full grounded path should emit thinking -> searching -> responding -> finalizing."""
        from core.schemas import EvidenceItem, EvidenceSourceType
        from core.settings import Settings

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

        from domain.retrieval.types import RankedChunk
        fake_chunk = RankedChunk(
            workspace_id=1, chunk_id=1, document_id=1,
            chunk_index=0, text="test content", score=0.9,
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

        fake_evidence = [EvidenceItem(
            evidence_id="e1",
            source_type=EvidenceSourceType.WORKSPACE,
            content="test",
            document_id=1, chunk_id=1, chunk_index=0,
        )]
        monkeypatch.setattr(
            "domain.chat.respond.build_workspace_evidence",
            lambda **kwargs: fake_evidence,
        )
        from core.schemas import Citation
        monkeypatch.setattr(
            "domain.chat.respond.build_workspace_citations",
            lambda evidence: [Citation(
                citation_id="c1", evidence_id="e1",
                label="From your notes",
            )],
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
            lambda **kwargs: ("SOCRATIC: test answer", None),
        )
        monkeypatch.setattr(
            "domain.chat.respond.build_document_summaries_context",
            lambda **kwargs: "",
        )
        monkeypatch.setattr(
            "domain.chat.respond.build_readiness_actions",
            lambda session, **kwargs: [],
        )
        monkeypatch.setattr(
            "domain.chat.respond.persist_turn",
            lambda *args, **kwargs: None,
        )

        from core.schemas import ChatRespondRequest
        from domain.chat.respond import generate_chat_response

        req = ChatRespondRequest(workspace_id=1, query="what is linear algebra")
        sink = RecordingSink()
        result = generate_chat_response(
            object(),  # type: ignore[arg-type]
            request=req,
            settings=Settings(_env_file=None),
            progress=sink,
        )

        assert result.kind.value == "answer"
        assert sink.phases == [
            ChatPhase.THINKING,
            ChatPhase.SEARCHING,
            ChatPhase.RESPONDING,
            ChatPhase.FINALIZING,
        ]

    def test_default_progress_is_noop(self, monkeypatch) -> None:
        """Calling without progress= should not raise."""
        from core.schemas import AssistantResponseEnvelope, AssistantResponseKind, GroundingMode
        from core.settings import Settings

        social_env = AssistantResponseEnvelope(
            kind=AssistantResponseKind.ANSWER,
            text="Hey!",
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

        req = ChatRespondRequest(workspace_id=1, query="hi")
        result = generate_chat_response(
            object(),  # type: ignore[arg-type]
            request=req,
            settings=Settings(_env_file=None),
        )
        assert result.text == "Hey!"
