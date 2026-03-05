from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from core.contracts import GraphLLMClient
from core.observability import SPAN_KIND_CHAIN, observation_context, set_span_summary, start_span
from core.prompting import PromptRegistry
from sqlalchemy import text
from sqlalchemy.orm import Session

from domain.learning.practice_novelty import (
    fingerprint_text,
)
from domain.learning.practice_novelty import (
    load_existing_fingerprints as _load_existing_fingerprints,
)
from domain.learning.practice_novelty import (
    record_item_fingerprints as _record_item_fingerprints,
)
from domain.learning.quiz_flow import (
    QuizGradingError as _QuizGradingError,
)
from domain.learning.quiz_flow import (
    QuizNotFoundError as _QuizNotFoundError,
)
from domain.learning.quiz_flow import (
    QuizUnavailableError as _QuizUnavailableError,
)
from domain.learning.quiz_flow import (
    QuizValidationError as _QuizValidationError,
)
from domain.learning.quiz_flow import (
    create_quiz as _create_quiz,
)
from domain.learning.quiz_flow import (
    submit_quiz as _submit_quiz,
)
from domain.learning.quiz_persistence import (
    list_quizzes_with_latest_attempt as _list_quizzes_with_latest_attempt,
)
from domain.learning.quiz_persistence import (
    load_quiz_items as _load_quiz_items,
)
from domain.learning.quiz_persistence import (
    load_quiz_with_latest_attempt as _load_quiz_with_latest_attempt,
)
from domain.learning.quiz_generation import (
    QuizValidationError,
    auto_items,
    normalize_items,
)

MIN_FLASHCARDS = 3
MAX_FLASHCARDS = 12
MIN_ITEMS = 3
MAX_ITEMS = 6
ADJACENT_LIMIT = 6
MAX_EXISTING_FLASHCARDS_CONTEXT = 20
MAX_FLASHCARD_BACK_LENGTH = 200
MAX_GENERATION_ATTEMPTS = 3
RETRY_HINT = "create a new practice quiz to retry"


class PracticeNotFoundError(ValueError):
    pass


class PracticeValidationError(ValueError):
    pass


class PracticeGenerationError(ValueError):
    pass


class PracticeGradingError(ValueError):
    pass


class PracticeUnavailableError(RuntimeError):
    pass


log = logging.getLogger("domain.learning.practice")
_registry = PromptRegistry()


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
    context["existing_flashcards"] = _load_existing_flashcard_content(
        session, workspace_id=workspace_id, concept_id=concept_id,
    )
    prompt, prompt_meta, sys_prompt = _build_flashcard_prompt(card_count=card_count, context=context)
    with observation_context(
        component="practice",
        operation="practice.flashcards.generate",
        workspace_id=workspace_id,
    ), start_span(
        "practice.flashcards.generate",
        kind=SPAN_KIND_CHAIN,
        component="practice",
        operation="practice.flashcards.generate",
        workspace_id=workspace_id,
    ) as span:
        if span is not None:
            span.set_attribute("concept.id", concept_id)
            set_span_summary(span, input_summary=context["concept_name"])
        payload = _parse_json(
            llm_client.generate_tutor_text(prompt=prompt, prompt_meta=prompt_meta, system_prompt=sys_prompt),
            "Flashcard generation response is not valid JSON.",
        )
        if span is not None:
            _cards_tmp = payload.get("flashcards")
            set_span_summary(
                span,
                output_summary=f"{len(_cards_tmp) if isinstance(_cards_tmp, list) else 0} flashcards",
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
    if not (MIN_ITEMS <= question_count <= MAX_ITEMS):
        raise PracticeValidationError(f"question_count must be between {MIN_ITEMS} and {MAX_ITEMS}")

    # Slice 11: Load seen quiz fingerprints for novelty dedup
    seen_fps = _load_existing_fingerprints(
        session,
        workspace_id=workspace_id,
        user_id=user_id,
        concept_id=concept_id,
        item_type="quiz",
    )

    context = _context(session, workspace_id=workspace_id, concept_id=concept_id)
    # Ask for extra items to compensate for dedup filtering, while keeping
    # generation count within practice quiz bounds.
    overfetch = question_count + len(seen_fps) if seen_fps else question_count
    generation_count = max(MIN_ITEMS, min(MAX_ITEMS, overfetch))

    if llm_client is None:
        items = _fallback_practice_items(context=context, question_count=generation_count)
    else:
        prompt, prompt_meta, sys_prompt = _build_practice_quiz_prompt(
            question_count=generation_count, context=context,
        )
        with observation_context(
            component="practice",
            operation="practice.quiz.generate",
            workspace_id=workspace_id,
        ), start_span(
            "practice.quiz.generate",
            kind=SPAN_KIND_CHAIN,
            component="practice",
            operation="practice.quiz.generate",
            workspace_id=workspace_id,
        ) as span:
            if span is not None and concept_id is not None:
                span.set_attribute("concept.id", concept_id)
                set_span_summary(span, input_summary=context["concept_name"])
            items = _generate_practice_items_with_retries(
                llm_client=llm_client,
                prompt=prompt,
                prompt_meta=prompt_meta,
                system_prompt=sys_prompt,
                context=context,
                question_count=generation_count,
            )
            if span is not None:
                set_span_summary(span, output_summary=f"{len(items)} items")

    # Slice 11: Filter out already-seen quiz items
    if seen_fps:
        novel_items: list[dict[str, Any]] = []
        for item in items:
            fp = fingerprint_text(str(item.get("prompt", "")))
            if fp not in seen_fps:
                novel_items.append(item)
        if len(novel_items) < MIN_ITEMS:
            novel_items = items[:question_count]  # fallback to unfiltered if too few
        items = novel_items[:question_count]

    # Record new fingerprints
    new_fps = [fingerprint_text(str(item.get("prompt", ""))) for item in items]
    try:
        _record_item_fingerprints(
            session,
            workspace_id=workspace_id,
            user_id=user_id,
            concept_id=concept_id,
            item_type="quiz",
            fingerprints=new_fps,
        )
    except Exception:
        if callable(getattr(session, "rollback", None)):
            session.rollback()  # Reset failed transaction state

    try:
        return _create_quiz(
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
    except _QuizNotFoundError as exc:
        raise PracticeNotFoundError(str(exc)) from exc
    except _QuizValidationError as exc:
        raise PracticeValidationError(str(exc)) from exc
    except _QuizUnavailableError as exc:
        raise PracticeUnavailableError(str(exc)) from exc


def submit_practice_quiz(
    session: Session,
    *,
    quiz_id: int,
    workspace_id: int,
    user_id: int,
    answers: list[dict[str, Any]],
    llm_client: GraphLLMClient | None,
) -> dict[str, Any]:
    try:
        return _submit_quiz(
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
    except _QuizNotFoundError as exc:
        raise PracticeNotFoundError(str(exc)) from exc
    except _QuizValidationError as exc:
        raise PracticeValidationError(str(exc)) from exc
    except _QuizGradingError as exc:
        raise PracticeGradingError(str(exc)) from exc
    except _QuizUnavailableError as exc:
        raise PracticeUnavailableError(str(exc)) from exc


def list_practice_quizzes(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    concept_id: int | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    if concept_id is not None and concept_id <= 0:
        raise PracticeValidationError("concept_id must be positive when provided.")

    rows = _list_quizzes_with_latest_attempt(
        session,
        workspace_id=workspace_id,
        user_id=user_id,
        quiz_type="practice",
        concept_id=concept_id,
        limit=limit,
    )
    return {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "concept_id": concept_id,
        "quizzes": [_serialize_quiz_history_row(row) for row in rows],
    }


def get_practice_quiz(
    session: Session,
    *,
    quiz_id: int,
    workspace_id: int,
    user_id: int,
) -> dict[str, Any]:
    row = _load_quiz_with_latest_attempt(
        session,
        workspace_id=workspace_id,
        user_id=user_id,
        quiz_id=quiz_id,
        quiz_type="practice",
    )
    if row is None:
        raise PracticeNotFoundError("Practice quiz not found.")

    items = _load_quiz_items(session, quiz_id=quiz_id)
    payload = _serialize_quiz_history_row(row)
    payload["items"] = [
        {
            "item_id": int(item["item_id"]),
            "position": int(item["position"]),
            "item_type": str(item["item_type"]),
            "prompt": str(item["prompt"]),
            "choices": [
                {"id": str(choice.get("id", "")), "text": str(choice.get("text", ""))}
                for choice in (
                    item["payload"].get("choices", [])
                    if isinstance(item.get("payload"), dict)
                    else []
                )
                if isinstance(choice, dict)
                and str(choice.get("id", "")).strip()
                and str(choice.get("text", "")).strip()
            ]
            or None,
        }
        for item in items
    ]
    return payload


def _generate_practice_items_with_retries(
    *,
    llm_client: GraphLLMClient,
    prompt: str,
    prompt_meta: Any | None = None,
    system_prompt: str | None = None,
    context: dict[str, Any],
    question_count: int,
) -> list[dict[str, Any]]:
    last_error: Exception | None = None
    retry_prompt = prompt
    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        try:
            with observation_context(retry_attempt=attempt):
                try:
                    llm_text = llm_client.generate_tutor_text(
                        prompt=retry_prompt, prompt_meta=prompt_meta,
                        system_prompt=system_prompt,
                    )
                except Exception:
                    return _fallback_practice_items(
                        context=context,
                        question_count=question_count,
                    )
                payload = _parse_json(
                    llm_text,
                    "Practice quiz generation response is not valid JSON.",
                )
            raw_items = _coerce_generated_items(payload.get("items"))
            items = normalize_items(
                raw_items,
                min_items=MIN_ITEMS,
                max_items=MAX_ITEMS,
            )
            if {item["item_type"] for item in items} != {"short_answer", "mcq"}:
                raise PracticeGenerationError(
                    "Practice quiz requires at least one short_answer and one mcq."
                )
            return items
        except PracticeGenerationError as exc:
            last_error = exc
        except (PracticeValidationError, QuizValidationError) as exc:
            last_error = exc
        if attempt < MAX_GENERATION_ATTEMPTS:
            retry_prompt = (
                f"{prompt}\n"
                f"RETRY_ATTEMPT: {attempt + 1}/{MAX_GENERATION_ATTEMPTS}\n"
                f"PREVIOUS_OUTPUT_INVALID_REASON: {last_error}\n"
                "Regenerate from scratch and return only valid JSON."
            )

    if last_error is None:
        return _fallback_practice_items(context=context, question_count=question_count)
    return _fallback_practice_items(context=context, question_count=question_count)


def _fallback_practice_items(
    *,
    context: dict[str, Any],
    question_count: int,
) -> list[dict[str, Any]]:
    safe_count = max(MIN_ITEMS, min(MAX_ITEMS, question_count))
    return auto_items(
        {
            "canonical_name": context["concept_name"],
            "description": context["concept_description"],
        },
        safe_count,
        min_items=MIN_ITEMS,
        max_items=MAX_ITEMS,
    )


def _coerce_generated_items(raw_items: Any) -> Any:
    if not isinstance(raw_items, list):
        return raw_items
    out: list[Any] = []
    for item in raw_items:
        if not isinstance(item, dict):
            out.append(item)
            continue
        normalized_item = dict(item)
        item_type = str(normalized_item.get("item_type", "")).strip().lower()
        payload = normalized_item.get("payload")
        if item_type == "short_answer" and isinstance(payload, dict):
            normalized_payload = dict(payload)
            normalized_payload["rubric_keywords"] = _coerce_keyword_list(
                normalized_payload.get("rubric_keywords"),
                default=["concept"],
            )
            normalized_payload["critical_misconception_keywords"] = _coerce_keyword_list(
                normalized_payload.get("critical_misconception_keywords", []),
                default=[],
            )
            normalized_item["payload"] = normalized_payload
        out.append(normalized_item)
    return out


def _serialize_quiz_history_row(row: Any) -> dict[str, Any]:
    grading = row["grading"] if isinstance(row.get("grading"), dict) else {}
    latest_attempt = None
    if row.get("attempt_id") is not None and row.get("graded_at") is not None:
        latest_attempt = {
            "attempt_id": int(row["attempt_id"]),
            "score": float(row["score"] or 0.0),
            "passed": bool(row["passed"]),
            "critical_misconception": bool(grading.get("critical_misconception", False)),
            "overall_feedback": str(grading.get("overall_feedback", "")).strip() or "(no feedback)",
            "graded_at": row["graded_at"],
        }
    return {
        "quiz_id": int(row["quiz_id"]),
        "workspace_id": int(row["workspace_id"]),
        "user_id": int(row["user_id"]),
        "concept_id": int(row["concept_id"]) if row.get("concept_id") is not None else None,
        "concept_name": str(row["concept_name"]) if row.get("concept_name") else None,
        "status": str(row["status"]),
        "item_count": int(row.get("item_count") or 0),
        "created_at": row["created_at"],
        "latest_attempt": latest_attempt,
    }


def _coerce_keyword_list(value: Any, *, default: list[str]) -> list[str]:
    if isinstance(value, list):
        raw_values = value
    elif isinstance(value, str):
        if "," in value:
            raw_values = value.split(",")
        else:
            raw_values = value.split()
    elif value is None:
        raw_values = []
    else:
        raw_values = [value]

    out: list[str] = []
    for raw in raw_values:
        token = str(raw).strip().lower()
        if token and token not in out:
            out.append(token)
    return out or list(default)


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


def _load_existing_flashcard_content(
    session: Session,
    *,
    workspace_id: int,
    concept_id: int,
) -> list[dict[str, str]]:
    """Load up to MAX_EXISTING_FLASHCARDS_CONTEXT recent flashcards for LLM context."""
    rows = session.execute(
        text(
            """
            SELECT front, back
            FROM practice_flashcard_bank
            WHERE workspace_id = :workspace_id
              AND concept_id = :concept_id
            ORDER BY id DESC
            LIMIT :limit
            """
        ),
        {
            "workspace_id": workspace_id,
            "concept_id": concept_id,
            "limit": MAX_EXISTING_FLASHCARDS_CONTEXT,
        },
    ).mappings().all()
    result: list[dict[str, str]] = []
    for row in rows:
        back = str(row["back"] or "")
        if len(back) > MAX_FLASHCARD_BACK_LENGTH:
            back = back[:MAX_FLASHCARD_BACK_LENGTH] + "…"
        result.append({"front": str(row["front"] or ""), "back": back})
    return result


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


# ── Slice 10: Stateful flashcard generation + rating ──────────────────


def generate_stateful_flashcards(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    concept_id: int,
    card_count: int,
    llm_client: GraphLLMClient | None,
) -> dict[str, Any]:
    """Generate flashcards, persist to bank, return with run_id.

    Unlike the basic ``generate_practice_flashcards``, this function:
    * Creates a ``practice_generation_runs`` record.
    * Inserts cards into ``practice_flashcard_bank`` with fingerprints.
    * Initialises ``practice_flashcard_progress`` rows for the user.
    * Skips cards whose fingerprints already exist (novelty, Slice 11).
    * Returns ``StatefulFlashcardsResponse``-shaped dict.
    """
    if llm_client is None:
        raise PracticeUnavailableError("LLM generation client is unavailable.")
    if not (MIN_FLASHCARDS <= card_count <= MAX_FLASHCARDS):
        raise PracticeValidationError(
            f"card_count must be between {MIN_FLASHCARDS} and {MAX_FLASHCARDS}"
        )

    context = _context(session, workspace_id=workspace_id, concept_id=concept_id)
    context["existing_flashcards"] = _load_existing_flashcard_content(
        session, workspace_id=workspace_id, concept_id=concept_id,
    )

    # Load already-seen fingerprints (Slice 11 – novelty)
    existing_fps = _load_existing_fingerprints(
        session,
        workspace_id=workspace_id,
        user_id=user_id,
        concept_id=concept_id,
        item_type="flashcard",
    )

    # Ask for extra cards to compensate for dedup
    request_count = card_count + min(len(existing_fps), card_count)

    prompt, prompt_meta, sys_prompt = _build_flashcard_prompt(card_count=request_count, context=context)
    with observation_context(
        component="practice",
        operation="practice.flashcards.generate_stateful",
        workspace_id=workspace_id,
    ), start_span(
        "practice.flashcards.generate_stateful",
        kind=SPAN_KIND_CHAIN,
        component="practice",
        operation="practice.flashcards.generate_stateful",
        workspace_id=workspace_id,
    ) as span:
        if span is not None and concept_id is not None:
            span.set_attribute("concept.id", concept_id)
            set_span_summary(span, input_summary=context["concept_name"])
        payload = _parse_json(
            llm_client.generate_tutor_text(prompt=prompt, prompt_meta=prompt_meta, system_prompt=sys_prompt),
            "Flashcard generation response is not valid JSON.",
        )
        if span is not None:
            _cards_tmp = payload.get("flashcards")
            set_span_summary(
                span,
                output_summary=f"{len(_cards_tmp) if isinstance(_cards_tmp, list) else 0} flashcards",
            )
        raw_cards = payload.get("flashcards")
        if not isinstance(raw_cards, list) or not raw_cards:
            raise PracticeGenerationError("Flashcard response must contain flashcard entries.")

    # Create generation run
    run_row = (
        session.execute(
            text(
                """
                INSERT INTO practice_generation_runs
                    (workspace_id, user_id, concept_id, generation_type, item_count)
                VALUES (:workspace_id, :user_id, :concept_id, 'flashcard', 0)
                RETURNING id, run_id
                """
            ),
            {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "concept_id": concept_id,
            },
        )
        .mappings()
        .one()
    )
    run_pk = int(run_row["id"])
    run_uuid = str(run_row["run_id"])

    # Normalize + dedup + persist
    persisted: list[dict[str, Any]] = []
    new_fps: list[str] = []
    for card in raw_cards:
        if not isinstance(card, dict):
            continue
        front = str(card.get("front", "")).strip()
        back = str(card.get("back", "")).strip()
        hint = str(card.get("hint", "")).strip()
        if not front or not back or not hint:
            continue
        fp = fingerprint_text(f"{front}|{back}")
        if fp in existing_fps:
            continue  # novelty skip
        existing_fps.add(fp)  # prevent within-batch dupes
        new_fps.append(fp)

        bank_row = (
            session.execute(
                text(
                    """
                    INSERT INTO practice_flashcard_bank
                        (run_id, workspace_id, concept_id, front, back, hint, fingerprint)
                    VALUES (:run_id, :workspace_id, :concept_id, :front, :back, :hint, :fingerprint)
                    RETURNING id, flashcard_id
                    """
                ),
                {
                    "run_id": run_pk,
                    "workspace_id": workspace_id,
                    "concept_id": concept_id,
                    "front": front,
                    "back": back,
                    "hint": hint,
                    "fingerprint": fp,
                },
            )
            .mappings()
            .one()
        )

        # Initialize progress row
        session.execute(
            text(
                """
                INSERT INTO practice_flashcard_progress (flashcard_id, user_id)
                VALUES (:flashcard_id, :user_id)
                ON CONFLICT (flashcard_id, user_id) DO NOTHING
                """
            ),
            {"flashcard_id": int(bank_row["id"]), "user_id": user_id},
        )

        persisted.append({
            "flashcard_id": str(bank_row["flashcard_id"]),
            "front": front,
            "back": back,
            "hint": hint,
            "self_rating": None,
            "passed": False,
        })
        if len(persisted) >= card_count:
            break

    # Record fingerprints for novelty engine
    _record_item_fingerprints(
        session,
        workspace_id=workspace_id,
        user_id=user_id,
        concept_id=concept_id,
        item_type="flashcard",
        fingerprints=new_fps,
    )

    # Check exhaustion
    has_more = len(persisted) >= card_count
    exhausted_reason: str | None = None
    if not persisted:
        exhausted_reason = "All available flashcards have been studied."
        has_more = False

    # Update run record
    session.execute(
        text(
            """
            UPDATE practice_generation_runs
            SET item_count = :count, has_more = :has_more, exhausted_reason = :exhausted_reason
            WHERE id = :run_id
            """
        ),
        {
            "count": len(persisted),
            "has_more": has_more,
            "exhausted_reason": exhausted_reason,
            "run_id": run_pk,
        },
    )
    session.commit()

    return {
        "workspace_id": workspace_id,
        "concept_id": concept_id,
        "concept_name": context["concept_name"],
        "run_id": run_uuid,
        "flashcards": persisted,
        "has_more": has_more,
        "exhausted_reason": exhausted_reason,
    }


def rate_flashcard(
    session: Session,
    *,
    flashcard_id: str,
    user_id: int,
    self_rating: str,
) -> dict[str, Any]:
    """Record a self-rating for a flashcard and compute passed status.

    Rating intervals (simplified SM-2 variant):
    * again → not passed, due immediately
    * hard  → not passed, due in shorter interval
    * good  → passed
    * easy  → passed
    """
    if self_rating not in ("again", "hard", "good", "easy"):
        raise PracticeValidationError(
            "self_rating must be one of: again, hard, good, easy"
        )

    passed = self_rating in ("good", "easy")

    # Look up the flashcard by UUID
    bank_row = session.execute(
        text(
            """
            SELECT id FROM practice_flashcard_bank
            WHERE flashcard_id = :flashcard_id
            LIMIT 1
            """
        ),
        {"flashcard_id": flashcard_id},
    ).mappings().first()
    if bank_row is None:
        raise PracticeNotFoundError("Flashcard not found.")

    session.execute(
        text(
            """
            INSERT INTO practice_flashcard_progress (flashcard_id, user_id, self_rating, passed, updated_at)
            VALUES (:flashcard_id, :user_id, :self_rating, :passed, now())
            ON CONFLICT (flashcard_id, user_id)
            DO UPDATE SET self_rating = :self_rating, passed = :passed, updated_at = now()
            """
        ),
        {
            "flashcard_id": int(bank_row["id"]),
            "user_id": user_id,
            "self_rating": self_rating,
            "passed": passed,
        },
    )

    # Update spaced repetition schedule
    from domain.learning.spaced_repetition import update_flashcard_schedule

    try:
        schedule = update_flashcard_schedule(
            session,
            flashcard_id=int(bank_row["id"]),
            user_id=user_id,
            self_rating=self_rating,
        )
    except Exception:
        if callable(getattr(session, "rollback", None)):
            session.rollback()
        schedule = {"interval_days": 1.0, "due_at": None}
    session.commit()

    return {
        "flashcard_id": flashcard_id,
        "self_rating": self_rating,
        "passed": passed,
        "interval_days": schedule.get("interval_days", 1.0),
        "due_at": schedule.get("due_at"),
    }


def list_flashcard_runs(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    concept_id: int | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    if concept_id is not None and concept_id <= 0:
        raise PracticeValidationError("concept_id must be positive when provided.")

    safe_limit = max(1, min(limit, 100))
    params: dict[str, Any] = {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "limit": safe_limit,
    }
    concept_filter = ""
    if concept_id is not None:
        concept_filter = "AND r.concept_id = :concept_id"
        params["concept_id"] = concept_id

    rows = (
        session.execute(
            text(
                f"""
                SELECT
                    r.run_id,
                    r.workspace_id,
                    r.user_id,
                    r.concept_id,
                    cc.canonical_name AS concept_name,
                    r.item_count,
                    r.has_more,
                    r.exhausted_reason,
                    r.created_at
                FROM practice_generation_runs r
                JOIN concepts_canon cc
                  ON cc.id = r.concept_id
                 AND cc.workspace_id = r.workspace_id
                WHERE r.workspace_id = :workspace_id
                  AND r.user_id = :user_id
                  AND r.generation_type = 'flashcard'
                  {concept_filter}
                ORDER BY r.id DESC
                LIMIT :limit
                """
            ),
            params,
        )
        .mappings()
        .all()
    )

    return {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "concept_id": concept_id,
        "runs": [_serialize_flashcard_run_row(row) for row in rows],
    }


def get_flashcard_run(
    session: Session,
    *,
    run_id: str,
    workspace_id: int,
    user_id: int,
) -> dict[str, Any]:
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError as exc:
        raise PracticeValidationError("run_id must be a valid UUID.") from exc

    run_row = (
        session.execute(
            text(
                """
                SELECT
                    r.id,
                    r.run_id,
                    r.workspace_id,
                    r.user_id,
                    r.concept_id,
                    cc.canonical_name AS concept_name,
                    r.item_count,
                    r.has_more,
                    r.exhausted_reason,
                    r.created_at
                FROM practice_generation_runs r
                JOIN concepts_canon cc
                  ON cc.id = r.concept_id
                 AND cc.workspace_id = r.workspace_id
                WHERE r.run_id = :run_id
                  AND r.workspace_id = :workspace_id
                  AND r.user_id = :user_id
                  AND r.generation_type = 'flashcard'
                LIMIT 1
                """
            ),
            {
                "run_id": run_uuid,
                "workspace_id": workspace_id,
                "user_id": user_id,
            },
        )
        .mappings()
        .first()
    )
    if run_row is None:
        raise PracticeNotFoundError("Flashcard run not found.")

    cards = (
        session.execute(
            text(
                """
                SELECT
                    b.flashcard_id,
                    b.front,
                    b.back,
                    b.hint,
                    p.self_rating,
                    p.passed,
                    p.due_at,
                    p.interval_days
                FROM practice_flashcard_bank b
                LEFT JOIN practice_flashcard_progress p
                  ON p.flashcard_id = b.id
                 AND p.user_id = :user_id
                WHERE b.run_id = :run_pk
                ORDER BY b.id ASC
                """
            ),
            {
                "run_pk": int(run_row["id"]),
                "user_id": user_id,
            },
        )
        .mappings()
        .all()
    )

    return {
        **_serialize_flashcard_run_row(run_row),
        "flashcards": [
            {
                "flashcard_id": str(card["flashcard_id"]),
                "front": str(card["front"]),
                "back": str(card["back"]),
                "hint": str(card["hint"]),
                "self_rating": str(card["self_rating"]) if card["self_rating"] else None,
                "passed": bool(card["passed"]) if card["passed"] is not None else False,
                "due_at": card["due_at"],
                "interval_days": float(card["interval_days"])
                if card["interval_days"] is not None
                else None,
            }
            for card in cards
        ],
    }


def _serialize_flashcard_run_row(row: Any) -> dict[str, Any]:
    return {
        "run_id": str(row["run_id"]),
        "workspace_id": int(row["workspace_id"]),
        "user_id": int(row["user_id"]),
        "concept_id": int(row["concept_id"]),
        "concept_name": str(row["concept_name"]),
        "item_count": int(row.get("item_count") or 0),
        "has_more": bool(row["has_more"]),
        "exhausted_reason": str(row["exhausted_reason"]) if row.get("exhausted_reason") else None,
        "created_at": row["created_at"],
    }


def _build_practice_quiz_prompt(*, question_count: int, context: dict[str, Any]) -> tuple[str, Any, str | None]:
    """Build the practice quiz generation prompt from asset or inline fallback."""
    try:
        prompt, meta = _registry.render_with_meta("practice_practice_quiz_generate_v1", {
            "question_count": str(question_count),
            "context_json": json.dumps(context, ensure_ascii=True),
            "novelty_seed": str(uuid.uuid4()),
        })
        return prompt, meta, None
    except Exception:
        log.debug("asset render failed for practice_quiz_generate_v1, using inline fallback")
        system = (
            "Return JSON practice quiz only. "
            "Schema: {\"items\":[{\"item_type\":\"short_answer|mcq\",\"prompt\":\"...\","
            "\"payload\":{...}}]}\n"
            "Include at least one short_answer and one mcq."
        )
        user = (
            f"QUESTION_COUNT: {question_count}\n"
            f"CONTEXT_JSON: {json.dumps(context, ensure_ascii=True)}\n"
            f"IMPORTANT: Generate completely novel and creative questions. Random seed: {uuid.uuid4()}"
        )
        return user, None, system


def _build_flashcard_prompt(*, card_count: int, context: dict[str, Any]) -> tuple[str, Any, str | None]:
    """Build the flashcard generation prompt from asset or inline fallback."""
    existing = context.get("existing_flashcards", [])
    if existing:
        lines = [f"- Q: {c['front']}  A: {c['back']}" for c in existing]
        existing_text = "\n".join(lines)
    else:
        existing_text = "None yet."

    try:
        prompt, meta = _registry.render_with_meta("practice_practice_flashcards_generate_v1", {
            "card_count": str(card_count),
            "context_json": json.dumps(context, ensure_ascii=True),
            "existing_flashcards_text": existing_text,
        })
        return prompt, meta, None
    except Exception:
        log.debug("asset render failed for practice_flashcards_generate_v1, using inline fallback")
        dedup_block = ""
        if existing:
            dedup_block = (
                "\nThe following flashcards already exist for this concept. "
                "Do NOT repeat or closely paraphrase any of them. "
                "Generate entirely new questions covering different aspects.\n"
                f"{existing_text}\n"
            )
        system = (
            "Return JSON flashcards only. "
            "Schema: {\"flashcards\":[{\"front\":\"...\",\"back\":\"...\","
            "\"hint\":\"...\"}]}"
            f"{dedup_block}"
        )
        user = (
            f"CARD_COUNT: {card_count}\n"
            f"CONTEXT_JSON: {json.dumps(context, ensure_ascii=True)}"
        )
        return user, None, system
