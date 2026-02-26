from __future__ import annotations

import json
import math
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

MIN_ITEMS = 5
MAX_ITEMS = 12
PASS_SCORE = 0.75
RETRY_HINT = "create a new level-up quiz to retry"
MAX_GENERATION_ATTEMPTS = 3


class LevelUpQuizNotFoundError(ValueError):
    pass


class LevelUpQuizValidationError(ValueError):
    pass


class LevelUpQuizGradingError(ValueError):
    pass


class LevelUpQuizUnavailableError(RuntimeError):
    pass


def create_level_up_quiz(
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
        raise LevelUpQuizNotFoundError("Concept not found in workspace.")
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


def submit_level_up_quiz(
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
                raise LevelUpQuizNotFoundError("Quiz not found in workspace.")
            if int(quiz["user_id"]) != user_id:
                raise LevelUpQuizValidationError("Quiz does not belong to user.")

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
                raise LevelUpQuizValidationError("Quiz has no items to submit.")

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
            raise


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
) -> list[dict[str, Any]]:
    if items:
        return _normalize_items(items, min_items=min_items, max_items=max_items)

    target = _validate_question_count(
        question_count=question_count,
        min_items=min_items,
        max_items=max_items,
    )
    if llm_client is not None and _supports_quiz_generation(llm_client):
        generated = _generate_level_up_items_with_retries(
            session,
            workspace_id=workspace_id,
            concept_id=concept_id,
            llm_client=llm_client,
            target_count=target,
            min_items=min_items,
            max_items=max_items,
        )
        if generated:
            return generated

    return _auto_items(concept, target, min_items=min_items, max_items=max_items)


def _supports_quiz_generation(llm_client: GraphLLMClient) -> bool:
    return callable(getattr(llm_client, "extract_raw_graph", None)) and callable(
        getattr(llm_client, "disambiguate", None)
    )


def _validate_question_count(
    *,
    question_count: int | None,
    min_items: int,
    max_items: int,
) -> int:
    if question_count is None:
        return min_items
    if question_count < min_items or question_count > max_items:
        raise LevelUpQuizValidationError(
            f"question_count must be between {min_items} and {max_items}"
        )
    return question_count


def _generate_level_up_items_with_retries(
    session: Session,
    *,
    workspace_id: int,
    concept_id: int,
    llm_client: GraphLLMClient,
    target_count: int,
    min_items: int,
    max_items: int,
) -> list[dict[str, Any]] | None:
    context = _generation_context(session, workspace_id=workspace_id, concept_id=concept_id)
    prompt = (
        "Return JSON only. Schema: {\"items\":[{\"item_type\":\"short_answer|mcq\","
        "\"prompt\":\"...\",\"payload\":{...}}]}.\n"
        "Rules: produce a level-up quiz with mixed item types and diverse prompts.\n"
        "MCQ payload must include choices[{id,text}], correct_choice_id, critical_choice_ids,"
        " and optional choice_explanations.\n"
        f"TARGET_COUNT: {target_count}\n"
        f"MIN_ITEMS: {min_items}\n"
        f"MAX_ITEMS: {max_items}\n"
        f"CONTEXT_JSON: {json.dumps(context, ensure_ascii=True)}"
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
                "Level-up generation response is not valid JSON.",
            )
            raw_items = payload.get("items")
            if not isinstance(raw_items, list):
                raise LevelUpQuizValidationError("Level-up generation response must include items.")
            normalized = _normalize_items(raw_items, min_items=min_items, max_items=max_items)
            _ensure_diversity(normalized)
            if len(normalized) != target_count:
                raise LevelUpQuizValidationError(
                    f"Generated quiz must have exactly {target_count} items."
                )
            return normalized
        except LevelUpQuizValidationError as exc:
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
        raise LevelUpQuizNotFoundError("Concept not found in workspace.")

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
    return {
        "concept_name": concept_name,
        "concept_description": str(concept["description"] or ""),
        "adjacent_concepts": adjacent,
    }


def _parse_json(response: str, message: str) -> dict[str, Any]:
    text_value = response.strip()
    if text_value.startswith("```"):
        text_value = "\n".join(
            line for line in text_value.splitlines() if not line.strip().startswith("```")
        ).strip()
    try:
        payload = json.loads(text_value)
    except json.JSONDecodeError as exc:
        raise LevelUpQuizValidationError(message) from exc
    if not isinstance(payload, dict):
        raise LevelUpQuizValidationError(message)
    return payload


def _ensure_diversity(items: list[dict[str, Any]]) -> None:
    types = {item["item_type"] for item in items}
    if types != {"short_answer", "mcq"}:
        raise LevelUpQuizValidationError(
            "level-up quiz requires at least one short_answer and one mcq."
        )
    seen: set[str] = set()
    for item in items:
        normalized_prompt = " ".join(str(item["prompt"]).lower().split())
        if normalized_prompt in seen:
            raise LevelUpQuizValidationError("level-up quiz prompts must be diverse.")
        seen.add(normalized_prompt)


def _normalize_items(
    items: list[dict[str, Any]],
    *,
    min_items: int = MIN_ITEMS,
    max_items: int = MAX_ITEMS,
) -> list[dict[str, Any]]:
    if len(items) < min_items or len(items) > max_items:
        raise LevelUpQuizValidationError(
            f"items must include between {min_items} and {max_items} entries"
        )
    normalized: list[dict[str, Any]] = []
    for item in items:
        item_type = str(item.get("item_type", "")).strip().lower()
        prompt = str(item.get("prompt", "")).strip()
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        if not prompt or item_type not in {"short_answer", "mcq"}:
            raise LevelUpQuizValidationError("Each item requires valid item_type and prompt.")
        payload = (
            _normalize_short(payload)
            if item_type == "short_answer"
            else _normalize_mcq(payload)
        )
        normalized.append({"item_type": item_type, "prompt": prompt, "payload": payload})
    return normalized


def _normalize_short(payload: dict[str, Any]) -> dict[str, Any]:
    rubric = _str_list(payload.get("rubric_keywords"), required=True, field="rubric_keywords")
    critical = _str_list(
        payload.get("critical_misconception_keywords", []),
        required=False,
        field="critical_misconception_keywords",
    )
    normalized = {"rubric_keywords": rubric, "critical_misconception_keywords": critical}
    generation_context = _normalize_generation_context(payload.get("_generation_context"))
    if generation_context is not None:
        normalized["_generation_context"] = generation_context
    return normalized


def _normalize_mcq(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("choices")
    if not isinstance(raw, list) or len(raw) < 2:
        raise LevelUpQuizValidationError("mcq payload requires at least two choices.")
    choices: list[dict[str, str]] = []
    ids: list[str] = []
    for choice in raw:
        if not isinstance(choice, dict):
            raise LevelUpQuizValidationError("mcq choices must be objects.")
        choice_id = str(choice.get("id", "")).strip()
        choice_text = str(choice.get("text", "")).strip()
        if not choice_id or not choice_text or choice_id in ids:
            raise LevelUpQuizValidationError("mcq choices require unique id and non-empty text.")
        ids.append(choice_id)
        choices.append({"id": choice_id, "text": choice_text})

    correct = str(payload.get("correct_choice_id", "")).strip()
    critical = _str_list(
        payload.get("critical_choice_ids", []),
        required=False,
        field="critical_choice_ids",
    )
    if correct not in ids or any(
        choice_id not in ids or choice_id == correct for choice_id in critical
    ):
        raise LevelUpQuizValidationError("mcq payload has invalid correct/critical choice ids.")
    raw_explanations = payload.get("choice_explanations", {})
    if raw_explanations is None:
        raw_explanations = {}
    if not isinstance(raw_explanations, dict):
        raise LevelUpQuizValidationError("mcq choice_explanations must be an object.")
    explanations: dict[str, str] = {}
    for choice in choices:
        choice_id = choice["id"]
        raw_text = raw_explanations.get(choice_id)
        provided = str(raw_text).strip() if raw_text is not None else ""
        if provided:
            explanations[choice_id] = provided
            continue
        explanations[choice_id] = _default_choice_explanation(
            choice_id=choice_id,
            correct_choice_id=correct,
            critical_choice_ids=critical,
            choice_text=choice["text"],
        )
    normalized = {
        "choices": choices,
        "correct_choice_id": correct,
        "critical_choice_ids": critical,
        "choice_explanations": explanations,
    }
    generation_context = _normalize_generation_context(payload.get("_generation_context"))
    if generation_context is not None:
        normalized["_generation_context"] = generation_context
    return normalized


def _str_list(value: Any, *, required: bool, field: str) -> list[str]:
    if not isinstance(value, list):
        raise LevelUpQuizValidationError(f"{field} must be a list.")
    out: list[str] = []
    for item in value:
        text_value = str(item).strip().lower()
        if not text_value:
            raise LevelUpQuizValidationError(f"{field} cannot contain empty values.")
        if text_value not in out:
            out.append(text_value)
    if required and not out:
        raise LevelUpQuizValidationError(f"{field} cannot be empty.")
    return out


def _normalize_generation_context(raw_context: Any) -> dict[str, Any] | None:
    if raw_context is None:
        return None
    if not isinstance(raw_context, dict):
        raise LevelUpQuizValidationError("_generation_context must be an object.")

    concept_name = str(raw_context.get("concept_name", "")).strip()
    if not concept_name:
        raise LevelUpQuizValidationError("_generation_context.concept_name must not be empty.")
    concept_description = str(raw_context.get("concept_description", "")).strip()
    context_source = str(raw_context.get("context_source", "")).strip().lower() or "generated"
    if context_source not in {"generated", "provided"}:
        raise LevelUpQuizValidationError(
            "_generation_context.context_source must be generated or provided."
        )
    context_keywords = _str_list(
        raw_context.get("context_keywords", []),
        required=False,
        field="_generation_context.context_keywords",
    )
    if not context_keywords:
        context_keywords = _extract_context_keywords(
            concept_name=concept_name,
            concept_description=concept_description,
        )
    return {
        "concept_name": concept_name,
        "concept_description": concept_description,
        "context_keywords": context_keywords,
        "context_source": context_source,
    }


def _safe_mcq_choices(raw_payload: Any) -> list[dict[str, str]] | None:
    if not isinstance(raw_payload, dict):
        return None
    raw_choices = raw_payload.get("choices")
    if not isinstance(raw_choices, list):
        return None

    out: list[dict[str, str]] = []
    for choice in raw_choices:
        if not isinstance(choice, dict):
            continue
        choice_id = str(choice.get("id", "")).strip()
        text_value = str(choice.get("text", "")).strip()
        if not choice_id or not text_value:
            continue
        out.append({"id": choice_id, "text": text_value})

    return out or None


def _extract_context_keywords(*, concept_name: str, concept_description: str) -> list[str]:
    raw_tokens = (concept_name + " " + concept_description).lower().split()
    tokens = ["".join(ch for ch in token if ch.isalnum()) for token in raw_tokens]
    keywords = [token for token in tokens if len(token) > 2][:4]
    return keywords or ["concept"]


def _attach_generation_context(
    items: list[dict[str, Any]],
    *,
    concept_name: str,
    concept_description: str,
    context_source: str,
) -> list[dict[str, Any]]:
    context_keywords = _extract_context_keywords(
        concept_name=concept_name,
        concept_description=concept_description,
    )
    with_context: list[dict[str, Any]] = []
    for item in items:
        payload = dict(item["payload"])
        payload["_generation_context"] = {
            "concept_name": concept_name,
            "concept_description": concept_description,
            "context_keywords": context_keywords,
            "context_source": context_source,
        }
        with_context.append(
            {
                "item_type": item["item_type"],
                "prompt": item["prompt"],
                "payload": payload,
            }
        )
    return with_context


def _auto_items(
    concept: dict[str, Any],
    question_count: int,
    *,
    min_items: int = MIN_ITEMS,
    max_items: int = MAX_ITEMS,
) -> list[dict[str, Any]]:
    if question_count < min_items or question_count > max_items:
        raise LevelUpQuizValidationError(
            f"question_count must be between {min_items} and {max_items}"
        )
    name = str(concept["canonical_name"])
    desc = str(concept["description"] or "")
    keywords = _extract_context_keywords(concept_name=name, concept_description=desc)
    short_count = min(
        max(int(math.floor((question_count * 0.6) + 0.5)), 1),
        question_count - 1,
    )
    mcq_count = question_count - short_count
    short_templates = [
        f"Explain the core idea of {name} in one concise paragraph.",
        f"What misconception about {name} causes the most errors?",
        f"How would you teach {name} to a beginner using one example?",
        f"Why is {name} important in solving real problems?",
        f"Compare {name} with a closely related concept and highlight one difference.",
        f"What is the minimum definition needed to correctly identify {name}?",
        f"Give one test you can apply to verify understanding of {name}.",
        f"What mistake would invalidate reasoning about {name}?",
    ]
    mcq_templates = [
        f"Which option best captures the definition of {name}?",
        f"Which statement about {name} is most accurate?",
        f"Which choice correctly applies {name} in context?",
        f"Which option reveals a critical misunderstanding of {name}?",
        f"Which statement distinguishes {name} from a similar concept?",
        f"Which answer best explains why {name} matters?",
    ]

    short = [
        {
            "item_type": "short_answer",
            "prompt": short_templates[index],
            "payload": {
                "rubric_keywords": keywords,
                "critical_misconception_keywords": ["contradiction", "unrelated"],
            },
        }
        for index in range(short_count)
    ]
    mcq = [
        {
            "item_type": "mcq",
            "prompt": mcq_templates[index],
            "payload": {
                "choices": [
                    {"id": "a", "text": f"Aligned with {name}."},
                    {"id": "b", "text": f"Partially related to {name} but incomplete."},
                    {"id": "c", "text": f"Generic statement not specific to {name}."},
                    {"id": "d", "text": f"Contradicts the core definition of {name}."},
                ],
                "correct_choice_id": "a",
                "critical_choice_ids": ["d"],
                "choice_explanations": {
                    "a": "Correct: this option best matches the concept.",
                    "b": "Incorrect: partially relevant but not sufficient.",
                    "c": "Incorrect: too generic to be the best answer.",
                    "d": "Incorrect (critical): this option contradicts the concept.",
                },
            },
        }
        for index in range(mcq_count)
    ]
    return short + mcq


def _validate_answers(items: list[dict[str, Any]], answers: list[dict[str, Any]]) -> dict[int, str]:
    if not answers:
        raise LevelUpQuizValidationError("answers must not be empty.")
    mapped: dict[int, str] = {}
    for answer in answers:
        item_id = answer.get("item_id")
        text_value = str(answer.get("answer", "")).strip()
        if not isinstance(item_id, int) or not text_value or item_id in mapped:
            raise LevelUpQuizValidationError(
                "answers must include unique item_id with non-empty answer."
            )
        mapped[item_id] = text_value

    item_ids = {item["item_id"] for item in items}
    if set(mapped.keys()) != item_ids:
        raise LevelUpQuizValidationError("answers must include every quiz item exactly once.")

    for item in items:
        if item["item_type"] != "mcq":
            continue
        choices = {choice["id"] for choice in item["payload"]["choices"]}
        if mapped[item["item_id"]] not in choices:
            raise LevelUpQuizValidationError("mcq answers must match a valid choice id.")
    return mapped


def _grade_short_items_without_llm(
    items: list[dict[str, Any]],
    answer_map: dict[int, str],
) -> dict[str, Any]:
    graded: list[dict[str, Any]] = []
    total_score = 0.0
    for item in items:
        payload = item["payload"]
        answer = answer_map[item["item_id"]].strip().lower()
        rubric_keywords = [
            str(v).strip().lower()
            for v in payload.get("rubric_keywords", [])
            if str(v).strip()
        ]
        critical_keywords = [
            str(v).strip().lower()
            for v in payload.get("critical_misconception_keywords", [])
            if str(v).strip()
        ]
        rubric_hits = sum(1 for keyword in rubric_keywords if keyword in answer)
        score = (
            min(1.0, rubric_hits / max(1, len(rubric_keywords)))
            if rubric_keywords
            else (0.5 if answer else 0.0)
        )
        critical = any(keyword in answer for keyword in critical_keywords)
        if critical:
            feedback = "Critical misconception detected; revisit the concept definition."
        elif score >= 0.95:
            feedback = "Strong answer that covered the key rubric points."
        elif score > 0.0:
            feedback = "Partially correct; include more core keywords from the concept."
        else:
            feedback = "Answer missed the core rubric points; review the concept and retry."
        graded.append(
            {
                "item_id": item["item_id"],
                "score": score,
                "critical_misconception": critical,
                "feedback": feedback,
            }
        )
        total_score += score

    average = total_score / max(1, len(items))
    overall = (
        "Short-answer graded using rubric keyword coverage because LLM grading was unavailable. "
        f"Average short-answer score: {average:.2f}."
    )
    return {"items": graded, "overall_feedback": overall}


def _grading_prompt(items: list[dict[str, Any]], answer_map: dict[int, str]) -> str:
    ids = [item["item_id"] for item in items]
    submission = [{**item, "answer": answer_map[item["item_id"]]} for item in items]
    return (
        "Return JSON only with keys items and overall_feedback. "
        "Use payload._generation_context as the canonical generation-time context. "
        "Each items entry must include item_id, score(0..1), "
        "critical_misconception(bool), feedback.\n"
        f"ITEM_IDS_JSON: {json.dumps(ids, ensure_ascii=True)}\n"
        f"QUIZ_SUBMISSION_JSON: {json.dumps(submission, ensure_ascii=True)}"
    )


def _parse_grading(response: str, item_ids: list[int]) -> dict[str, Any]:
    text_value = response.strip()
    if text_value.startswith("```"):
        text_value = "\n".join(
            line for line in text_value.splitlines() if not line.strip().startswith("```")
        ).strip()
    try:
        payload = json.loads(text_value)
    except json.JSONDecodeError as exc:
        raise LevelUpQuizGradingError("Grading response is not valid JSON.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise LevelUpQuizGradingError("Grading response missing items list.")
    if (
        not isinstance(payload.get("overall_feedback"), str)
        or not payload["overall_feedback"].strip()
    ):
        raise LevelUpQuizGradingError("Grading response missing overall_feedback.")

    by_id: dict[int, dict[str, Any]] = {}
    for item in payload["items"]:
        if not isinstance(item, dict) or not isinstance(item.get("item_id"), int):
            raise LevelUpQuizGradingError("Invalid grading item payload.")
        score = item.get("score")
        critical = item.get("critical_misconception")
        feedback = item.get("feedback")
        if (
            not isinstance(score, (int, float))
            or float(score) < 0
            or float(score) > 1
            or not isinstance(critical, bool)
            or not isinstance(feedback, str)
            or not feedback.strip()
        ):
            raise LevelUpQuizGradingError("Invalid grading score/critical/feedback values.")
        by_id[int(item["item_id"])] = {
            "item_id": int(item["item_id"]),
            "score": float(score),
            "critical_misconception": critical,
            "feedback": feedback.strip(),
        }

    if set(by_id.keys()) != set(item_ids):
        raise LevelUpQuizGradingError("grading items must cover every quiz item exactly once.")

    return {
        "items": [by_id[item_id] for item_id in item_ids],
        "overall_feedback": payload["overall_feedback"].strip(),
    }


def _grade_mcq_items(
    items: list[dict[str, Any]],
    answer_map: dict[int, str],
) -> list[dict[str, Any]]:
    graded: list[dict[str, Any]] = []
    for item in items:
        payload = item["payload"]
        answer = answer_map[item["item_id"]]
        score = 1.0 if answer == payload["correct_choice_id"] else 0.0
        critical = answer in payload["critical_choice_ids"]
        feedback = payload["choice_explanations"].get(
            answer,
            "Incorrect: the selected option does not match the concept.",
        )
        graded.append(
            {
                "item_id": item["item_id"],
                "score": score,
                "critical_misconception": critical,
                "feedback": feedback,
            }
        )
    return graded


def _compose_feedback_items(
    *,
    item_refs: list[dict[str, Any]],
    graded_items: Any,
) -> list[dict[str, Any]]:
    if not isinstance(graded_items, list):
        return []

    item_types_by_id: dict[int, str] = {}
    for item in item_refs:
        item_id = item.get("item_id")
        item_type = str(item.get("item_type", "")).strip().lower()
        if isinstance(item_id, int) and item_type:
            item_types_by_id[item_id] = item_type

    by_id: dict[int, dict[str, Any]] = {}
    for graded_item in graded_items:
        if not isinstance(graded_item, dict):
            continue
        item_id = graded_item.get("item_id")
        if not isinstance(item_id, int):
            continue
        item_type = item_types_by_id.get(item_id)
        if item_type is None:
            continue
        feedback = str(graded_item.get("feedback", "")).strip()
        if not feedback:
            continue
        score = _coerce_score(graded_item.get("score"))
        critical = bool(graded_item.get("critical_misconception", False))
        result = _derive_item_result(item_type=item_type, score=score, critical=critical)
        by_id[item_id] = {
            "item_id": item_id,
            "item_type": item_type,
            "result": result,
            "is_correct": result == "correct",
            "critical_misconception": critical,
            "feedback": feedback,
            "score": score,
        }

    return [by_id[item_id] for item_id in item_types_by_id if item_id in by_id]


def _coerce_score(value: Any) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        return None
    score = float(value)
    return max(0.0, min(1.0, score))


def _derive_item_result(*, item_type: str, score: float | None, critical: bool) -> str:
    if item_type == "mcq":
        return "correct" if score is not None and score >= 1.0 else "incorrect"

    if item_type == "short_answer":
        if critical:
            return "incorrect"
        if score is None:
            return "partial"
        if score >= 1.0:
            return "correct"
        if score <= 0.0:
            return "incorrect"
        return "partial"

    if score is None:
        return "partial"
    if score >= 1.0:
        return "correct"
    if score <= 0.0:
        return "incorrect"
    return "partial"


def _default_choice_explanation(
    *,
    choice_id: str,
    correct_choice_id: str,
    critical_choice_ids: list[str],
    choice_text: str,
) -> str:
    if choice_id == correct_choice_id:
        return "Correct: this option best matches the concept."
    if choice_id in critical_choice_ids:
        return "Incorrect (critical): this option contradicts the concept."
    return f"Incorrect: '{choice_text}' is not the best match."


def _build_overall_feedback(
    *,
    short_overall_feedback: str,
    mcq_graded: list[dict[str, Any]],
    passed: bool,
    critical: bool,
) -> str:
    parts: list[str] = []
    base = short_overall_feedback.strip()
    if base:
        parts.append(base)
    else:
        parts.append("Quiz graded.")
    if mcq_graded:
        correct = sum(1 for item in mcq_graded if float(item["score"]) >= 1.0)
        parts.append(f"MCQ correctness: {correct}/{len(mcq_graded)}.")
    if critical:
        parts.append("A critical misconception was detected.")
    if passed:
        parts.append("You passed the level-up criteria.")
    else:
        parts.append("You did not pass; review feedback and retry with a new quiz.")
    return " ".join(parts)


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
        raise LevelUpQuizValidationError("session_id is not valid for workspace/user scope.")


__all__ = [
    "LevelUpQuizGradingError",
    "LevelUpQuizNotFoundError",
    "LevelUpQuizUnavailableError",
    "LevelUpQuizValidationError",
    "create_level_up_quiz",
    "submit_level_up_quiz",
]
