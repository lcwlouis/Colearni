"""Shared quiz grading helpers for both level-up and practice flows."""

from __future__ import annotations

import json
import logging
from typing import Any

from core.prompting import PromptRegistry

log = logging.getLogger("domain.learning.quiz_grading")
_registry = PromptRegistry()


class QuizGradingError(ValueError):
    """Raised when grading response parsing fails."""


def validate_answers(items: list[dict[str, Any]], answers: list[dict[str, Any]]) -> dict[int, str]:
    from domain.learning.quiz_generation import QuizValidationError

    if not answers:
        raise QuizValidationError("answers must not be empty.")
    mapped: dict[int, str] = {}
    for answer in answers:
        item_id = answer.get("item_id")
        text_value = str(answer.get("answer", "")).strip()
        if not isinstance(item_id, int) or not text_value or item_id in mapped:
            raise QuizValidationError(
                "answers must include unique item_id with non-empty answer."
            )
        mapped[item_id] = text_value

    item_ids = {item["item_id"] for item in items}
    if set(mapped.keys()) != item_ids:
        raise QuizValidationError("answers must include every quiz item exactly once.")

    for item in items:
        if item["item_type"] != "mcq":
            continue
        choices = {choice["id"] for choice in item["payload"]["choices"]}
        if mapped[item["item_id"]] not in choices:
            raise QuizValidationError("mcq answers must match a valid choice id.")
    return mapped


def grade_short_items_without_llm(
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


def grading_prompt(items: list[dict[str, Any]], answer_map: dict[int, str]) -> str:
    ids = [item["item_id"] for item in items]
    submission = [{**item, "answer": answer_map[item["item_id"]]} for item in items]
    ids_json = json.dumps(ids, ensure_ascii=True)
    submission_json = json.dumps(submission, ensure_ascii=True)
    try:
        return _registry.render("assessment_levelup_grade_v1", {
            "item_ids_json": ids_json,
            "quiz_submission_json": submission_json,
        })
    except Exception:
        log.debug("asset render failed for levelup_grade_v1, using inline fallback")
        return _grading_prompt_inline(ids_json, submission_json)


def _grading_prompt_inline(ids_json: str, submission_json: str) -> str:
    """Inline fallback for grading prompt."""
    return (
        "Return JSON only with keys items and overall_feedback. "
        "Use payload._generation_context as the canonical generation-time context. "
        "Each items entry must include item_id, score(0..1), "
        "critical_misconception(bool), feedback.\n"
        f"ITEM_IDS_JSON: {ids_json}\n"
        f"QUIZ_SUBMISSION_JSON: {submission_json}"
    )


def parse_grading(response: str, item_ids: list[int]) -> dict[str, Any]:
    text_value = response.strip()
    if text_value.startswith("```"):
        text_value = "\n".join(
            line for line in text_value.splitlines() if not line.strip().startswith("```")
        ).strip()
    try:
        payload = json.loads(text_value)
    except json.JSONDecodeError as exc:
        raise QuizGradingError("Grading response is not valid JSON.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise QuizGradingError("Grading response missing items list.")
    if (
        not isinstance(payload.get("overall_feedback"), str)
        or not payload["overall_feedback"].strip()
    ):
        raise QuizGradingError("Grading response missing overall_feedback.")

    by_id: dict[int, dict[str, Any]] = {}
    for item in payload["items"]:
        if not isinstance(item, dict) or not isinstance(item.get("item_id"), int):
            raise QuizGradingError("Invalid grading item payload.")
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
            raise QuizGradingError("Invalid grading score/critical/feedback values.")
        by_id[int(item["item_id"])] = {
            "item_id": int(item["item_id"]),
            "score": float(score),
            "critical_misconception": critical,
            "feedback": feedback.strip(),
        }

    if set(by_id.keys()) != set(item_ids):
        raise QuizGradingError("grading items must cover every quiz item exactly once.")

    return {
        "items": [by_id[item_id] for item_id in item_ids],
        "overall_feedback": payload["overall_feedback"].strip(),
    }


def grade_mcq_items(
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


def compose_feedback_items(
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
        score = coerce_score(graded_item.get("score"))
        critical = bool(graded_item.get("critical_misconception", False))
        result = derive_item_result(item_type=item_type, score=score, critical=critical)
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


def coerce_score(value: Any) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        return None
    score = float(value)
    return max(0.0, min(1.0, score))


def derive_item_result(*, item_type: str, score: float | None, critical: bool) -> str:
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


def build_overall_feedback(
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
