"""Tutor text generation, mastery resolution, quiz context, LLM client factory."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from adapters.db.mastery import get_mastery_status
from adapters.llm.factory import build_query_analyzer_llm_client as _build_qa_client
from adapters.llm.factory import build_tutor_llm_client as _build_tutor_client
from core.contracts import GraphLLMClient
from core.schemas import ChatRespondRequest, EvidenceItem, GroundingMode
from core.schemas.assistant import GenerationTrace
from core.settings import Settings
from domain.chat.prompt_kit import build_tutor_messages, get_persona
from domain.chat.tutor_agent import build_tutor_response_text, resolve_tutor_style
from domain.learning.quiz_persistence import get_latest_quiz_summary_for_concept

log = logging.getLogger("domain.chat.response_service")


def generate_tutor_text(
    *,
    query: str,
    evidence: list[EvidenceItem],
    mastery_status: str | None,
    grounding_mode: GroundingMode,
    llm_client: GraphLLMClient | None,
    history_text: str,
    assessment_context: str,
    document_summaries: str = "",
    graph_context: str = "",
    quiz_context: str = "",
    flashcard_progress: str = "",
    learner_profile_summary: str = "",
) -> tuple[str, GenerationTrace | None]:
    """Build a rich tutor prompt via prompt_kit and call the LLM.

    Returns (text, trace) where trace is non-None when an LLM call succeeds.
    """
    style = resolve_tutor_style(mastery_status=mastery_status)
    persona = get_persona("colearni")
    combined_assessment = assessment_context
    if quiz_context:
        combined_assessment = f"{assessment_context}\n\n{quiz_context}" if assessment_context else quiz_context
    builder, prompt_meta = build_tutor_messages(
        query=query,
        evidence=evidence,
        persona=persona,
        style=style,
        grounding_mode=grounding_mode,
        assessment_context=combined_assessment,
        history_summary=history_text,
        document_summaries=document_summaries,
        graph_context=graph_context,
        flashcard_progress=flashcard_progress,
        learner_profile_summary=learner_profile_summary,
    )
    msgs = builder.messages
    system_len = sum(len(m["content"]) for m in msgs if m["role"] == "system")
    user_len = sum(len(m["content"]) for m in msgs if m["role"] == "user")
    log.debug(
        "tutor prompt assembled: system=%d user=%d chars, history=%d, assessment=%d, docs=%d, flashcards=%d",
        system_len,
        user_len,
        len(history_text),
        len(combined_assessment),
        len(document_summaries),
        len(flashcard_progress),
    )
    if llm_client is not None:
        # Prefer messages[]-native path; fall back to legacy API.
        complete_fn = getattr(llm_client, "complete_messages", None)
        if callable(complete_fn):
            try:
                text, trace = complete_fn(
                    builder.build(), prompt_meta=prompt_meta,
                )
                text = text.strip()
            except (RuntimeError, ValueError):
                text, trace = "", None
            if text:
                return text, trace
        else:
            traced_fn = getattr(llm_client, "generate_tutor_text_traced", None)
            flat = builder.messages
            sys_text = "\n\n".join(m["content"] for m in flat if m["role"] == "system")
            usr_text = "\n\n".join(m["content"] for m in flat if m["role"] == "user")
            if callable(traced_fn):
                try:
                    text, trace = traced_fn(
                        prompt=usr_text, prompt_meta=prompt_meta,
                        system_prompt=sys_text,
                    )
                    text = text.strip()
                except (RuntimeError, ValueError):
                    text, trace = "", None
                if text:
                    return text, trace
            else:
                try:
                    text = llm_client.generate_tutor_text(
                        prompt=usr_text, prompt_meta=prompt_meta,
                        system_prompt=sys_text,
                    ).strip()
                except (RuntimeError, ValueError):
                    text = ""
                if text:
                    return text, None
    fallback = build_tutor_response_text(
        query=query,
        evidence=evidence,
        mastery_status=mastery_status,
        grounding_mode=grounding_mode,
        llm_client=None,
    )
    return fallback, None


def resolve_mastery_status(
    *,
    session: Session,
    request: ChatRespondRequest,
    resolved_concept_id: int | None,
) -> str | None:
    """Look up mastery status for the user's active concept."""
    if request.user_id is None:
        return None
    concept_id = resolved_concept_id or request.concept_id
    if concept_id is None:
        return None
    return get_mastery_status(
        session,
        workspace_id=request.workspace_id,
        user_id=request.user_id,
        concept_id=concept_id,
    )


def build_tutor_llm_client(*, settings: Settings) -> GraphLLMClient | None:
    """Build the tutor LLM client, returning None if unavailable."""
    try:
        return _build_tutor_client(settings=settings)
    except ValueError:
        return None


def build_query_analyzer_client(*, settings: Settings) -> GraphLLMClient | None:
    """Build the query analyzer LLM client, returning None if unavailable."""
    try:
        return _build_qa_client(settings=settings)
    except ValueError:
        return None


def build_quiz_context(
    *,
    session: Session,
    workspace_id: int,
    user_id: int | None,
    concept_id: int | None,
) -> str:
    """Build a short quiz status context string for the tutor prompt."""
    if user_id is None or concept_id is None:
        return ""
    try:
        summary = get_latest_quiz_summary_for_concept(
            session,
            workspace_id=workspace_id,
            user_id=user_id,
            concept_id=concept_id,
        )
    except Exception:
        if callable(getattr(session, "rollback", None)):
            session.rollback()
        return ""
    if summary is None or not summary.get("attempted"):
        return ""
    score = summary.get("score")
    passed = summary.get("passed")
    feedback = summary.get("overall_feedback", "")
    parts = [f"LATEST QUIZ FOR ACTIVE CONCEPT (quiz_id={summary['quiz_id']}):"]
    if score is not None:
        parts.append(f"- Score: {score:.0%}")
    if passed is not None:
        parts.append(f"- Result: {'PASSED' if passed else 'NOT YET PASSED'}")
    if feedback:
        parts.append(f"- Feedback: {feedback}")
    return "\n".join(parts)
