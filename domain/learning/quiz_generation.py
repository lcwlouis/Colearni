"""Shared quiz item generation, normalization, and validation helpers.

Used by both level-up and practice quiz flows.
"""

from __future__ import annotations

import json
import math
import random
from typing import Any


class QuizValidationError(ValueError):
    """Raised when quiz items fail validation."""


class QuizGenerationError(ValueError):
    """Raised when quiz generation fails."""


# ── Constants ─────────────────────────────────────────────────────────

DEFAULT_MIN_ITEMS = 5
DEFAULT_MAX_ITEMS = 12


# ── Item normalization ────────────────────────────────────────────────


def normalize_items(
    items: list[dict[str, Any]],
    *,
    min_items: int = DEFAULT_MIN_ITEMS,
    max_items: int = DEFAULT_MAX_ITEMS,
) -> list[dict[str, Any]]:
    if len(items) < min_items or len(items) > max_items:
        raise QuizValidationError(
            f"items must include between {min_items} and {max_items} entries"
        )
    normalized: list[dict[str, Any]] = []
    for item in items:
        item_type = str(item.get("item_type", "")).strip().lower()
        prompt = str(item.get("prompt", "")).strip()
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        if not prompt or item_type not in {"short_answer", "mcq"}:
            raise QuizValidationError("Each item requires valid item_type and prompt.")
        payload = (
            normalize_short_payload(payload)
            if item_type == "short_answer"
            else normalize_mcq_payload(payload)
        )
        normalized.append({"item_type": item_type, "prompt": prompt, "payload": payload})
    return normalized


def normalize_short_payload(payload: dict[str, Any]) -> dict[str, Any]:
    rubric = _str_list(payload.get("rubric_keywords"), required=True, field="rubric_keywords")
    critical = _str_list(
        payload.get("critical_misconception_keywords", []),
        required=False,
        field="critical_misconception_keywords",
    )
    normalized = {"rubric_keywords": rubric, "critical_misconception_keywords": critical}
    generation_context = normalize_generation_context(payload.get("_generation_context"))
    if generation_context is not None:
        normalized["_generation_context"] = generation_context
    return normalized


def normalize_mcq_payload(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("choices")
    if not isinstance(raw, list) or len(raw) < 2:
        raise QuizValidationError("mcq payload requires at least two choices.")
    choices: list[dict[str, str]] = []
    ids: list[str] = []
    for choice in raw:
        if not isinstance(choice, dict):
            raise QuizValidationError("mcq choices must be objects.")
        choice_id = str(choice.get("id", "")).strip()
        choice_text = str(choice.get("text", "")).strip()
        if not choice_id or not choice_text or choice_id in ids:
            raise QuizValidationError("mcq choices require unique id and non-empty text.")
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
        raise QuizValidationError("mcq payload has invalid correct/critical choice ids.")
    raw_explanations = payload.get("choice_explanations", {})
    if raw_explanations is None:
        raw_explanations = {}
    if not isinstance(raw_explanations, dict):
        raise QuizValidationError("mcq choice_explanations must be an object.")
    explanations: dict[str, str] = {}
    for choice in choices:
        choice_id = choice["id"]
        raw_text = raw_explanations.get(choice_id)
        provided = str(raw_text).strip() if raw_text is not None else ""
        if provided:
            explanations[choice_id] = provided
            continue
        explanations[choice_id] = default_choice_explanation(
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
    generation_context = normalize_generation_context(payload.get("_generation_context"))
    if generation_context is not None:
        normalized["_generation_context"] = generation_context
    return normalized


def _str_list(value: Any, *, required: bool, field: str) -> list[str]:
    if not isinstance(value, list):
        raise QuizValidationError(f"{field} must be a list.")
    out: list[str] = []
    for item in value:
        text_value = str(item).strip().lower()
        if not text_value:
            raise QuizValidationError(f"{field} cannot contain empty values.")
        if text_value not in out:
            out.append(text_value)
    if required and not out:
        raise QuizValidationError(f"{field} cannot be empty.")
    return out


def normalize_generation_context(raw_context: Any) -> dict[str, Any] | None:
    if raw_context is None:
        return None
    if not isinstance(raw_context, dict):
        raise QuizValidationError("_generation_context must be an object.")
    concept_name = str(raw_context.get("concept_name", "")).strip()
    if not concept_name:
        raise QuizValidationError("_generation_context.concept_name must not be empty.")
    concept_description = str(raw_context.get("concept_description", "")).strip()
    context_source = str(raw_context.get("context_source", "")).strip().lower() or "generated"
    if context_source not in {"generated", "provided"}:
        raise QuizValidationError(
            "_generation_context.context_source must be generated or provided."
        )
    context_keywords = _str_list(
        raw_context.get("context_keywords", []),
        required=False,
        field="_generation_context.context_keywords",
    )
    if not context_keywords:
        context_keywords = extract_context_keywords(
            concept_name=concept_name,
            concept_description=concept_description,
        )
    return {
        "concept_name": concept_name,
        "concept_description": concept_description,
        "context_keywords": context_keywords,
        "context_source": context_source,
    }


# ── Auto-generation ──────────────────────────────────────────────────


def validate_question_count(
    *,
    question_count: int | None,
    min_items: int,
    max_items: int,
) -> int:
    if question_count is None:
        return min_items
    if question_count < min_items or question_count > max_items:
        raise QuizValidationError(
            f"question_count must be between {min_items} and {max_items}"
        )
    return question_count


def ensure_diversity(items: list[dict[str, Any]]) -> None:
    types = {item["item_type"] for item in items}
    if types != {"short_answer", "mcq"}:
        raise QuizValidationError(
            "level-up quiz requires at least one short_answer and one mcq."
        )
    seen: set[str] = set()
    for item in items:
        normalized_prompt = " ".join(str(item["prompt"]).lower().split())
        if normalized_prompt in seen:
            raise QuizValidationError("level-up quiz prompts must be diverse.")
        seen.add(normalized_prompt)


def auto_items(
    concept: dict[str, Any],
    question_count: int,
    *,
    min_items: int = DEFAULT_MIN_ITEMS,
    max_items: int = DEFAULT_MAX_ITEMS,
) -> list[dict[str, Any]]:
    if question_count < min_items or question_count > max_items:
        raise QuizValidationError(
            f"question_count must be between {min_items} and {max_items}"
        )
    name = str(concept["canonical_name"])
    desc = str(concept["description"] or "")
    keywords = extract_context_keywords(concept_name=name, concept_description=desc)
    short_count = min(
        max(int(math.floor((question_count * 0.6) + 0.5)), 1),
        question_count - 1,
    )
    mcq_count = question_count - short_count
    desc_short = (desc[:120] + "...") if len(desc) > 120 else desc

    short_templates = [
        f"Explain what {name} means and why it matters.",
        f"What is a common mistake people make when applying {name}?",
        f"How would you teach {name} to someone new using a concrete example?",
        f"Why is {name} important in its field?",
        f"Compare {name} with a closely related concept.",
        f"What are the key properties that define {name}?",
        f"Describe a scenario where {name} would be applied.",
        f"What would go wrong if someone misunderstood {name}?",
    ]
    random.shuffle(short_templates)
    mcq_items = build_auto_mcq_items(
        name=name, desc=desc_short, keywords=keywords, count=mcq_count,
    )
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
    return short + mcq_items


def build_auto_mcq_items(
    *, name: str, desc: str, keywords: list[str], count: int,
) -> list[dict[str, Any]]:
    """Build MCQ items with concept-specific choices derived from description."""
    kw_str = ", ".join(keywords[:4]) if keywords else name
    mcq_pool = [
        {
            "prompt": f"Which statement best describes {name}?",
            "correct": desc if desc else f"{name} is defined by: {kw_str}.",
            "distractors": [
                f"{name} is unrelated to {kw_str}.",
                f"{name} only applies in trivial cases with no real impact.",
                f"{name} is the opposite of what its name suggests.",
            ],
        },
        {
            "prompt": f"Which of these is a key property of {name}?",
            "correct": f"It involves {kw_str}." if keywords else "It is central to its domain.",
            "distractors": [
                "It has no relationship to any other concepts.",
                "It can be ignored without consequence.",
                "It contradicts foundational principles.",
            ],
        },
        {
            "prompt": f"What would indicate a misunderstanding of {name}?",
            "correct": f"Claiming {name} is irrelevant to {kw_str}.",
            "distractors": [
                f"Recognizing {name} as important in its field.",
                f"Connecting {name} to related concepts.",
                f"Using {name} in a practical scenario.",
            ],
        },
        {
            "prompt": f"How does {name} relate to its domain?",
            "correct": f"It plays a foundational role involving {kw_str}.",
            "distractors": [
                "It is a deprecated idea with no modern use.",
                "It exists in isolation with no connections.",
                "It is only a theoretical abstraction with no applications.",
            ],
        },
        {
            "prompt": f"Which scenario correctly applies {name}?",
            "correct": f"Using {name} where {kw_str} is relevant.",
            "distractors": [
                f"Applying {name} to a completely unrelated problem.",
                f"Ignoring {name} when it is directly applicable.",
                f"Confusing {name} with its opposite.",
            ],
        },
        {
            "prompt": f"Why is understanding {name} valuable?",
            "correct": f"Because it underpins work involving {kw_str}.",
            "distractors": [
                "It is not valuable and can always be skipped.",
                "Only because it appears on tests, not in practice.",
                "Because everyone else talks about it, not for substance.",
            ],
        },
    ]
    random.shuffle(mcq_pool)
    items: list[dict[str, Any]] = []
    for i in range(count):
        template = mcq_pool[i % len(mcq_pool)]
        choices_raw = [
            {"text": template["correct"], "is_correct": True},
        ] + [{"text": d, "is_correct": False} for d in template["distractors"]]
        random.shuffle(choices_raw)
        choice_ids = ["a", "b", "c", "d"]
        choices = [
            {"id": choice_ids[j], "text": choices_raw[j]["text"]}
            for j in range(len(choices_raw))
        ]
        correct_id = next(
            choice_ids[j] for j in range(len(choices_raw))
            if choices_raw[j]["is_correct"]
        )
        critical_ids = [
            choice_ids[j] for j in range(len(choices_raw))
            if not choices_raw[j]["is_correct"]
            and ("opposite" in choices_raw[j]["text"].lower()
                 or "contradicts" in choices_raw[j]["text"].lower()
                 or "irrelevant" in choices_raw[j]["text"].lower())
        ]
        critical_ids = [cid for cid in critical_ids if cid != correct_id]
        if not critical_ids:
            wrong_ids = [choice_ids[j] for j in range(len(choices_raw)) if not choices_raw[j]["is_correct"]]
            critical_ids = [wrong_ids[0]] if wrong_ids else []
        items.append({
            "item_type": "mcq",
            "prompt": template["prompt"],
            "payload": {
                "choices": choices,
                "correct_choice_id": correct_id,
                "critical_choice_ids": critical_ids,
                "choice_explanations": {
                    c["id"]: ("Correct." if c["id"] == correct_id else "Incorrect.")
                    for c in choices
                },
            },
        })
    return items


# ── Helpers ───────────────────────────────────────────────────────────


def extract_context_keywords(*, concept_name: str, concept_description: str) -> list[str]:
    raw_tokens = (concept_name + " " + concept_description).lower().split()
    tokens = ["".join(ch for ch in token if ch.isalnum()) for token in raw_tokens]
    keywords = [token for token in tokens if len(token) > 2][:4]
    return keywords or ["concept"]


def attach_generation_context(
    items: list[dict[str, Any]],
    *,
    concept_name: str,
    concept_description: str,
    context_source: str,
) -> list[dict[str, Any]]:
    context_keywords = extract_context_keywords(
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


def safe_mcq_choices(raw_payload: Any) -> list[dict[str, str]] | None:
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


def default_choice_explanation(
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


def parse_json(response: str, message: str) -> dict[str, Any]:
    text_value = response.strip()
    if text_value.startswith("```"):
        text_value = "\n".join(
            line for line in text_value.splitlines() if not line.strip().startswith("```")
        ).strip()
    try:
        payload = json.loads(text_value)
    except json.JSONDecodeError as exc:
        raise QuizValidationError(message) from exc
    if not isinstance(payload, dict):
        raise QuizValidationError(message)
    return payload
