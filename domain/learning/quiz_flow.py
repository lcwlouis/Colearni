"""Shared quiz creation and submission orchestration.

Provides generic create/submit quiz flows used by both level-up
and practice quiz types.  Level-up-specific and practice-specific
behaviour is handled by their respective modules which wrap these
shared functions.

DB reads and writes are delegated to :mod:`domain.learning.quiz_persistence`.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from opentelemetry import trace

from core.contracts import GraphLLMClient
from core.observability import (
    SPAN_KIND_CHAIN,
    emit_event,
    observation_context,
    set_input_output,
    set_span_summary,
    start_span,
)
from core.prompting import PromptRegistry
from sqlalchemy.orm import Session

from domain.chat.session_memory import load_chat_context_for_quiz
from domain.learning.quiz_generation import (
    QuizValidationError as _QVE,
)
from domain.learning.quiz_generation import (
    attach_generation_context as _attach_generation_context,
)
from domain.learning.quiz_generation import (
    auto_items as _auto_items,
)
from domain.learning.quiz_generation import (
    ensure_diversity as _ensure_diversity,
)
from domain.learning.quiz_generation import (
    normalize_items as _normalize_items,
)
from domain.learning.quiz_generation import (
    normalize_mcq_payload as _normalize_mcq,
)
from domain.learning.quiz_generation import (
    normalize_short_payload as _normalize_short,
)
from domain.learning.quiz_generation import (
    parse_json as _parse_json,
)
from domain.learning.quiz_generation import (
    safe_mcq_choices as _safe_mcq_choices,
)
from domain.learning.quiz_generation import (
    validate_question_count as _validate_question_count,
)
from domain.learning.quiz_grading import (
    QuizGradingError as _QGE,
)
from domain.learning.quiz_grading import (
    build_overall_feedback as _build_overall_feedback,
)
from domain.learning.quiz_grading import (
    compose_feedback_items as _compose_feedback_items,
)
from domain.learning.quiz_grading import (
    grade_mcq_items as _grade_mcq_items,
)
from domain.learning.quiz_grading import (
    grade_short_items_without_llm as _grade_short_items_without_llm,
)
from domain.learning.quiz_grading import (
    grading_messages as _grading_messages,
)
from domain.learning.quiz_grading import (
    grading_prompt as _grading_prompt,
)
from domain.learning.quiz_grading import (
    parse_grading as _parse_grading,
)
from domain.learning.quiz_grading import (
    validate_answers as _validate_answers,
)
from domain.learning.quiz_persistence import (
    check_session_scope as _check_session_scope,
)
from domain.learning.quiz_persistence import (
    insert_attempt as _insert_attempt,
)
from domain.learning.quiz_persistence import (
    insert_quiz_items as _insert_quiz_items,
)
from domain.learning.quiz_persistence import (
    insert_quiz_row as _insert_quiz_row,
)
from domain.learning.quiz_persistence import (
    load_existing_graded_attempt as _load_existing_graded_attempt,
)
from domain.learning.quiz_persistence import (
    load_generation_context as _load_generation_context,
)
from domain.learning.quiz_persistence import (
    load_quiz_for_grading as _load_quiz_for_grading,
)
from domain.learning.quiz_persistence import (
    load_quiz_items as _load_quiz_items,
)
from domain.learning.quiz_persistence import (
    lookup_active_concept as _lookup_active_concept,
)
from domain.learning.quiz_persistence import (
    lookup_mastery as _lookup_mastery,
)
from domain.learning.quiz_persistence import (
    mark_quiz_graded as _mark_quiz_graded,
)
from domain.learning.quiz_persistence import (
    upsert_mastery as _upsert_mastery,
)
from domain.learning.quiz_persistence import (
    get_child_concept_ids as _get_child_concept_ids,
)
from domain.learning.quiz_persistence import (
    lookup_concept_tier as _lookup_concept_tier,
)

MIN_ITEMS = 5
MAX_ITEMS = 12
PASS_SCORE = 0.75
RETRY_HINT = "create a new level-up quiz to retry"
MAX_GENERATION_ATTEMPTS = 3
_CASCADABLE_TIERS = frozenset({"umbrella", "topic", "subtopic"})

log = logging.getLogger("domain.learning.quiz_flow")
_registry = PromptRegistry()


class QuizNotFoundError(ValueError):
    pass


class QuizValidationError(ValueError):
    pass


class QuizGradingError(ValueError):
    pass


class QuizUnavailableError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Create quiz
# ---------------------------------------------------------------------------

def create_quiz(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    concept_id: int,
    session_id: int | None,
    question_count: int | None,
    items: list[dict[str, Any]] | None,
    llm_client: GraphLLMClient | None = None,
    quiz_type: str = "level_up",
    min_items: int = MIN_ITEMS,
    max_items: int = MAX_ITEMS,
    context_source: str | None = None,
) -> dict[str, Any]:
    if session_id is not None:
        if not _check_session_scope(
            session,
            workspace_id=workspace_id,
            user_id=user_id,
            session_id=session_id,
        ):
            raise QuizValidationError("session_id is not valid for workspace/user scope.")

    concept = _lookup_active_concept(
        session, workspace_id=workspace_id, concept_id=concept_id
    )
    if concept is None:
        raise QuizNotFoundError("Concept not found in workspace.")
    concept_name = str(concept["canonical_name"])
    concept_description = str(concept["description"] or "")
    resolved_context_source = context_source or ("provided" if items else "generated")

    normalized_items = _choose_items(
        session,
        workspace_id=workspace_id,
        concept_id=concept_id,
        concept=concept,
        question_count=question_count,
        items=items,
        llm_client=llm_client,
        min_items=min_items,
        max_items=max_items,
        session_id=session_id,
    )
    normalized_items = _attach_generation_context(
        normalized_items,
        concept_name=concept_name,
        concept_description=concept_description,
        context_source=resolved_context_source,
    )

    quiz = _insert_quiz_row(
        session,
        workspace_id=workspace_id,
        user_id=user_id,
        session_id=session_id,
        concept_id=concept_id,
        quiz_type=quiz_type,
    )
    quiz_id = int(quiz["id"])

    _insert_quiz_items(session, quiz_id=quiz_id, items=normalized_items)
    session.commit()

    rows = _load_quiz_items(session, quiz_id=quiz_id)
    return {
        "quiz_id": quiz_id,
        "workspace_id": workspace_id,
        "user_id": user_id,
        "concept_id": concept_id,
        "status": str(quiz["status"]),
        "items": [
            {
                "item_id": int(row["item_id"]),
                "position": int(row["position"]),
                "item_type": str(row["item_type"]),
                "prompt": str(row["prompt"]),
                "choices": _safe_mcq_choices(row["payload"]),
            }
            for row in rows
        ],
    }


# ---------------------------------------------------------------------------
# Submit quiz
# ---------------------------------------------------------------------------

def submit_quiz(
    session: Session,
    *,
    quiz_id: int,
    workspace_id: int,
    user_id: int,
    answers: list[dict[str, Any]],
    llm_client: GraphLLMClient | None,
    quiz_type: str = "level_up",
    load_quiz_type: str | None = ...,  # sentinel: use quiz_type by default
    update_mastery: bool = True,
    retry_hint: str = RETRY_HINT,
    run_id: str | None = None,
) -> dict[str, Any]:
    resolved_run_id = run_id or str(uuid4())
    event_prefix = "grading.level_up" if quiz_type == "level_up" else "grading.practice"
    operation = f"{event_prefix}.submit"
    stage = "load_quiz"
    # When load_quiz_type is not explicitly set, default to quiz_type.
    # Pass None to skip the quiz_type filter (e.g. practice retries of level-up quizzes).
    effective_load_type = quiz_type if load_quiz_type is ... else load_quiz_type

    with observation_context(
        component="grading",
        operation=operation,
        workspace_id=workspace_id,
        quiz_id=quiz_id,
        run_id=resolved_run_id,
    ), start_span(
        event_prefix,
        kind=SPAN_KIND_CHAIN,
        component="grading",
        operation=operation,
        workspace_id=workspace_id,
        quiz_id=quiz_id,
        run_id=resolved_run_id,
    ) as span:
        set_span_summary(span, input_summary=f"quiz={quiz_id}, answers={len(answers)}")
        try:
            quiz = _load_quiz_for_grading(
                session,
                quiz_id=quiz_id,
                workspace_id=workspace_id,
                quiz_type=effective_load_type,
            )
            if quiz is None:
                raise QuizNotFoundError("Quiz not found in workspace.")
            if int(quiz["user_id"]) != user_id:
                raise QuizValidationError("Quiz does not belong to user.")

            stage = "load_items"
            item_rows = _load_quiz_items(session, quiz_id=quiz_id)
            item_refs = [
                {
                    "item_id": int(row["item_id"]),
                    "item_type": str(row["item_type"]),
                }
                for row in item_rows
            ]
            short_item_count = sum(
                1 for row in item_rows if str(row["item_type"]) == "short_answer"
            )
            mcq_item_count = sum(1 for row in item_rows if str(row["item_type"]) == "mcq")
            emit_event(
                f"{event_prefix}.start",
                status="info",
                component="grading",
                operation=operation,
                workspace_id=workspace_id,
                quiz_id=quiz_id,
                short_item_count=short_item_count,
                mcq_item_count=mcq_item_count,
            )

            stage = "check_replay"
            existing = _load_existing_graded_attempt(
                session, quiz_id=quiz_id, user_id=user_id
            )
            if existing is not None and quiz_type != "practice":
                grading = existing["grading"] if isinstance(existing["grading"], dict) else {}
                feedback_items = _compose_feedback_items(
                    item_refs=item_refs,
                    graded_items=grading.get("items"),
                )
                session.commit()
                payload: dict[str, Any] = {
                    "quiz_id": quiz_id,
                    "attempt_id": int(existing["id"]),
                    "score": float(existing["score"] or 0.0),
                    "passed": bool(existing["passed"]),
                    "critical_misconception": bool(grading.get("critical_misconception", False)),
                    "overall_feedback": str(grading.get("overall_feedback", "")).strip(),
                    "items": feedback_items,
                    "replayed": True,
                    "retry_hint": retry_hint,
                }
                if update_mastery:
                    mastery = _lookup_mastery(
                        session,
                        workspace_id=workspace_id,
                        user_id=user_id,
                        concept_id=int(quiz["concept_id"]),
                    )
                    payload["mastery_status"] = (
                        str(mastery["status"])
                        if mastery
                        else ("learned" if existing["passed"] else "learning")
                    )
                    payload["mastery_score"] = (
                        float(mastery["score"]) if mastery else float(existing["score"] or 0.0)
                    )
                emit_event(
                    f"{event_prefix}.result",
                    status="success",
                    component="grading",
                    operation=operation,
                    workspace_id=workspace_id,
                    quiz_id=quiz_id,
                    attempt_id=int(existing["id"]),
                    score=payload["score"],
                    passed=payload["passed"],
                    critical_misconception=payload["critical_misconception"],
                    replayed=True,
                )
                return payload

            if not item_rows:
                raise QuizValidationError("Quiz has no items to submit.")

            stage = "normalize_items"
            items: list[dict[str, Any]] = []
            for row in item_rows:
                payload = row["payload"] if isinstance(row["payload"], dict) else {}
                item_type = str(row["item_type"])
                payload = (
                    _normalize_short(payload)
                    if item_type == "short_answer"
                    else _normalize_mcq(payload)
                )
                items.append(
                    {
                        "item_id": int(row["item_id"]),
                        "item_type": item_type,
                        "prompt": str(row["prompt"]),
                        "payload": payload,
                    }
                )

            stage = "validate_answers"
            answer_map = _validate_answers(items, answers)
            short_items = [item for item in items if item["item_type"] == "short_answer"]
            mcq_items = [item for item in items if item["item_type"] == "mcq"]
            graded_by_id: dict[int, dict[str, Any]] = {}
            short_overall_feedback = ""

            if short_items:
                stage = "grade_short_answer"
                if llm_client is None:
                    short_grading = _grade_short_items_without_llm(short_items, answer_map)
                else:
                    short_ids = [item["item_id"] for item in short_items]
                    if callable(getattr(llm_client, "complete_messages", None)):
                        messages = _grading_messages(short_items, answer_map)
                        llm_text, _ = llm_client.complete_messages(messages)
                    else:
                        short_prompt = _grading_prompt(short_items, answer_map)
                        llm_text = llm_client.generate_tutor_text(prompt=short_prompt)
                    short_grading = _parse_grading(llm_text, short_ids)
                short_overall_feedback = short_grading["overall_feedback"]
                for graded_item in short_grading["items"]:
                    graded_by_id[int(graded_item["item_id"])] = graded_item

            stage = "grade_mcq"
            mcq_graded = _grade_mcq_items(mcq_items, answer_map)
            for graded_item in mcq_graded:
                graded_by_id[int(graded_item["item_id"])] = graded_item

            ordered_items = [graded_by_id[item["item_id"]] for item in items]
            feedback_items = _compose_feedback_items(
                item_refs=[
                    {"item_id": item["item_id"], "item_type": item["item_type"]} for item in items
                ],
                graded_items=ordered_items,
            )
            score = sum(float(item["score"]) for item in ordered_items) / len(ordered_items)
            critical = any(bool(item["critical_misconception"]) for item in ordered_items)
            passed = score >= PASS_SCORE and not critical
            mastery_status = "learned" if passed else "learning"
            mastery_score = max(0.0, min(1.0, float(score)))
            overall_feedback = _build_overall_feedback(
                short_overall_feedback=short_overall_feedback,
                mcq_graded=mcq_graded,
                passed=passed,
                critical=critical,
            )
            grading_payload = {
                "items": feedback_items,
                "overall_feedback": overall_feedback,
                "critical_misconception": critical,
            }

            stage = "persist_attempt"
            attempt_id = _insert_attempt(
                session,
                quiz_id=quiz_id,
                user_id=user_id,
                answers=answers,
                grading_payload=grading_payload,
                score=mastery_score,
                passed=passed,
            )
            _mark_quiz_graded(session, quiz_id=quiz_id)
            if update_mastery:
                stage = "update_mastery"
                _upsert_mastery(
                    session,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    concept_id=int(quiz["concept_id"]),
                    score=mastery_score,
                    status=mastery_status,
                )
                if passed:
                    stage = "cascade_mastery"
                    cascaded = cascade_mastery_to_children(
                        session,
                        workspace_id=workspace_id,
                        user_id=user_id,
                        concept_id=int(quiz["concept_id"]),
                        score=mastery_score,
                    )
            stage = "commit"
            session.commit()

            payload = {
                "quiz_id": quiz_id,
                "attempt_id": attempt_id,
                "score": mastery_score,
                "passed": passed,
                "critical_misconception": critical,
                "overall_feedback": overall_feedback,
                "items": feedback_items,
                "replayed": False,
                "retry_hint": None,
            }
            if update_mastery:
                payload["mastery_status"] = mastery_status
                payload["mastery_score"] = mastery_score
                if passed:
                    payload["cascaded_to"] = cascaded
            set_input_output(
                span,
                output_value=json.dumps(
                    {"score": mastery_score, "passed": passed, "critical": critical},
                ),
                output_mime_type="application/json",
            )
            emit_event(
                f"{event_prefix}.result",
                status="success",
                component="grading",
                operation=operation,
                workspace_id=workspace_id,
                quiz_id=quiz_id,
                attempt_id=attempt_id,
                score=mastery_score,
                passed=passed,
                critical_misconception=critical,
                replayed=False,
            )
            return payload
        except Exception as exc:
            emit_event(
                f"{event_prefix}.failure",
                status="failure",
                component="grading",
                operation=operation,
                workspace_id=workspace_id,
                quiz_id=quiz_id,
                stage=stage,
                error_type=type(exc).__name__,
            )
            if span is not None:
                span.set_status(trace.StatusCode.ERROR, str(exc))
                span.record_exception(exc)
            if isinstance(exc, _QVE) and not isinstance(exc, QuizValidationError):
                raise QuizValidationError(str(exc)) from exc
            if isinstance(exc, _QGE) and not isinstance(exc, QuizGradingError):
                raise QuizGradingError(str(exc)) from exc
            raise


# ---------------------------------------------------------------------------
# Mastery cascade
# ---------------------------------------------------------------------------

def cascade_mastery_to_children(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    concept_id: int,
    score: float,
) -> list[int]:
    """Cascade ``learned`` mastery to direct child concepts.

    Only cascades downward when the concept tier is umbrella, topic, or
    subtopic.  Children already marked ``learned`` are left unchanged.
    Returns the list of child concept IDs whose mastery was cascaded.
    """
    tier = _lookup_concept_tier(
        session, workspace_id=workspace_id, concept_id=concept_id,
    )
    if tier not in _CASCADABLE_TIERS:
        return []

    child_ids = _get_child_concept_ids(
        session, workspace_id=workspace_id, concept_id=concept_id,
    )
    cascaded: list[int] = []
    for child_id in child_ids:
        existing = _lookup_mastery(
            session, workspace_id=workspace_id, user_id=user_id, concept_id=child_id,
        )
        if existing and str(existing["status"]) == "learned":
            continue
        _upsert_mastery(
            session,
            workspace_id=workspace_id,
            user_id=user_id,
            concept_id=child_id,
            score=score,
            status="learned",
        )
        cascaded.append(child_id)

    if cascaded:
        log.info(
            "mastery cascade: concept=%d tier=%s → %d children cascaded %s",
            concept_id, tier, len(cascaded), cascaded,
        )
    return cascaded


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _choose_items(
    session: Session,
    *,
    workspace_id: int,
    concept_id: int,
    concept: dict[str, Any],
    question_count: int | None,
    items: list[dict[str, Any]] | None,
    llm_client: GraphLLMClient | None,
    min_items: int,
    max_items: int,
    session_id: int | None = None,
) -> list[dict[str, Any]]:
    if items:
        return _normalize_items(items, min_items=min_items, max_items=max_items)

    target = _validate_question_count(
        question_count=question_count,
        min_items=min_items,
        max_items=max_items,
    )
    if llm_client is not None and _supports_quiz_generation(llm_client):
        generated = _generate_items_with_retries(
            session,
            workspace_id=workspace_id,
            concept_id=concept_id,
            llm_client=llm_client,
            target_count=target,
            min_items=min_items,
            max_items=max_items,
            session_id=session_id,
        )
        if generated:
            return generated

    return _auto_items(concept, target, min_items=min_items, max_items=max_items)


def _supports_quiz_generation(llm_client: GraphLLMClient) -> bool:
    """Check if the LLM client supports both graph extraction and text generation."""
    return (
        callable(getattr(llm_client, "extract_raw_graph", None))
        and callable(getattr(llm_client, "generate_tutor_text", None))
    )


def _generate_items_with_retries(
    session: Session,
    *,
    workspace_id: int,
    concept_id: int,
    llm_client: GraphLLMClient,
    target_count: int,
    min_items: int,
    max_items: int,
    session_id: int | None = None,
) -> list[dict[str, Any]] | None:
    context = _load_generation_context(
        session, workspace_id=workspace_id, concept_id=concept_id
    )
    if context is None:
        raise QuizNotFoundError("Concept not found in workspace.")
    concept_name = context["concept_name"]
    concept_desc = context.get("concept_description", "")
    adjacent = context.get("adjacent_concepts", [])
    adjacent_str = ", ".join(adjacent[:6]) if adjacent else "none"
    chunk_excerpts = context.get("chunk_excerpts", [])
    chunks_block = ""
    if chunk_excerpts:
        chunks_block = "\nSOURCE MATERIAL EXCERPTS:\n" + "\n".join(
            f"- {excerpt}" for excerpt in chunk_excerpts
        ) + "\n"
    chat_history = load_chat_context_for_quiz(
        session, session_id=session_id, max_turns=8
    )
    chat_block = ""
    if chat_history:
        chat_block = (
            "\nCHAT HISTORY CONTEXT (use to target areas the learner discussed, "
            "struggled with, or showed curiosity about):\n"
            f"{chat_history}\n"
        )
    prompt, prompt_meta, system_prompt = _build_quiz_generation_prompt(
        concept_name=concept_name,
        concept_desc=concept_desc,
        adjacent_str=adjacent_str,
        chunks_block=chunks_block,
        chat_block=chat_block,
        target_count=target_count,
    )
    retry_prompt = prompt
    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        try:
            llm_response = llm_client.generate_tutor_text(
                prompt=retry_prompt, prompt_meta=prompt_meta,
                system_prompt=system_prompt,
            )
        except Exception:
            return None
        try:
            payload = _parse_json(
                llm_response,
                "Quiz generation response is not valid JSON.",
            )
            raw_items = payload.get("items")
            if not isinstance(raw_items, list):
                raise QuizValidationError("Quiz generation response must include items.")
            normalized = _normalize_items(raw_items, min_items=min_items, max_items=max_items)
            _ensure_diversity(normalized)
            if len(normalized) != target_count:
                raise QuizValidationError(
                    f"Generated quiz must have exactly {target_count} items."
                )
            return normalized
        except (QuizValidationError, _QVE) as exc:
            if attempt == MAX_GENERATION_ATTEMPTS:
                return None
            retry_prompt = (
                f"{prompt}\n"
                f"RETRY_ATTEMPT: {attempt + 1}/{MAX_GENERATION_ATTEMPTS}\n"
                f"PREVIOUS_OUTPUT_INVALID_REASON: {exc}\n"
                "Regenerate from scratch with fully valid JSON."
            )
    return None


def _build_quiz_generation_prompt(
    *,
    concept_name: str,
    concept_desc: str,
    adjacent_str: str,
    chunks_block: str,
    chat_block: str,
    target_count: int,
) -> tuple[str, Any, str | None]:
    """Build the quiz generation prompt from the asset or inline fallback."""
    try:
        system_prompt = _registry.render("assessment_levelup_generate_v1_system", {})
    except Exception:
        system_prompt = None

    try:
        prompt, meta = _registry.render_with_meta("assessment_levelup_generate_v1", {
            "target_count": str(target_count),
            "concept_name": concept_name,
            "concept_description": concept_desc,
            "adjacent_concepts": adjacent_str,
            "chunk_excerpts": chunks_block or "(none)",
            "chat_history": chat_block or "(none)",
        })
        return prompt, meta, system_prompt
    except Exception:
        log.debug("asset render failed for levelup_generate_v1, using inline fallback")
        system = (
            "You are generating a mastery-gating level-up quiz. "
            "Create a bounded mixed-format quiz testing concept understanding. "
            "Include both short_answer and mcq types. "
            "Progress from recall to application to analysis. "
            "Return valid JSON only."
        )
        user = (
            f"TARGET_COUNT: {target_count}\n"
            f"CONCEPT: {concept_name}\n"
            f"DESCRIPTION: {concept_desc}\n"
            f"RELATED CONCEPTS: {adjacent_str}\n"
            f"{chunks_block}"
            f"{chat_block}"
        )
        return user, None, system
