from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from core.contracts import GraphLLMClient
from core.observability import SPAN_KIND_CHAIN, observation_context, set_span_kind, start_span
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
    prompt, prompt_meta = _build_flashcard_prompt(card_count=card_count, context=context)
    with observation_context(
        component="practice",
        operation="practice.flashcards.generate",
        workspace_id=workspace_id,
    ), start_span(
        "practice.flashcards.generate",
        component="practice",
        operation="practice.flashcards.generate",
        workspace_id=workspace_id,
    ) as span:
        set_span_kind(span, SPAN_KIND_CHAIN)
        if span is not None:
            span.set_attribute("concept.id", concept_id)
        payload = _parse_json(
            llm_client.generate_tutor_text(prompt=prompt, prompt_meta=prompt_meta),
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
    # Ask for extra items to compensate for dedup filtering
    overfetch = question_count + len(seen_fps) if seen_fps else question_count

    if llm_client is None:
        items = _fallback_practice_items(context=context, question_count=overfetch)
    else:
        prompt, prompt_meta = _build_practice_quiz_prompt(
            question_count=overfetch, context=context,
        )
        with observation_context(
            component="practice",
            operation="practice.quiz.generate",
            workspace_id=workspace_id,
        ), start_span(
            "practice.quiz.generate",
            component="practice",
            operation="practice.quiz.generate",
            workspace_id=workspace_id,
        ) as span:
            set_span_kind(span, SPAN_KIND_CHAIN)
            if span is not None and concept_id is not None:
                span.set_attribute("concept.id", concept_id)
            items = _generate_practice_items_with_retries(
                llm_client=llm_client,
                prompt=prompt,
                prompt_meta=prompt_meta,
                context=context,
                question_count=overfetch,
            )

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


def _generate_practice_items_with_retries(
    *,
    llm_client: GraphLLMClient,
    prompt: str,
    prompt_meta: Any | None = None,
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
    return auto_items(
        {
            "canonical_name": context["concept_name"],
            "description": context["concept_description"],
        },
        question_count,
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

    prompt, prompt_meta = _build_flashcard_prompt(card_count=request_count, context=context)
    with observation_context(
        component="practice",
        operation="practice.flashcards.generate_stateful",
        workspace_id=workspace_id,
    ), start_span(
        "practice.flashcards.generate_stateful",
        component="practice",
        operation="practice.flashcards.generate_stateful",
        workspace_id=workspace_id,
    ) as span:
        set_span_kind(span, SPAN_KIND_CHAIN)
        if span is not None and concept_id is not None:
            span.set_attribute("concept.id", concept_id)
        payload = _parse_json(
            llm_client.generate_tutor_text(prompt=prompt, prompt_meta=prompt_meta),
            "Flashcard generation response is not valid JSON.",
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


def _build_practice_quiz_prompt(*, question_count: int, context: dict[str, Any]) -> tuple[str, Any]:
    """Build the practice quiz generation prompt from asset or inline fallback."""
    try:
        return _registry.render_with_meta("practice_practice_quiz_generate_v1", {
            "question_count": str(question_count),
            "context_json": json.dumps(context, ensure_ascii=True),
            "novelty_seed": str(uuid.uuid4()),
        })
    except Exception:
        log.debug("asset render failed for practice_quiz_generate_v1, using inline fallback")
        return (
            "Return JSON practice quiz only. "
            "Schema: {\"items\":[{\"item_type\":\"short_answer|mcq\",\"prompt\":\"...\","
            "\"payload\":{...}}]}\n"
            "Include at least one short_answer and one mcq.\n"
            f"QUESTION_COUNT: {question_count}\n"
            f"CONTEXT_JSON: {json.dumps(context, ensure_ascii=True)}\n"
            f"IMPORTANT: Generate completely novel and creative questions. Random seed: {uuid.uuid4()}"
        ), None


def _build_flashcard_prompt(*, card_count: int, context: dict[str, Any]) -> tuple[str, Any]:
    """Build the flashcard generation prompt from asset or inline fallback."""
    try:
        return _registry.render_with_meta("practice_practice_flashcards_generate_v1", {
            "card_count": str(card_count),
            "context_json": json.dumps(context, ensure_ascii=True),
        })
    except Exception:
        log.debug("asset render failed for practice_flashcards_generate_v1, using inline fallback")
        return (
            "Return JSON flashcards only. "
            "Schema: {\"flashcards\":[{\"front\":\"...\",\"back\":\"...\","
            "\"hint\":\"...\"}]}\n"
            f"CARD_COUNT: {card_count}\n"
            f"CONTEXT_JSON: {json.dumps(context, ensure_ascii=True)}"
        ), None
