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
    set_span_kind,
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
    ChatStreamDeltaEvent,
    ChatStreamErrorEvent,
    ChatStreamEvent,
    ChatStreamFinalEvent,
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
from domain.chat.response_service import (
    build_quiz_context,
    build_tutor_llm_client,
    resolve_mastery_status,
)
from domain.chat.retrieval_context import (
    apply_concept_bias,
    retrieve_ranked_chunks,
    workspace_has_no_chunks,
)
from domain.chat.session_memory import (
    load_assessment_context,
    load_flashcard_progress,
    load_history_text,
    persist_turn,
)
from domain.chat.social_turns import try_social_response
from domain.chat.prompt_kit import build_full_tutor_prompt, get_persona
from domain.chat.tutor_agent import resolve_tutor_style
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
        component="chat",
        operation="chat.stream",
        workspace_id=request.workspace_id,
    )
    if span is not None:
        set_span_kind(span, SPAN_KIND_CHAIN)
        set_input_output(span, input_value=request.query)
        if request.session_id is not None:
            span.set_attribute("session.id", request.session_id)
        if request.user_id is not None:
            span.set_attribute("user.id", request.user_id)

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
    yield ChatStreamStatusEvent(phase=ChatPhase.SEARCHING)

    history_text = load_history_text(session, session_id=request.session_id)
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

    ranked_chunks = retrieve_ranked_chunks(
        session,
        workspace_id=request.workspace_id,
        query=request.query,
        top_k=request.top_k,
        settings=settings,
    )

    # ── Empty workspace fast-path ─────────────────────────────────────
    if not ranked_chunks and workspace_has_no_chunks(session, request.workspace_id):
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

    if concept_resolution.resolved_concept is not None:
        ranked_chunks = apply_concept_bias(
            session,
            workspace_id=request.workspace_id,
            concept_id=concept_resolution.resolved_concept.concept_id,
            chunks=ranked_chunks,
        )

    evidence = build_workspace_evidence(
        session=session,
        workspace_id=request.workspace_id,
        chunks=ranked_chunks,
    )
    citations = build_workspace_citations(evidence)
    tutor_llm_client = build_tutor_llm_client(settings=settings)
    mastery_status = resolve_mastery_status(
        session=session,
        request=request,
        resolved_concept_id=(
            concept_resolution.resolved_concept.concept_id
            if concept_resolution.resolved_concept is not None
            else None
        ),
    )

    # ── Phase: responding (deferred until first visible delta — S1) ─────

    resolved_concept_id = (
        concept_resolution.resolved_concept.concept_id
        if concept_resolution.resolved_concept is not None
        else None
    )

    # Build tutor text — attempt streaming if client supports it
    generation_trace: GenerationTrace | None = None
    responded = False  # S1: track whether we've emitted 'responding'
    if concept_resolution.requires_clarification:
        assistant_text = concept_resolution.clarification_prompt or ""
        # Clarification is immediate visible content
        if assistant_text:
            yield ChatStreamStatusEvent(phase=ChatPhase.RESPONDING)
            responded = True
    elif tutor_llm_client is not None and hasattr(tutor_llm_client, "generate_tutor_text_stream"):
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
        style = resolve_tutor_style(mastery_status=mastery_status)
        persona = get_persona("colearni")
        combined_assessment = assessment_context
        if quiz_context_text:
            combined_assessment = (
                f"{assessment_context}\n\n{quiz_context_text}"
                if assessment_context
                else quiz_context_text
            )
        prompt = build_full_tutor_prompt(
            query=request.query,
            evidence=evidence,
            persona=persona,
            style=style,
            assessment_context=combined_assessment,
            history_summary=history_text,
            document_summaries=build_document_summaries_context(
                session=session,
                workspace_id=request.workspace_id,
                chunks=ranked_chunks,
            ),
            flashcard_progress=flashcard_progress,
        )
        text_stream: TutorTextStream = tutor_llm_client.generate_tutor_text_stream(prompt=prompt)
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
    else:
        # Fallback to blocking generation (no streaming support)
        from domain.chat.response_service import generate_tutor_text

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
        assistant_text, generation_trace = generate_tutor_text(
            query=request.query,
            evidence=evidence,
            mastery_status=mastery_status,
            llm_client=tutor_llm_client,
            history_text=history_text,
            assessment_context=assessment_context,
            document_summaries=build_document_summaries_context(
                session=session,
                workspace_id=request.workspace_id,
                chunks=ranked_chunks,
            ),
            quiz_context=quiz_context_text,
            flashcard_progress=flashcard_progress,
        )
        # S1: emit responding only after blocking generation yields content
        if assistant_text:
            yield ChatStreamStatusEvent(phase=ChatPhase.RESPONDING)
            responded = True

    if not assistant_text:
        assistant_text = "(no response generated)"

    # ── Verify + finalize ─────────────────────────────────────────────
    draft = AssistantDraft(text=assistant_text, evidence=evidence, citations=citations)
    envelope = verify_assistant_draft(draft=draft, grounding_mode=grounding_mode)
    envelope = filter_used_citations(envelope)

    meta = ConversationMeta(
        session_id=request.session_id,
        resolved_concept_id=resolved_concept_id,
        resolved_concept_name=(
            concept_resolution.resolved_concept.canonical_name
            if concept_resolution.resolved_concept is not None
            else None
        ),
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

    envelope = envelope.model_copy(
        update={
            "actions": actions,
            "response_mode": "grounded",
            "generation_trace": generation_trace,
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
        concept_name=(
            concept_resolution.resolved_concept.canonical_name
            if concept_resolution.resolved_concept is not None
            else None
        ),
    )

    yield ChatStreamFinalEvent(envelope=envelope)
