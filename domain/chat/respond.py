"""Chat response orchestration with evidence verification."""

from __future__ import annotations

import logging

from core.observability import (
    SPAN_KIND_CHAIN,
    observation_context,
    record_content_enabled,
    set_input_output,
    start_span,
)
from core.schemas import (
    AssistantDraft,
    AssistantResponseEnvelope,
    AssistantResponseKind,
    ConceptSwitchSuggestion,
    ConversationMeta,
    GenerationTrace,
    GroundingMode,
)
from core.schemas.chat import ChatPhase
from core.settings import Settings, get_settings
from core.verifier import verify_assistant_draft
from sqlalchemy.orm import Session

from domain.chat.concept_resolver import resolve_concept_for_turn
from domain.chat.evidence_builder import (
    build_document_summaries_context,
    build_workspace_citations,
    build_workspace_evidence,
    filter_used_citations,
)
from domain.chat.progress import ProgressSink, noop_sink
from domain.chat.query_analyzer import run_query_analysis
from domain.chat.response_service import (
    build_quiz_context,
    build_tutor_llm_client,
    generate_tutor_text,
    resolve_mastery_status,
)
from domain.retrieval.evidence_planner import (
    build_evidence_plan,
    execute_evidence_plan,
)
from domain.chat.session_memory import (
    load_assessment_context,
    load_flashcard_progress,
    load_history_text,
    load_quiz_progress_snapshot,
    persist_turn,
)
from domain.chat.social_turns import try_social_response
from domain.chat.answer_parts import split_answer_parts
from domain.chat.turn_plan import build_turn_plan
from domain.readiness.analyzer import build_readiness_actions

from core.schemas import ChatRespondRequest  # noqa: E402

log = logging.getLogger("domain.chat.respond")


def generate_chat_response(
    session: Session,
    *,
    request: ChatRespondRequest,
    settings: Settings | None = None,
    progress: ProgressSink | None = None,
) -> AssistantResponseEnvelope:
    """Build a deterministic chat response and enforce citation policy."""
    sink = progress or noop_sink()
    with observation_context(
        component="chat",
        operation="chat.respond",
        workspace_id=request.workspace_id,
    ), start_span(
        "chat.respond",
        kind=SPAN_KIND_CHAIN,
        component="chat",
        operation="chat.respond",
        workspace_id=request.workspace_id,
    ) as span:
        set_input_output(span, input_value=request.query)
        # Correlation fields for Phoenix filtering
        if span is not None:
            if request.session_id is not None:
                span.set_attribute("session.id", request.session_id)
            if request.user_id is not None:
                span.set_attribute("user.id", request.user_id)
            if request.concept_id is not None:
                span.set_attribute("concept.id", request.concept_id)
        active_settings = settings or get_settings()
        grounding_mode = request.grounding_mode or active_settings.default_grounding_mode

        # ── Phase: thinking ───────────────────────────────────────────
        sink.on_phase(ChatPhase.THINKING)

        # ── Social intent fast-path ───────────────────────────────────
        social_llm = build_tutor_llm_client(settings=active_settings)
        social_envelope = try_social_response(
            query=request.query,
            grounding_mode=grounding_mode,
            settings=active_settings,
            social_llm=social_llm,
        )
        if social_envelope is not None:
            sink.on_phase(ChatPhase.FINALIZING)
            persist_turn(
                session,
                workspace_id=request.workspace_id,
                session_id=request.session_id,
                user_id=request.user_id,
                user_text=request.query,
                assistant_payload=social_envelope.model_dump(mode="json"),
            )
            set_input_output(span, output_value=social_envelope.text)
            return social_envelope

        # ── Standard grounded path ────────────────────────────────────
        # ── Phase: searching ──────────────────────────────────────────
        sink.on_phase(ChatPhase.SEARCHING)
        history_text = load_history_text(session, session_id=request.session_id)

        # ── Query analysis (AR1.1) ────────────────────────────────────
        query_analysis = run_query_analysis(
            query=request.query,
            history_summary=history_text,
            llm_client=social_llm,
        )
        log.info(
            "query_analysis intent=%s mode=%s retrieval=%s",
            query_analysis.intent,
            query_analysis.requested_mode,
            query_analysis.needs_retrieval,
        )

        assessment_context = load_assessment_context(
            session, session_id=request.session_id
        )

        concept_resolution = resolve_concept_for_turn(
            session,
            workspace_id=request.workspace_id,
            query=request.query,
            history_text=history_text,
            current_concept_id=request.concept_id,
            suggested_concept_id=request.suggested_concept_id,
            switch_decision=request.concept_switch_decision,
        )

        resolved_concept_id = (
            concept_resolution.resolved_concept.concept_id
            if concept_resolution.resolved_concept is not None
            else None
        )
        resolved_name = (
            concept_resolution.resolved_concept.canonical_name
            if concept_resolution.resolved_concept is not None
            else None
        )

        mastery_status = resolve_mastery_status(
            session=session,
            request=request,
            resolved_concept_id=resolved_concept_id,
        )

        # ── Learner profile snapshot (AR4.3) ──────────────────────────
        from domain.learner.assembler import assemble_learner_snapshot

        learner_snapshot = assemble_learner_snapshot(
            session,
            workspace_id=request.workspace_id,
            user_id=request.user_id,
            session_id=getattr(request, "session_id", None),
        )
        learner_profile_summary = learner_snapshot.summary_text()

        # ── Turn plan (AR1.2 / AR1.3) ────────────────────────────────
        turn_plan = build_turn_plan(
            query_analysis=query_analysis,
            mastery_status=mastery_status,
            resolved_concept_name=resolved_name,
            resolved_concept_id=resolved_concept_id,
            has_documents=True,
        )

        # ── Plan-gated retrieval via EvidencePlan (AR2.1 / AR2.2) ─────
        evidence_plan = build_evidence_plan(
            base_query=request.query,
            workspace_id=request.workspace_id,
            needs_retrieval=turn_plan.needs_retrieval,
            top_k=request.top_k,
            concept_id=(
                concept_resolution.resolved_concept.concept_id
                if concept_resolution.resolved_concept is not None
                else None
            ),
            concept_name=resolved_name,
            session=session,
        )
        evidence_plan, ranked_chunks = execute_evidence_plan(
            session,
            plan=evidence_plan,
            settings=active_settings,
        )

        # ── Empty workspace fast-path ─────────────────────────────────
        if evidence_plan.stop_reason == "empty_workspace":
            sink.on_phase(ChatPhase.FINALIZING)
            no_docs_text = (
                "It looks like your workspace doesn't have any documents yet! "
                "I'd love to help you learn, but I need some study material first.\n\n"
                "**Here's how to get started:**\n"
                "1. Head over to the **Knowledge Base** page\n"
                "2. Upload your notes, textbooks, or any study material (Markdown or text files)\n"
                "3. Come back here and ask me anything about them!\n\n"
                "Once you upload documents, I can provide Socratic guidance, "
                "generate quizzes, and help you master the material. 📚"
            )
            empty_ws_envelope = AssistantResponseEnvelope(
                kind=AssistantResponseKind.ANSWER,
                text=no_docs_text,
                grounding_mode=grounding_mode,
                evidence=[],
                citations=[],
                response_mode="onboarding",
                actions=[],
            )
            persist_turn(
                session,
                workspace_id=request.workspace_id,
                session_id=request.session_id,
                user_id=request.user_id,
                user_text=request.query,
                assistant_payload=empty_ws_envelope.model_dump(mode="json"),
            )
            set_input_output(span, output_value=empty_ws_envelope.text)
            return empty_ws_envelope

        evidence = build_workspace_evidence(
            session=session,
            workspace_id=request.workspace_id,
            chunks=ranked_chunks,
        )
        citations = build_workspace_citations(evidence)
        tutor_llm_client = build_tutor_llm_client(settings=active_settings)

        quiz_context_text = build_quiz_context(
            session=session,
            workspace_id=request.workspace_id,
            user_id=request.user_id,
            concept_id=resolved_concept_id,
        )

        flashcard_progress = load_flashcard_progress(
            session,
            workspace_id=request.workspace_id,
            user_id=request.user_id,
            concept_id=resolved_concept_id,
        )
        quiz_progress_snapshot = load_quiz_progress_snapshot(
            session,
            workspace_id=request.workspace_id,
            user_id=request.user_id,
            concept_id=resolved_concept_id,
        )
        combined_quiz_context = "\n\n".join(
            part for part in (quiz_context_text, quiz_progress_snapshot) if part
        )

        # ── Enrich span with assembled chat context ───────────────────
        log.info(
            "chat.respond ws=%s session=%s concept=%s chunks=%d confidence=%.2f clarify=%s plan_strategy=%s",
            request.workspace_id,
            request.session_id,
            resolved_name,
            len(ranked_chunks),
            concept_resolution.confidence,
            concept_resolution.requires_clarification,
            turn_plan.teaching_strategy,
        )
        if span is not None and record_content_enabled():
            span.set_attribute("chat.history_text_len", len(history_text))
            span.set_attribute("chat.assessment_context_len", len(assessment_context))
            span.set_attribute("chat.quiz_progress_snapshot_len", len(quiz_progress_snapshot))
            span.set_attribute("chat.flashcard_progress_len", len(flashcard_progress))
            span.set_attribute("chat.retrieval_chunk_count", len(ranked_chunks))
            span.set_attribute("chat.evidence_count", len(evidence))
            if resolved_name:
                span.set_attribute("chat.resolved_concept", resolved_name)
            span.set_attribute("chat.concept_confidence", concept_resolution.confidence)
            span.set_attribute("chat.requires_clarification", concept_resolution.requires_clarification)
            span.set_attribute("chat.plan_intent", turn_plan.intent)
            span.set_attribute("chat.plan_strategy", turn_plan.teaching_strategy)
            span.set_attribute("chat.plan_needs_retrieval", turn_plan.needs_retrieval)
            span.set_attribute("chat.evidence_plan_stop_reason", evidence_plan.stop_reason)
            span.set_attribute("chat.evidence_plan_budget", evidence_plan.retrieval_budget)
            if concept_resolution.switch_suggestion is not None:
                span.set_attribute(
                    "chat.switch_suggestion",
                    f"{concept_resolution.switch_suggestion.from_concept_name} -> {concept_resolution.switch_suggestion.to_concept_name}",
                )

        # ── Phase: responding (LLM generation) ────────────────────────
        sink.on_phase(ChatPhase.RESPONDING)
        generation_trace = None
        if concept_resolution.requires_clarification:
            assistant_text = concept_resolution.clarification_prompt
        else:
            assistant_text, generation_trace = generate_tutor_text(
                query=request.query,
                evidence=evidence,
                mastery_status=mastery_status,
                grounding_mode=grounding_mode,
                llm_client=tutor_llm_client,
                history_text=history_text,
                assessment_context=assessment_context,
                document_summaries=build_document_summaries_context(
                    session=session,
                    workspace_id=request.workspace_id,
                    chunks=ranked_chunks,
                ),
                quiz_context=combined_quiz_context,
                flashcard_progress=flashcard_progress,
                learner_profile_summary=learner_profile_summary,
            )

        draft = AssistantDraft(
            text=assistant_text,
            evidence=evidence,
            citations=citations,
        )
        allow_uncited_hybrid = (
            grounding_mode == GroundingMode.HYBRID
            and turn_plan.intent == "clarify"
            and not turn_plan.needs_retrieval
        )
        envelope = verify_assistant_draft(
            draft=draft,
            grounding_mode=grounding_mode,
            allow_uncited_hybrid=allow_uncited_hybrid,
        )
        envelope = filter_used_citations(envelope)

        meta = ConversationMeta(
            session_id=request.session_id,
            resolved_concept_id=resolved_concept_id,
            resolved_concept_name=resolved_name,
            concept_confidence=concept_resolution.confidence,
            requires_clarification=concept_resolution.requires_clarification,
            concept_switch_suggestion=(
                ConceptSwitchSuggestion(
                    from_concept_id=concept_resolution.switch_suggestion.from_concept_id,
                    from_concept_name=concept_resolution.switch_suggestion.from_concept_name,
                    to_concept_id=concept_resolution.switch_suggestion.to_concept_id,
                    to_concept_name=concept_resolution.switch_suggestion.to_concept_name,
                    reason=concept_resolution.switch_suggestion.reason,
                )
                if concept_resolution.switch_suggestion is not None
                else None
            ),
        )
        envelope = envelope.model_copy(update={"conversation_meta": meta})

        # ── Readiness CTA actions ─────────────────────────────────────
        actions: list[dict[str, object]] = []
        if request.user_id is not None:
            try:
                actions = build_readiness_actions(
                    session,
                    workspace_id=request.workspace_id,
                    user_id=request.user_id,
                    limit=2,
                )
            except Exception:
                if callable(getattr(session, "rollback", None)):
                    session.rollback()

        # ── Plan-driven quiz actions ──────────────────────────────────
        if turn_plan.should_start_quiz and turn_plan.quiz_concept_id is not None:
            actions.insert(0, {
                "action_type": "quiz_start",
                "label": "Start quiz now",
                "concept_id": turn_plan.quiz_concept_id,
                "concept_name": resolved_name,
            })
        elif turn_plan.should_offer_quiz and turn_plan.quiz_concept_id is not None:
            actions.insert(0, {
                "action_type": "quiz_offer",
                "label": "Ready for a quiz?",
                "concept_id": turn_plan.quiz_concept_id,
                "concept_name": resolved_name,
            })
        # ── Enrich trace with planner metadata ──────────────────────
        if generation_trace is None:
            generation_trace = GenerationTrace()
        generation_trace = generation_trace.model_copy(update={
            "plan_intent": turn_plan.intent,
            "plan_strategy": turn_plan.teaching_strategy,
            "plan_needs_retrieval": turn_plan.needs_retrieval,
            "plan_concept_hint": turn_plan.resolved_concept_hint,
            "plan_should_offer_quiz": turn_plan.should_offer_quiz,
            "plan_should_start_quiz": turn_plan.should_start_quiz,
            "evidence_plan_stop_reason": evidence_plan.stop_reason,
            "evidence_plan_budget": evidence_plan.retrieval_budget,
            "evidence_plan_chunk_count": evidence_plan.retrieved_chunk_count,
            "evidence_plan_passes": evidence_plan.retrieval_passes_used,
            "evidence_plan_retrieved_count": evidence_plan.retrieved_chunk_count,
            "evidence_plan_used_count": len(envelope.evidence) if envelope.evidence else 0,
            "learner_weak_topic_count": len(learner_snapshot.weak_topics),
            "learner_strong_topic_count": len(learner_snapshot.strong_topics),
            "learner_frontier_count": len(learner_snapshot.current_frontier),
            "learner_review_count": len(learner_snapshot.review_queue),
            "learner_profile_summary": learner_profile_summary or None,
        })

        envelope = envelope.model_copy(
            update={
                "actions": actions,
                "response_mode": envelope.response_mode,
                "generation_trace": generation_trace,
                "answer_parts": split_answer_parts(envelope.text),
            }
        )

        set_input_output(span, output_value=envelope.text)

        # ── Phase: finalizing ─────────────────────────────────────────
        sink.on_phase(ChatPhase.FINALIZING)
        persist_turn(
            session,
            workspace_id=request.workspace_id,
            session_id=request.session_id,
            user_id=request.user_id,
            user_text=request.query,
            assistant_payload=envelope.model_dump(mode="json"),
            concept_name=resolved_name,
        )
        return envelope


__all__ = ["generate_chat_response"]
