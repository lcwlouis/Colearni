"""Shared quiz creation and submission orchestration.

Provides generic create/submit quiz flows used by both level-up
and practice quiz types.  Level-up-specific and practice-specific
behaviour is handled by their respective modules which wrap these
shared functions.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from core.contracts import GraphLLMClient
from core.observability import (
    SPAN_KIND_CHAIN,
    emit_event,
    observation_context,
    set_input_output,
    set_span_kind,
    start_span,
)
from sqlalchemy import text
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
    grading_prompt as _grading_prompt,
)
from domain.learning.quiz_grading import (
    parse_grading as _parse_grading,
)
from domain.learning.quiz_grading import (
    validate_answers as _validate_answers,
)

MIN_ITEMS = 5
MAX_ITEMS = 12
PASS_SCORE = 0.75
RETRY_HINT = "create a new level-up quiz to retry"
MAX_GENERATION_ATTEMPTS = 3


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
        _validate_session_scope(
            session,
            workspace_id=workspace_id,
            user_id=user_id,
            session_id=session_id,
        )

    concept = (
        session.execute(
            text(
                """
                SELECT canonical_name, description
                FROM concepts_canon
                WHERE id = :concept_id AND workspace_id = :workspace_id AND is_active = TRUE
                LIMIT 1
                """
            ),
            {"concept_id": concept_id, "workspace_id": workspace_id},
        )
        .mappings()
        .first()
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

    quiz = (
        session.execute(
            text(
                """
                INSERT INTO quizzes (
                    workspace_id,
                    user_id,
                    session_id,
                    concept_id,
                    quiz_type,
                    status
                )
                VALUES (:workspace_id, :user_id, :session_id, :concept_id, :quiz_type, 'ready')
                RETURNING id, status
                """
            ),
            {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "session_id": session_id,
                "concept_id": concept_id,
                "quiz_type": quiz_type,
            },
        )
        .mappings()
        .one()
    )
    quiz_id = int(quiz["id"])

    session.execute(
        text(
            """
            INSERT INTO quiz_items (quiz_id, position, item_type, prompt, payload)
            VALUES (:quiz_id, :position, :item_type, :prompt, CAST(:payload AS jsonb))
            """
        ),
        [
            {
                "quiz_id": quiz_id,
                "position": idx,
                "item_type": item["item_type"],
                "prompt": item["prompt"],
                "payload": json.dumps(item["payload"], ensure_ascii=True),
            }
            for idx, item in enumerate(normalized_items, start=1)
        ],
    )
    session.commit()

    rows = (
        session.execute(
            text(
                """
                SELECT id AS item_id, position, item_type, prompt, payload
                FROM quiz_items
                WHERE quiz_id = :quiz_id
                ORDER BY position
                """
            ),
            {"quiz_id": quiz_id},
        )
        .mappings()
        .all()
    )
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
    update_mastery: bool = True,
    retry_hint: str = RETRY_HINT,
    run_id: str | None = None,
) -> dict[str, Any]:
    resolved_run_id = run_id or str(uuid4())
    event_prefix = "grading.level_up" if quiz_type == "level_up" else "grading.practice"
    operation = f"{event_prefix}.submit"
    stage = "load_quiz"

    with observation_context(
        component="grading",
        operation=operation,
        workspace_id=workspace_id,
        quiz_id=quiz_id,
        run_id=resolved_run_id,
    ), start_span(
        event_prefix,
        component="grading",
        operation=operation,
        workspace_id=workspace_id,
        quiz_id=quiz_id,
        run_id=resolved_run_id,
    ) as span:
        set_span_kind(span, SPAN_KIND_CHAIN)
        try:
            quiz = (
                session.execute(
                    text(
                        """
                        SELECT id, user_id, concept_id
                        FROM quizzes
                        WHERE id = :quiz_id
                          AND workspace_id = :workspace_id
                          AND quiz_type = :quiz_type
                        FOR UPDATE
                        """
                    ),
                    {"quiz_id": quiz_id, "workspace_id": workspace_id, "quiz_type": quiz_type},
                )
                .mappings()
                .first()
            )
            if quiz is None:
                raise QuizNotFoundError("Quiz not found in workspace.")
            if int(quiz["user_id"]) != user_id:
                raise QuizValidationError("Quiz does not belong to user.")

            stage = "load_items"
            item_rows = (
                session.execute(
                    text(
                        """
                        SELECT id AS item_id, item_type, prompt, payload
                        FROM quiz_items
                        WHERE quiz_id = :quiz_id
                        ORDER BY position
                        """
                    ),
                    {"quiz_id": quiz_id},
                )
                .mappings()
                .all()
            )
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
            existing = (
                session.execute(
                    text(
                        """
                        SELECT id, score, passed, grading
                        FROM quiz_attempts
                        WHERE quiz_id = :quiz_id AND user_id = :user_id AND graded_at IS NOT NULL
                        ORDER BY id
                        LIMIT 1
                        """
                    ),
                    {"quiz_id": quiz_id, "user_id": user_id},
                )
                .mappings()
                .first()
            )
            if existing is not None:
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
                    mastery = (
                        session.execute(
                            text(
                                """
                                SELECT status, score
                                FROM mastery
                                WHERE workspace_id = :workspace_id
                                  AND user_id = :user_id
                                  AND concept_id = :concept_id
                                LIMIT 1
                                """
                            ),
                            {
                                "workspace_id": workspace_id,
                                "user_id": user_id,
                                "concept_id": int(quiz["concept_id"]),
                            },
                        )
                        .mappings()
                        .first()
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
                    short_prompt = _grading_prompt(short_items, answer_map)
                    short_grading = _parse_grading(
                        llm_client.generate_tutor_text(prompt=short_prompt),
                        [item["item_id"] for item in short_items],
                    )
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
            session.execute(
                text(
                    """
                    INSERT INTO quiz_attempts (
                        quiz_id,
                        user_id,
                        answers,
                        grading,
                        score,
                        passed,
                        graded_at
                    )
                    VALUES (
                        :quiz_id,
                        :user_id,
                        CAST(:answers AS jsonb),
                        CAST(:grading AS jsonb),
                        :score,
                        :passed,
                        now()
                    )
                    """
                ),
                {
                    "quiz_id": quiz_id,
                    "user_id": user_id,
                    "answers": json.dumps({"answers": answers}, ensure_ascii=True),
                    "grading": json.dumps(grading_payload, ensure_ascii=True),
                    "score": mastery_score,
                    "passed": passed,
                },
            )
            attempt_id = int(
                session.execute(text("SELECT currval('quiz_attempts_id_seq')")).scalar_one()
            )
            session.execute(
                text(
                    "UPDATE quizzes "
                    "SET status = 'graded', updated_at = now() "
                    "WHERE id = :quiz_id"
                ),
                {"quiz_id": quiz_id},
            )
            if update_mastery:
                stage = "update_mastery"
                session.execute(
                    text(
                        """
                        INSERT INTO mastery (workspace_id, user_id, concept_id, score, status)
                        VALUES (:workspace_id, :user_id, :concept_id, :score, :status)
                        ON CONFLICT (user_id, concept_id)
                        DO UPDATE SET
                            workspace_id = EXCLUDED.workspace_id,
                            score = EXCLUDED.score,
                            status = EXCLUDED.status,
                            updated_at = now()
                        """
                    ),
                    {
                        "workspace_id": workspace_id,
                        "user_id": user_id,
                        "concept_id": int(quiz["concept_id"]),
                        "score": mastery_score,
                        "status": mastery_status,
                    },
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
            if isinstance(exc, _QVE) and not isinstance(exc, QuizValidationError):
                raise QuizValidationError(str(exc)) from exc
            if isinstance(exc, _QGE) and not isinstance(exc, QuizGradingError):
                raise QuizGradingError(str(exc)) from exc
            raise


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
    context = _generation_context(session, workspace_id=workspace_id, concept_id=concept_id)
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
    prompt = (
        "You are creating a quiz to assess understanding of a concept.\n"
        f"CONCEPT: {concept_name}\n"
        f"DESCRIPTION: {concept_desc}\n"
        f"RELATED CONCEPTS: {adjacent_str}\n"
        f"{chunks_block}"
        f"{chat_block}\n"
        "Return ONLY valid JSON with this schema:\n"
        '{"items":[{"item_type":"short_answer"|"mcq","prompt":"...","payload":{...}}]}\n\n'
        "Rules:\n"
        f"- Produce exactly {target_count} items with a mix of short_answer and mcq types.\n"
        "- Each question must be SPECIFIC to the concept — reference facts, examples, or properties unique to it.\n"
        "- short_answer payload: {\"rubric_keywords\":[...],\"critical_misconception_keywords\":[...]}\n"
        "- mcq payload: {\"choices\":[{\"id\":\"a\",\"text\":\"...\"}, ...], \"correct_choice_id\":\"a\", "
        "\"critical_choice_ids\":[\"d\"], \"choice_explanations\":{\"a\":\"...\", ...}}\n"
        "- MCQ choices must contain SPECIFIC, distinct content — not generic placeholders.\n"
        "  The correct answer must be clearly right, distractors must be plausible but wrong.\n"
        "- Make questions progressively harder: start with recall, then application, then analysis.\n"
        "- Do NOT use generic prompts like 'Which is most accurate about X'. Ask specific questions.\n"
    )
    retry_prompt = prompt
    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        try:
            llm_response = llm_client.generate_tutor_text(prompt=retry_prompt)
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


def _generation_context(
    session: Session,
    *,
    workspace_id: int,
    concept_id: int,
) -> dict[str, Any]:
    concept = (
        session.execute(
            text(
                """
                SELECT canonical_name, description
                FROM concepts_canon
                WHERE id = :concept_id
                  AND workspace_id = :workspace_id
                  AND is_active = TRUE
                LIMIT 1
                """
            ),
            {"workspace_id": workspace_id, "concept_id": concept_id},
        )
        .mappings()
        .first()
    )
    if concept is None:
        raise QuizNotFoundError("Concept not found in workspace.")

    rows = (
        session.execute(
            text(
                """
                SELECT src.canonical_name AS src_name, tgt.canonical_name AS tgt_name
                FROM edges_canon e
                JOIN concepts_canon src ON src.id = e.src_id
                JOIN concepts_canon tgt ON tgt.id = e.tgt_id
                WHERE e.workspace_id = :workspace_id
                  AND ((e.src_id = :concept_id AND tgt.is_active = TRUE)
                       OR (e.tgt_id = :concept_id AND src.is_active = TRUE))
                ORDER BY e.weight DESC, e.id ASC
                LIMIT 8
                """
            ),
            {"workspace_id": workspace_id, "concept_id": concept_id},
        )
        .mappings()
        .all()
    )

    concept_name = str(concept["canonical_name"])
    adjacent = [
        str(row["tgt_name"]) if str(row["src_name"]) == concept_name else str(row["src_name"])
        for row in rows
    ]
    chunk_rows = (
        session.execute(
            text(
                """
                SELECT ch.text
                FROM provenance p
                JOIN chunks ch ON ch.id = p.chunk_id AND ch.workspace_id = p.workspace_id
                WHERE p.workspace_id = :workspace_id
                  AND p.target_type = 'concept'
                  AND p.target_id = :concept_id
                ORDER BY p.chunk_id ASC
                LIMIT 3
                """
            ),
            {"workspace_id": workspace_id, "concept_id": concept_id},
        )
        .mappings()
        .all()
    )
    chunk_excerpts = [str(r["text"])[:300] for r in chunk_rows]
    return {
        "concept_name": concept_name,
        "concept_description": str(concept["description"] or ""),
        "adjacent_concepts": adjacent,
        "chunk_excerpts": chunk_excerpts,
    }


def _validate_session_scope(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    session_id: int,
) -> None:
    row = (
        session.execute(
            text(
                """
                SELECT id
                FROM chat_sessions
                WHERE id = :session_id
                  AND workspace_id = :workspace_id
                  AND user_id = :user_id
                LIMIT 1
                """
            ),
            {
                "session_id": session_id,
                "workspace_id": workspace_id,
                "user_id": user_id,
            },
        )
        .mappings()
        .first()
    )
    if row is None:
        raise QuizValidationError("session_id is not valid for workspace/user scope.")
