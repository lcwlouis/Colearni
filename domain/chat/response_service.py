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
from core.settings import Settings, get_settings
from domain.chat.prompt_kit import build_tutor_messages, get_persona
from domain.chat.tutor_agent import build_tutor_response_text, resolve_tutor_style
from domain.learning.quiz_persistence import get_latest_quiz_summary_for_concept

log = logging.getLogger("domain.chat.response_service")


def _try_tool_augmented(
    *,
    llm_client: GraphLLMClient | None,
    messages: list,
    session: Session | None,
    workspace_id: int | None,
    user_id: int | None,
) -> tuple[str, GenerationTrace | None] | None:
    """Attempt tool-augmented generation; return None to fall through.

    Only activates when ``enable_tool_calling`` is ``True``, the LLM client
    is available, and at least one tool is registered.
    """
    settings = get_settings()
    if not settings.enable_tool_calling or llm_client is None:
        return None

    try:
        from domain.chat.tool_augmented import generate_with_tools  # noqa: PLC0415
        from domain.tools.registry_factory import build_tool_registry  # noqa: PLC0415

        registry = build_tool_registry(
            session=session,
            workspace_id=workspace_id or 0,
            user_id=user_id or 0,
            web_search_api_key=settings.web_search_api_key,
            web_search_max_results=settings.web_search_max_results,
        )
        if not registry.list_tools():
            return None

        result = generate_with_tools(
            messages=messages,
            llm_client=llm_client,
            tool_registry=registry,
            max_iterations=settings.agent_max_iterations,
        )
        if not result.text:
            log.warning("Tool-augmented generation returned empty text, falling back")
            return None

        trace = GenerationTrace(
            prompt_tokens=result.total_prompt_tokens or None,
            completion_tokens=result.total_completion_tokens or None,
            total_tokens=(
                (result.total_prompt_tokens + result.total_completion_tokens)
                if result.total_prompt_tokens and result.total_completion_tokens
                else None
            ),
        )
        return result.text, trace
    except Exception:
        log.warning("Tool-augmented generation failed, falling back", exc_info=True)
        return None


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
    session: Session | None = None,
    workspace_id: int | None = None,
    user_id: int | None = None,
) -> tuple[str, GenerationTrace | None]:
    """Build a rich tutor prompt via prompt_kit and call the LLM.

    Returns (text, trace) where trace is non-None when an LLM call succeeds.

    When ``settings.enable_tool_calling`` is ``True`` and the required context
    (session, workspace_id, user_id) is available, routes through the
    tool-augmented generation path using :class:`~core.agent_loop.AgentLoop`.
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

    # ── Optional tool-augmented path ──────────────────────────────────
    tool_result = _try_tool_augmented(
        llm_client=llm_client,
        messages=builder.build(),
        session=session,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    if tool_result is not None:
        return tool_result

    if llm_client is not None:
        try:
            text, trace = llm_client.complete_messages(
                builder.build(), prompt_meta=prompt_meta,
            )
            text = text.strip()
        except (RuntimeError, ValueError):
            text, trace = "", None
        if text:
            return text, trace
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
