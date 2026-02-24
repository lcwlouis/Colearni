from __future__ import annotations

import json
from typing import Any

from core.contracts import GraphLLMClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from domain.learning import level_up

MIN_FLASHCARDS = 3
MAX_FLASHCARDS = 12
MIN_ITEMS = 3
MAX_ITEMS = 6
ADJACENT_LIMIT = 6
RETRY_HINT = "create a new practice quiz to retry"

PracticeNotFoundError = level_up.LevelUpQuizNotFoundError
PracticeValidationError = level_up.LevelUpQuizValidationError
PracticeGenerationError = level_up.LevelUpQuizValidationError
PracticeGradingError = level_up.LevelUpQuizGradingError
PracticeUnavailableError = level_up.LevelUpQuizUnavailableError


def generate_practice_flashcards(
    session: Session,
    *,
    workspace_id: int,
    concept_id: int,
    card_count: int,
    llm_client: GraphLLMClient | None,
) -> dict[str, Any]:
    if llm_client is None:
        raise PracticeUnavailableError("LLM generation client is unavailable.")
    if not (MIN_FLASHCARDS <= card_count <= MAX_FLASHCARDS):
        raise PracticeValidationError(
            f"card_count must be between {MIN_FLASHCARDS} and {MAX_FLASHCARDS}"
        )

    context = _context(session, workspace_id=workspace_id, concept_id=concept_id)
    prompt = (
        "Return JSON flashcards only. "
        "Schema: {\"flashcards\":[{\"front\":\"...\",\"back\":\"...\","
        "\"hint\":\"...\"}]}\n"
        f"CARD_COUNT: {card_count}\n"
        f"CONTEXT_JSON: {json.dumps(context, ensure_ascii=True)}"
    )
    payload = _parse_json(
        llm_client.generate_tutor_text(prompt=prompt),
        "Flashcard generation response is not valid JSON.",
    )
    cards = payload.get("flashcards")
    if not isinstance(cards, list) or len(cards) != card_count:
        raise PracticeGenerationError("Flashcard response must contain exactly card_count entries.")

    normalized: list[dict[str, str]] = []
    for card in cards:
        if not isinstance(card, dict):
            raise PracticeGenerationError("Each flashcard must be an object.")
        front, back, hint = [str(card.get(key, "")).strip() for key in ("front", "back", "hint")]
        if not front or not back or not hint:
            raise PracticeGenerationError("Each flashcard requires front, back, and hint.")
        normalized.append({"front": front, "back": back, "hint": hint})

    return {
        "workspace_id": workspace_id,
        "concept_id": concept_id,
        "concept_name": context["concept_name"],
        "flashcards": normalized,
    }


def create_practice_quiz(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    concept_id: int,
    session_id: int | None,
    question_count: int,
    llm_client: GraphLLMClient | None,
) -> dict[str, Any]:
    if llm_client is None:
        raise PracticeUnavailableError("LLM generation client is unavailable.")
    if not (MIN_ITEMS <= question_count <= MAX_ITEMS):
        raise PracticeValidationError(f"question_count must be between {MIN_ITEMS} and {MAX_ITEMS}")

    context = _context(session, workspace_id=workspace_id, concept_id=concept_id)
    prompt = (
        "Return JSON practice quiz only. "
        "Schema: {\"items\":[{\"item_type\":\"short_answer|mcq\",\"prompt\":\"...\","
        "\"payload\":{...}}]}\n"
        "Include at least one short_answer and one mcq.\n"
        f"QUESTION_COUNT: {question_count}\n"
        f"CONTEXT_JSON: {json.dumps(context, ensure_ascii=True)}"
    )
    payload = _parse_json(
        llm_client.generate_tutor_text(prompt=prompt),
        "Practice quiz generation response is not valid JSON.",
    )
    items = level_up._normalize_items(
        payload.get("items"),
        min_items=MIN_ITEMS,
        max_items=MAX_ITEMS,
    )
    if {item["item_type"] for item in items} != {"short_answer", "mcq"}:
        raise PracticeGenerationError(
            "Practice quiz requires at least one short_answer and one mcq."
        )

    return level_up.create_level_up_quiz(
        session,
        workspace_id=workspace_id,
        user_id=user_id,
        concept_id=concept_id,
        session_id=session_id,
        question_count=question_count,
        items=items,
        quiz_type="practice",
        min_items=MIN_ITEMS,
        max_items=MAX_ITEMS,
        context_source="generated",
    )


def submit_practice_quiz(
    session: Session,
    *,
    quiz_id: int,
    workspace_id: int,
    user_id: int,
    answers: list[dict[str, Any]],
    llm_client: GraphLLMClient | None,
) -> dict[str, Any]:
    return level_up.submit_level_up_quiz(
        session,
        quiz_id=quiz_id,
        workspace_id=workspace_id,
        user_id=user_id,
        answers=answers,
        llm_client=llm_client,
        quiz_type="practice",
        update_mastery=False,
        retry_hint=RETRY_HINT,
    )


def _context(session: Session, *, workspace_id: int, concept_id: int) -> dict[str, Any]:
    concept = session.execute(
        text(
            """
            SELECT canonical_name, description
            FROM concepts_canon
            WHERE id = :concept_id AND workspace_id = :workspace_id AND is_active = TRUE
            LIMIT 1
            """
        ),
        {"concept_id": concept_id, "workspace_id": workspace_id},
    ).mappings().first()
    if concept is None:
        raise PracticeNotFoundError("Concept not found in workspace.")

    rows = session.execute(
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
            LIMIT :limit
            """
        ),
        {"workspace_id": workspace_id, "concept_id": concept_id, "limit": ADJACENT_LIMIT},
    ).mappings().all()
    concept_name = str(concept["canonical_name"])

    return {
        "concept_name": concept_name,
        "concept_description": str(concept["description"] or ""),
        "adjacent_concepts": [
            str(row["tgt_name"]) if str(row["src_name"]) == concept_name else str(row["src_name"])
            for row in rows
        ],
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
        raise PracticeGenerationError(message) from exc
    if not isinstance(payload, dict):
        raise PracticeGenerationError(message)
    return payload
