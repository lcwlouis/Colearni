"""Streaming chat response orchestration.

Yields ``ChatStreamEvent`` objects that the SSE route converts to
``text/event-stream`` frames.  Re-uses the same domain helpers as the
blocking path to keep verification and persistence ordering intact.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

from core.contracts import TutorTextStream
from core.observability import (
    SPAN_KIND_CHAIN,
    create_span,
    set_input_output,
)
from core.schemas import (
    AssistantDraft,
    AssistantResponseEnvelope,
    AssistantResponseKind,
    ChatRespondRequest,
    ConceptSwitchSuggestion,
    ConversationMeta,
    GroundingMode,
)
from core.schemas.assistant import GenerationTrace
from core.schemas.chat import (
    ChatPhase,
    ChatStreamAnswerPartEvent,
    ChatStreamDeltaEvent,
    ChatStreamErrorEvent,
    ChatStreamEvent,
    ChatStreamFinalEvent,
    ChatStreamReasoningSummaryEvent,
    ChatStreamStatusEvent,
    ChatStreamTraceEvent,
)
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
from domain.chat.query_analyzer import run_query_analysis
from domain.chat.response_service import (
    build_quiz_context,
    build_tutor_llm_client,
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
from domain.chat.prompt_kit import build_full_tutor_prompt_with_meta, get_persona
from domain.chat.tutor_agent import resolve_tutor_style
from domain.chat.answer_parts import split_answer_parts
from domain.chat.turn_plan import build_turn_plan
from domain.readiness.analyzer import build_readiness_actions

log = logging.getLogger("domain.chat.stream")


def generate_chat_response_stream(
    session: Session,
    *,
    request: ChatRespondRequest,
    settings: Settings | None = None,
) -> Iterator[ChatStreamEvent]:
    """Yield stream events for a chat response, ending with ``final`` or ``error``."""
    active_settings = settings or get_settings()
    grounding_mode = request.grounding_mode or active_settings.default_grounding_mode

    # Manual span lifecycle – context managers cannot wrap generators that
    # cross async boundaries (Starlette runs sync generators in threadpool).
    span = create_span(
        "chat.stream",
        kind=SPAN_KIND_CHAIN,
        component="chat",
        operation="chat.stream",
        workspace_id=request.workspace_id,
    )
    if span is not None:
        set_input_output(span, input_value=request.query)
        if request.session_id is not None:
            span.set_attribute("session.id", request.session_id)
        if request.user_id is not None:
            span.set_attribute("user.id", request.user_id)
        if request.concept_id is not None:
            span.set_attribute("concept.id", request.concept_id)

    try:
        final_text: str | None = None
        for event in _stream_inner(
            session,
            request=request,
            settings=active_settings,
            grounding_mode=grounding_mode,
        ):
            if isinstance(event, ChatStreamFinalEvent) and event.envelope:
                final_text = event.envelope.text
            yield event
        if span is not None:
            set_input_output(span, output_value=final_text)
            from opentelemetry import trace as _trace
            span.set_status(_trace.StatusCode.OK)
    except Exception as exc:
        log.exception("stream error: %s", exc)
        if span is not None:
            from opentelemetry import trace as _trace
            span.set_status(_trace.StatusCode.ERROR, str(exc))
            span.record_exception(exc)
        yield ChatStreamErrorEvent(message=str(exc))
    finally:
        if span is not None:
            span.end()


def _stream_inner(
    session: Session,
    *,
    request: ChatRespondRequest,
    settings: Settings,
    grounding_mode: GroundingMode,
) -> Iterator[ChatStreamEvent]:
    # ── Phase: thinking ───────────────────────────────────────────────
    yield ChatStreamStatusEvent(phase=ChatPhase.THINKING)

    # ── Social fast-path ──────────────────────────────────────────────
    social_llm = build_tutor_llm_client(settings=settings)
    social_envelope = try_social_response(
        query=request.query,
        grounding_mode=grounding_mode,
        settings=settings,
        social_llm=social_llm,
    )
    if social_envelope is not None:
        yield ChatStreamStatusEvent(phase=ChatPhase.FINALIZING)
        persist_turn(
            session,
            workspace_id=request.workspace_id,
            session_id=request.session_id,
            user_id=request.user_id,
            user_text=request.query,
            assistant_payload=social_envelope.model_dump(mode="json"),
        )
        yield ChatStreamFinalEvent(envelope=social_envelope)
        return

    # ── Phase: searching ──────────────────────────────────────────────
    yield ChatStreamStatusEvent(phase=ChatPhase.SEARCHING, activity="planning_turn", step_label="Analyzing question")

    history_text = load_history_text(session, session_id=request.session_id)

    # ── Query analysis (AR1.1) ────────────────────────────────────────
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

    assessment_context = load_assessment_context(session, session_id=request.session_id)

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

    yield ChatStreamStatusEvent(phase=ChatPhase.SEARCHING, activity="checking_mastery", step_label="Checking mastery level")
    mastery_status = resolve_mastery_status(
        session=session,
        request=request,
        resolved_concept_id=resolved_concept_id,
    )

    # ── Learner profile snapshot (AR4.3) ──────────────────────────────
    from domain.learner.assembler import assemble_learner_snapshot

    learner_snapshot = assemble_learner_snapshot(
        session,
        workspace_id=request.workspace_id,
        user_id=request.user_id,
        session_id=getattr(request, "session_id", None),
    )
    learner_profile_summary = learner_snapshot.summary_text()

    # ── Background trace state (AR6.5) ────────────────────────────────
    from domain.chat.background_trace import fetch_background_trace_state

    bg_state = fetch_background_trace_state(
        session,
        workspace_id=request.workspace_id,
        user_id=request.user_id,
    )

    # ── Turn plan (AR1.2 / AR1.3) ─────────────────────────────────────
    turn_plan = build_turn_plan(
        query_analysis=query_analysis,
        mastery_status=mastery_status,
        resolved_concept_name=resolved_name,
        resolved_concept_id=resolved_concept_id,
        has_documents=True,
    )

    # ── Plan-gated retrieval via EvidencePlan (AR2.1 / AR2.2) ────────
    yield ChatStreamStatusEvent(phase=ChatPhase.SEARCHING, activity="retrieving_chunks", step_label="Searching knowledge base")
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
    if evidence_plan.expand_graph_neighbors:
        yield ChatStreamStatusEvent(phase=ChatPhase.SEARCHING, activity="expanding_graph", step_label="Finding related concepts")
    evidence_plan, ranked_chunks = execute_evidence_plan(
        session,
        plan=evidence_plan,
        settings=settings,
    )

    # ── Empty workspace fast-path ─────────────────────────────────
    if evidence_plan.stop_reason == "empty_workspace":
        yield ChatStreamStatusEvent(phase=ChatPhase.FINALIZING)
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
        empty_env = AssistantResponseEnvelope(
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
            assistant_payload=empty_env.model_dump(mode="json"),
        )
        yield ChatStreamFinalEvent(envelope=empty_env)
        return

    evidence = build_workspace_evidence(
        session=session,
        workspace_id=request.workspace_id,
        chunks=ranked_chunks,
    )
    citations = build_workspace_citations(evidence)
    tutor_llm_client = build_tutor_llm_client(settings=settings)
    quiz_context_text = build_quiz_context(
        session=session,
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
    if quiz_progress_snapshot:
        quiz_context_text = "\n\n".join(
            part for part in (quiz_context_text, quiz_progress_snapshot) if part
        )
    flashcard_progress = load_flashcard_progress(
        session,
        workspace_id=request.workspace_id,
        user_id=request.user_id,
        concept_id=resolved_concept_id,
    )

    # ── Phase: responding (deferred until first visible delta — S1) ─────

    # Build tutor text — attempt streaming if client supports it
    generation_trace: GenerationTrace | None = None
    responded = False  # S1: track whether we've emitted 'responding'
    yield ChatStreamStatusEvent(phase=ChatPhase.SEARCHING, activity="generating_reply", step_label="Generating response")
    if concept_resolution.requires_clarification:
        assistant_text = concept_resolution.clarification_prompt or ""
        # Clarification is immediate visible content
        if assistant_text:
            yield ChatStreamStatusEvent(phase=ChatPhase.RESPONDING)
            responded = True
    elif tutor_llm_client is not None and hasattr(tutor_llm_client, "generate_tutor_text_stream"):
        style = resolve_tutor_style(mastery_status=mastery_status)
        persona = get_persona("colearni")
        combined_assessment = assessment_context
        if quiz_context_text:
            combined_assessment = (
                f"{assessment_context}\n\n{quiz_context_text}"
                if assessment_context
                else quiz_context_text
            )
        prompt, prompt_meta = build_full_tutor_prompt_with_meta(
            query=request.query,
            evidence=evidence,
            persona=persona,
            style=style,
            grounding_mode=grounding_mode,
            assessment_context=combined_assessment,
            history_summary=history_text,
            document_summaries=build_document_summaries_context(
                session=session,
                workspace_id=request.workspace_id,
                chunks=ranked_chunks,
                expanded_document_ids=evidence_plan.expanded_document_ids,
            ),
            flashcard_progress=flashcard_progress,
            learner_profile_summary=learner_profile_summary,
        )
        text_stream: TutorTextStream = tutor_llm_client.generate_tutor_text_stream(
            prompt=prompt, prompt_meta=prompt_meta, operation="chat.stream",
        )
        text_parts: list[str] = []
        for delta in text_stream:
            if not responded and delta:
                yield ChatStreamStatusEvent(phase=ChatPhase.RESPONDING)
                responded = True
            text_parts.append(delta)
            yield ChatStreamDeltaEvent(text=delta)
        assistant_text = "".join(text_parts).strip()
        generation_trace = text_stream.trace
        if generation_trace is not None:
            yield ChatStreamTraceEvent(trace=generation_trace)
            # U5: emit ephemeral reasoning summary when enabled and provider
            # reported reasoning tokens — regardless of whether the app
            # explicitly requested reasoning params.
            if (
                settings.reasoning_summary_enabled
                and generation_trace.reasoning_tokens
                and generation_trace.reasoning_tokens > 0
            ):
                effort_label = generation_trace.reasoning_effort or "default"
                if generation_trace.reasoning_used:
                    summary = (
                        f"Reasoned for {generation_trace.reasoning_tokens} tokens "
                        f"at {effort_label} effort"
                    )
                else:
                    summary = (
                        f"Provider reasoning: {generation_trace.reasoning_tokens} tokens"
                    )
                yield ChatStreamReasoningSummaryEvent(summary=summary)
    else:
        # Fallback to blocking generation (no streaming support)
        from domain.chat.response_service import generate_tutor_text
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
                expanded_document_ids=evidence_plan.expanded_document_ids,
            ),
            quiz_context=quiz_context_text,
            flashcard_progress=flashcard_progress,
            learner_profile_summary=learner_profile_summary,
        )
        # S1: emit responding only after blocking generation yields content
        if assistant_text:
            yield ChatStreamStatusEvent(phase=ChatPhase.RESPONDING)
            responded = True

    if not assistant_text:
        assistant_text = "(no response generated)"

    # ── Structured answer parts (U6) ─────────────────────────────────
    answer_parts = split_answer_parts(assistant_text)
    yield ChatStreamAnswerPartEvent(parts=answer_parts)

    # ── Verify + finalize ─────────────────────────────────────────────
    yield ChatStreamStatusEvent(phase=ChatPhase.FINALIZING, activity="verifying_citations", step_label="Verifying citations")
    draft = AssistantDraft(text=assistant_text, evidence=evidence, citations=citations)
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

    # ── Plan-driven quiz actions ──────────────────────────────────────
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

    # ── Enrich trace with planner metadata ──────────────────────────
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
        "evidence_plan_provenance_chunks": evidence_plan.provenance_chunks_added,
        "evidence_plan_doc_summary_ids": len(evidence_plan.expanded_document_ids),
        "learner_weak_topic_count": len(learner_snapshot.weak_topics),
        "learner_strong_topic_count": len(learner_snapshot.strong_topics),
        "learner_frontier_count": len(learner_snapshot.current_frontier),
        "learner_review_count": len(learner_snapshot.review_queue),
        "learner_profile_summary": learner_profile_summary or None,
        "bg_digest_available": bg_state.digest_available,
        "bg_frontier_suggestion_count": bg_state.frontier_suggestion_count,
        "bg_research_candidate_pending": bg_state.research_candidate_pending,
        "bg_research_candidate_approved": bg_state.research_candidate_approved,
    })

    envelope = envelope.model_copy(
        update={
            "actions": actions,
            "response_mode": envelope.response_mode,
            "generation_trace": generation_trace,
            "answer_parts": answer_parts,
        }
    )

    # ── Phase: finalizing ─────────────────────────────────────────────
    yield ChatStreamStatusEvent(phase=ChatPhase.FINALIZING)

    persist_turn(
        session,
        workspace_id=request.workspace_id,
        session_id=request.session_id,
        user_id=request.user_id,
        user_text=request.query,
        assistant_payload=envelope.model_dump(mode="json"),
        concept_name=resolved_name,
    )

    yield ChatStreamFinalEvent(envelope=envelope)
