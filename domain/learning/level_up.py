from __future__ import annotations

import json
import math
from typing import Any

from core.contracts import GraphLLMClient
from sqlalchemy import text
from sqlalchemy.orm import Session

MIN_ITEMS = 5
MAX_ITEMS = 10
PASS_SCORE = 0.75
RETRY_HINT = "create a new level-up quiz to retry"


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
    question_count: int,
    items: list[dict[str, Any]] | None,
    quiz_type: str = "level_up",
    min_items: int = MIN_ITEMS,
    max_items: int = MAX_ITEMS,
    context_source: str | None = None,
) -> dict[str, Any]:
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

    normalized_items = (
        _normalize_items(items, min_items=min_items, max_items=max_items)
        if items
        else _auto_items(concept, question_count, min_items=min_items, max_items=max_items)
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
                SELECT id AS item_id, position, item_type, prompt
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
) -> dict[str, Any]:
    quiz = (
        session.execute(
            text(
                """
                SELECT id, user_id, concept_id
                FROM quizzes
                WHERE id = :quiz_id AND workspace_id = :workspace_id AND quiz_type = :quiz_type
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
        return payload

    if not item_rows:
        raise LevelUpQuizValidationError("Quiz has no items to submit.")

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

    answer_map = _validate_answers(items, answers)
    short_items = [item for item in items if item["item_type"] == "short_answer"]
    mcq_items = [item for item in items if item["item_type"] == "mcq"]
    graded_by_id: dict[int, dict[str, Any]] = {}
    short_overall_feedback = ""

    if short_items:
        if llm_client is None:
            raise LevelUpQuizUnavailableError("LLM grading client is unavailable.")
        short_prompt = _grading_prompt(short_items, answer_map)
        short_grading = _parse_grading(
            llm_client.generate_tutor_text(prompt=short_prompt),
            [item["item_id"] for item in short_items],
        )
        short_overall_feedback = short_grading["overall_feedback"]
        for graded_item in short_grading["items"]:
            graded_by_id[int(graded_item["item_id"])] = graded_item

    mcq_graded = _grade_mcq_items(mcq_items, answer_map)
    for graded_item in mcq_graded:
        graded_by_id[int(graded_item["item_id"])] = graded_item

    ordered_items = [graded_by_id[item["item_id"]] for item in items]
    feedback_items = _compose_feedback_items(
        item_refs=[{"item_id": item["item_id"], "item_type": item["item_type"]} for item in items],
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

    session.execute(
        text(
            """
            INSERT INTO quiz_attempts (quiz_id, user_id, answers, grading, score, passed, graded_at)
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
    attempt_id = int(session.execute(text("SELECT currval('quiz_attempts_id_seq')")).scalar_one())
    session.execute(
        text("UPDATE quizzes SET status = 'graded', updated_at = now() WHERE id = :quiz_id"),
        {"quiz_id": quiz_id},
    )
    if update_mastery:
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
    return payload


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
    short = [
        {
            "item_type": "short_answer",
            "prompt": f"Explain the core idea of {name}.",
            "payload": {
                "rubric_keywords": keywords,
                "critical_misconception_keywords": ["contradiction", "unrelated"],
            },
        }
        for _ in range(short_count)
    ]
    mcq = [
        {
            "item_type": "mcq",
            "prompt": f"Which option best describes {name}?",
            "payload": {
                "choices": [
                    {"id": "a", "text": f"Aligned with {name}."},
                    {"id": "b", "text": "Partially relevant."},
                    {"id": "c", "text": "Too generic."},
                    {"id": "d", "text": "Contradicts the concept."},
                ],
                "correct_choice_id": "a",
                "critical_choice_ids": ["d"],
                "choice_explanations": {
                    "a": "Correct: this option best matches the concept.",
                    "b": "Incorrect: this option is only partially relevant.",
                    "c": "Incorrect: this option is too generic to be correct.",
                    "d": "Incorrect (critical): this option contradicts the concept.",
                },
            },
        }
        for _ in range(mcq_count)
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


__all__ = [
    "LevelUpQuizGradingError",
    "LevelUpQuizNotFoundError",
    "LevelUpQuizUnavailableError",
    "LevelUpQuizValidationError",
    "create_level_up_quiz",
    "submit_level_up_quiz",
]
