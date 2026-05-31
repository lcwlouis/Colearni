from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from hashlib import blake2b
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.prompts import prompt_registry
from backend.app.models.concept import ConceptNode
from backend.app.models.conversation import ConversationTurn
from backend.app.models.learner_state import LearnerState, QuizAttemptSummary
from backend.app.models.mastery import QuizAttempt
from backend.app.schemas.mastery import (
    LearnerStateObservation,
    PerQuestionEvaluation,
    QuizEvaluation,
    QuizQuestion,
)
from backend.app.schemas.types import QuizType
from backend.app.services.mastery import PASS_THRESHOLD

if TYPE_CHECKING:
    from backend.app.agents.llm_client import LLMClient
    from backend.app.agents.prompts.registry import PromptRegistry

_SCORE_STRONG = 0.85
_SCORE_PARTIAL = 0.4
_MAX_CONTEXT_SUMMARIES = 5
_OBSERVER_TURN_SNIPPET_CHARS = 800


async def get_learner_state(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    concept_id: uuid.UUID,
) -> LearnerState | None:
    return await session.scalar(
        select(LearnerState).where(
            LearnerState.workspace_id == workspace_id,
            LearnerState.concept_id == concept_id,
        )
    )


async def record_quiz_learning_evidence(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    concept: ConceptNode,
    attempt: QuizAttempt,
    quiz_type: QuizType,
    questions: list[QuizQuestion],
    evaluation: QuizEvaluation,
    passed: bool,
) -> tuple[QuizAttemptSummary, LearnerState]:
    """Create an immutable attempt summary and update mutable learner state.

    The attempt remains immutable. LearnerState is the current, supersedable view:
    a later passed level-up can clear repair targets created by an older failed one.
    """
    existing_summary = await session.scalar(
        select(QuizAttemptSummary).where(QuizAttemptSummary.quiz_attempt_id == attempt.id)
    )
    if existing_summary is not None:
        state = await _upsert_learner_state(
            session,
            workspace_id=workspace_id,
            concept=concept,
            attempt=attempt,
            summary=existing_summary,
            passed=passed,
            quiz_type=quiz_type,
        )
        return existing_summary, state

    per_question = {item.question_id: item for item in evaluation.per_question}
    strengths = _label_evidence(
        questions=questions,
        per_question=per_question,
        keep=lambda score: score >= PASS_THRESHOLD,
    )
    gaps = _label_evidence(
        questions=questions,
        per_question=per_question,
        keep=lambda score: score < PASS_THRESHOLD,
    )
    fingerprints = _question_fingerprints(questions=questions, per_question=per_question)
    summary_text = _summary_text(
        quiz_type=quiz_type,
        score=evaluation.score,
        passed=passed,
        strengths=strengths,
        gaps=gaps,
    )

    summary = QuizAttemptSummary(
        workspace_id=workspace_id,
        concept_id=concept.id,
        quiz_attempt_id=attempt.id,
        quiz_type=quiz_type,
        summary_text=summary_text,
        strengths_json=strengths,
        gaps_json=gaps,
        question_fingerprints_json=fingerprints,
    )
    session.add(summary)
    await session.flush()

    state = await _upsert_learner_state(
        session,
        workspace_id=workspace_id,
        concept=concept,
        attempt=attempt,
        summary=summary,
        passed=passed,
        quiz_type=quiz_type,
    )
    return summary, state


async def format_prior_quiz_context(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    concept_id: uuid.UUID,
    limit: int = _MAX_CONTEXT_SUMMARIES,
) -> str:
    """Return bounded prior quiz context for generation without answers/keys."""
    rows = list(
        await session.scalars(
            select(QuizAttemptSummary)
            .where(
                QuizAttemptSummary.workspace_id == workspace_id,
                QuizAttemptSummary.concept_id == concept_id,
            )
            .order_by(QuizAttemptSummary.created_at.desc())
            .limit(max(1, min(limit, _MAX_CONTEXT_SUMMARIES)))
        )
    )
    if not rows:
        return "No prior quiz attempts for this concept."

    blocks: list[str] = []
    for index, row in enumerate(rows, start=1):
        fingerprints = row.question_fingerprints_json or []
        prompts = []
        for item in fingerprints[:4]:
            label = item.get("mastery_label") or "unknown_label"
            score_band = item.get("score_band") or "unknown"
            prompt_excerpt = item.get("prompt_excerpt") or ""
            prompts.append(f"  - {label} ({score_band}): {prompt_excerpt}")
        prompt_text = "\n".join(prompts) if prompts else "  - no question fingerprints recorded"
        blocks.append(
            f"Attempt {index} ({row.quiz_type}): {row.summary_text}\n"
            f"Question fingerprints to avoid repeating verbatim:\n{prompt_text}"
        )
    return "\n\n".join(blocks)


def _label_evidence(
    *,
    questions: list[QuizQuestion],
    per_question: dict[str, PerQuestionEvaluation],
    keep,
) -> list[dict]:
    evidence: list[dict] = []
    for question in questions:
        item = per_question.get(question.id)
        if item is None:
            # No grade for this question: treat as ungraded (consistent with
            # _question_fingerprints) rather than defaulting to a passing 1.0,
            # which would wrongly count it as a strength and hide repair targets.
            continue
        score = item.score
        if keep(score):
            evidence.append(
                {
                    "mastery_label": question.mastery_label,
                    "score": round(score, 2),
                    "question_id": question.id,
                    "prompt_excerpt": _excerpt(question.prompt),
                }
            )
    return evidence


def _question_fingerprints(
    *,
    questions: list[QuizQuestion],
    per_question: dict[str, PerQuestionEvaluation],
) -> list[dict]:
    fingerprints: list[dict] = []
    for question in questions:
        item = per_question.get(question.id)
        score = item.score if item is not None else None
        fingerprints.append(
            {
                "hash": _prompt_hash(question.prompt),
                "mastery_label": question.mastery_label,
                "type": question.type,
                "difficulty": question.difficulty,
                "score_band": _score_band(score),
                "prompt_excerpt": _excerpt(question.prompt),
            }
        )
    return fingerprints


async def _upsert_learner_state(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    concept: ConceptNode,
    attempt: QuizAttempt,
    summary: QuizAttemptSummary,
    passed: bool,
    quiz_type: QuizType,
) -> LearnerState:
    state = await get_learner_state(
        session,
        workspace_id=workspace_id,
        concept_id=concept.id,
    )
    strengths = list(summary.strengths_json or [])
    gaps = list(summary.gaps_json or [])
    misconceptions = [item for item in gaps if float(item.get("score", 1.0)) <= _SCORE_PARTIAL]
    repair_targets = [] if quiz_type == "level_up" and passed else gaps
    summary_text = _state_summary_text(
        concept_title=concept.title,
        quiz_type=quiz_type,
        score=attempt.score,
        passed=passed,
        strengths=strengths,
        repair_targets=repair_targets,
    )

    now = datetime.now(UTC)
    if state is None:
        state = LearnerState(
            workspace_id=workspace_id,
            concept_id=concept.id,
            summary_text=summary_text,
            strengths_json=strengths,
            misconceptions_json=misconceptions,
            next_repair_targets_json=repair_targets,
            last_quiz_attempt_id=attempt.id,
            updated_at=now,
        )
        session.add(state)
    else:
        state.summary_text = summary_text
        state.strengths_json = strengths
        state.misconceptions_json = misconceptions
        state.next_repair_targets_json = repair_targets
        state.last_quiz_attempt_id = attempt.id
        state.updated_at = now
    await session.flush()
    return state


def _summary_text(
    *,
    quiz_type: QuizType,
    score: float,
    passed: bool,
    strengths: list[dict],
    gaps: list[dict],
) -> str:
    outcome = "passed" if passed else "needs review"
    strengths_text = _labels(strengths) or "none yet"
    gaps_text = _labels(gaps) or "none"
    return (
        f"{quiz_type.replace('_', ' ')} scored {score:.0%} ({outcome}). "
        f"Strengths: {strengths_text}. Gaps/repair targets: {gaps_text}."
    )


def _state_summary_text(
    *,
    concept_title: str,
    quiz_type: QuizType,
    score: float,
    passed: bool,
    strengths: list[dict],
    repair_targets: list[dict],
) -> str:
    strengths_text = _labels(strengths) or "no stable strengths recorded yet"
    if quiz_type == "level_up" and passed:
        return (
            f"Current learner state for {concept_title}: latest level-up passed at {score:.0%}. "
            f"Demonstrated strengths: {strengths_text}. No current repair targets from quizzes."
        )
    repair_text = _labels(repair_targets) or "none"
    return (
        f"Current learner state for {concept_title}: latest {quiz_type.replace('_', ' ')} "
        f"scored {score:.0%}. Demonstrated strengths: {strengths_text}. "
        f"Next repair targets: {repair_text}."
    )


def _labels(items: list[dict]) -> str:
    return ", ".join(str(item.get("mastery_label", "")).replace("_", " ") for item in items if item)


def _score_band(score: float | None) -> str:
    if score is None:
        return "ungraded"
    if score >= _SCORE_STRONG:
        return "answered strongly"
    if score >= PASS_THRESHOLD:
        return "answered correctly"
    if score >= _SCORE_PARTIAL:
        return "partial/needs repair"
    return "missed"


def _prompt_hash(prompt: str) -> str:
    normalized = " ".join(prompt.lower().split())
    return blake2b(normalized.encode("utf-8"), digest_size=8).hexdigest()


def _excerpt(text: str, *, max_chars: int = 180) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return f"{cleaned[: max_chars - 1].rstrip()}…"


# ---------------------------------------------------------------------------
# Tutor-driven learner-state updates (Phase 13.5d / Phase 13 mutable state).
#
# Quiz grading is the immutable-evidence trigger; this is the conversational
# trigger. It runs sparingly (at most once every N learner turns), AFTER the
# tutor turn's `done` event so it never adds visible latency, and the observer
# itself decides whether an update is warranted (most turns are no-ops).
# ---------------------------------------------------------------------------


@runtime_checkable
class LearnerStateObserver(Protocol):
    async def observe(
        self,
        *,
        concept_title: str,
        current_state: str,
        recent_turns: str,
    ) -> LearnerStateObservation: ...


class LLMLearnerStateObserver:
    """LLM-backed observer that decides whether to update mutable learner state."""

    def __init__(self, client: LLMClient, registry: PromptRegistry = prompt_registry) -> None:
        self._client = client
        self._registry = registry

    async def observe(
        self,
        *,
        concept_title: str,
        current_state: str,
        recent_turns: str,
    ) -> LearnerStateObservation:
        prompt = self._registry.render(
            "learner_state_update",
            {
                "concept_title": concept_title,
                "current_state": current_state,
                "recent_turns": recent_turns,
            },
            version=1,
        )
        raw = await self._client.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=400,
            response_format={"type": "json_object"},
            thinking=False,
        )
        return _parse_observation(raw)


async def maybe_update_learner_state_from_chat(
    session: AsyncSession,
    observer: LearnerStateObserver,
    *,
    workspace_id: uuid.UUID,
    concept: ConceptNode,
    conversation_id: uuid.UUID,
    interval: int,
    recent_visible_turns_limit: int,
) -> LearnerState | None:
    """Maybe update mutable learner state from the recent tutor conversation.

    Gated so it costs zero LLM calls on most turns: it only consults the observer
    once every ``interval`` visible learner (user) turns. When ``interval`` <= 0
    the tutor-driven path is disabled entirely. Even when consulted, the observer
    returns ``should_update=False`` for ordinary turns and nothing is written.

    Idempotent-by-design: re-running on the same turn count re-derives the same
    state; the immutable quiz attempts and their summaries are never touched.
    """
    if interval <= 0:
        return None

    user_turn_count = (
        await session.scalar(
            select(func.count())
            .select_from(ConversationTurn)
            .where(
                ConversationTurn.conversation_id == conversation_id,
                ConversationTurn.kind == "visible",
                ConversationTurn.role == "user",
            )
        )
        or 0
    )
    if user_turn_count == 0 or user_turn_count % interval != 0:
        return None

    recent_turns = list(
        await session.scalars(
            select(ConversationTurn)
            .where(
                ConversationTurn.conversation_id == conversation_id,
                ConversationTurn.kind == "visible",
            )
            .order_by(ConversationTurn.turn_index.desc())
            .limit(recent_visible_turns_limit)
        )
    )
    if not recent_turns:
        return None
    recent_turns.reverse()

    state = await get_learner_state(session, workspace_id=workspace_id, concept_id=concept.id)
    observation = await observer.observe(
        concept_title=concept.title,
        current_state=_format_state_for_observer(state),
        recent_turns=_format_observer_turns(recent_turns),
    )
    if not observation.should_update:
        return None
    return await _apply_tutor_observation(
        session,
        workspace_id=workspace_id,
        concept=concept,
        state=state,
        observation=observation,
    )


async def _apply_tutor_observation(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    concept: ConceptNode,
    state: LearnerState | None,
    observation: LearnerStateObservation,
) -> LearnerState:
    resolved = {_normalize_label(label) for label in observation.resolved}
    resolved.discard("")

    existing_strengths = list(state.strengths_json) if state else []
    existing_misconceptions = list(state.misconceptions_json) if state else []
    existing_repair = list(state.next_repair_targets_json) if state else []

    new_strengths = _label_items(observation.strengths)
    new_misconceptions = _label_items(observation.misconceptions)

    strengths = _merge_items(existing_strengths, new_strengths)
    misconceptions = _drop_labels(
        _merge_items(existing_misconceptions, new_misconceptions), resolved
    )
    # A revealed misconception is also a repair target; a resolved one is removed.
    repair_targets = _drop_labels(_merge_items(existing_repair, new_misconceptions), resolved)

    summary_text = observation.summary.strip() or _derived_tutor_summary(
        concept_title=concept.title, strengths=strengths, repair_targets=repair_targets
    )

    now = datetime.now(UTC)
    if state is None:
        state = LearnerState(
            workspace_id=workspace_id,
            concept_id=concept.id,
            summary_text=summary_text,
            strengths_json=strengths,
            misconceptions_json=misconceptions,
            next_repair_targets_json=repair_targets,
            last_quiz_attempt_id=None,
            updated_at=now,
        )
        session.add(state)
    else:
        # Preserve last_quiz_attempt_id: the tutor refines the mutable view but
        # does not own the immutable quiz linkage.
        state.summary_text = summary_text
        state.strengths_json = strengths
        state.misconceptions_json = misconceptions
        state.next_repair_targets_json = repair_targets
        state.updated_at = now
    await session.flush()
    return state


def _parse_observation(raw: str) -> LearnerStateObservation:
    """Parse the observer JSON, failing closed (no update) on any error."""
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    try:
        data = json.loads(cleaned)
    except Exception:
        return LearnerStateObservation()
    try:
        return LearnerStateObservation.model_validate(data)
    except Exception:
        return LearnerStateObservation()


def _normalize_label(label: str) -> str:
    return " ".join(str(label).split()).strip().lower()


def _label_items(labels: list[str]) -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()
    for label in labels:
        norm = _normalize_label(label)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        items.append({"mastery_label": norm, "source": "tutor"})
    return items


def _merge_items(existing: list[dict], new: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen: set[str] = set()
    for item in (*existing, *new):
        label = _normalize_label(item.get("mastery_label", ""))
        if not label or label in seen:
            continue
        seen.add(label)
        merged.append(item)
    return merged


def _drop_labels(items: list[dict], labels: set[str]) -> list[dict]:
    return [item for item in items if _normalize_label(item.get("mastery_label", "")) not in labels]


def _derived_tutor_summary(
    *, concept_title: str, strengths: list[dict], repair_targets: list[dict]
) -> str:
    strengths_text = _labels(strengths) or "none yet"
    repair_text = _labels(repair_targets) or "none"
    return (
        f"Current learner state for {concept_title} (from tutoring): "
        f"demonstrated strengths: {strengths_text}; repair targets: {repair_text}."
    )


def _format_state_for_observer(state: LearnerState | None) -> str:
    if state is None:
        return "No learner-state record yet for this concept."
    return (
        f"Summary: {state.summary_text}\n"
        f"Strengths: {_labels(state.strengths_json) or 'none recorded'}\n"
        f"Misconceptions: {_labels(state.misconceptions_json) or 'none recorded'}\n"
        f"Repair targets: {_labels(state.next_repair_targets_json) or 'none recorded'}"
    )


def _format_observer_turns(turns: list[ConversationTurn]) -> str:
    lines: list[str] = []
    for turn in turns:
        role = "Learner" if turn.role == "user" else "Tutor"
        lines.append(f"{role}: {_excerpt(turn.content, max_chars=_OBSERVER_TURN_SNIPPET_CHARS)}")
    return "\n".join(lines)
