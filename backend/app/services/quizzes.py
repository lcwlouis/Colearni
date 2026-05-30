from __future__ import annotations

import json
import re
import uuid
from hashlib import blake2b
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError

from backend.app.agents.prompts import prompt_registry
from backend.app.models.concept import ConceptNode
from backend.app.models.mastery import QuizAttempt, QuizDraft
from backend.app.schemas.mastery import (
    GradeResult,
    LevelUpCard,
    QuizAnswer,
    QuizAttemptRead,
    QuizEvaluation,
    QuizGenerationOutput,
    QuizQuestion,
)
from backend.app.schemas.types import MasteryStatus, QuizType
from backend.app.services.conversations import validate_concept_scope
from backend.app.services.learner_state import (
    format_prior_quiz_context,
    record_quiz_learning_evidence,
)
from backend.app.services.mastery import (
    PASS_THRESHOLD,
    apply_level_up_result,
    get_mastery_state,
    store_quiz_attempt,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.app.agents.llm_client import LLMClient
    from backend.app.agents.prompts.registry import PromptRegistry


class QuizGenerationError(Exception):
    pass


class QuizGradingError(Exception):
    pass


class QuizValidationError(Exception):
    pass


@runtime_checkable
class QuizGenerator(Protocol):
    async def generate(
        self,
        *,
        concept: ConceptNode,
        quiz_type: QuizType,
        prior_quiz_context: str = "",
    ) -> list[QuizQuestion]: ...


@runtime_checkable
class QuizGrader(Protocol):
    async def grade(
        self,
        *,
        concept: ConceptNode,
        questions: list[QuizQuestion],
        answers: list[QuizAnswer],
    ) -> QuizEvaluation: ...


class LLMQuizGenerator:
    def __init__(
        self,
        client: LLMClient,
        registry: PromptRegistry = prompt_registry,
    ) -> None:
        self._client = client
        self._registry = registry

    async def generate(
        self,
        *,
        concept: ConceptNode,
        quiz_type: QuizType,
        prior_quiz_context: str = "",
    ) -> list[QuizQuestion]:
        prompt = self._registry.render(
            "quiz_generation",
            {
                "concept": json.dumps(
                    {
                        "title": concept.title,
                        "concept_level": concept.concept_level,
                    },
                    indent=2,
                ),
                "mastery_check_labels": json.dumps(concept.mastery_check_labels, indent=2),
                "bloom_target": concept.bloom_level,
                "quiz_type": quiz_type,
                "prior_quiz_context": prior_quiz_context,
            },
            version=2,
        )
        raw = await self._client.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=1200,
        )
        return await self._parse_or_repair(raw, concept=concept, quiz_type=quiz_type)

    async def _parse_or_repair(
        self,
        raw: str,
        *,
        concept: ConceptNode,
        quiz_type: QuizType,
    ) -> list[QuizQuestion]:
        try:
            return _parse_generation_output(raw)
        except Exception as exc:
            repaired = await self._repair(raw, str(exc), concept=concept, quiz_type=quiz_type)
            try:
                return _parse_generation_output(repaired)
            except Exception as repair_exc:
                raise QuizGenerationError(
                    f"Quiz generation returned invalid JSON after repair: {repair_exc}"
                ) from repair_exc

    async def _repair(
        self,
        raw: str,
        error: str,
        *,
        concept: ConceptNode,
        quiz_type: QuizType,
    ) -> str:
        repair_prompt = (
            "The following quiz_generation JSON failed validation. "
            "Return only corrected JSON with 2-4 questions and unique ids.\n\n"
            f"CONCEPT: {concept.title}\n"
            f"QUIZ TYPE: {quiz_type}\n"
            f"ERROR: {error}\n\n"
            f"JSON:\n{raw}"
        )
        return await self._client.chat(
            [{"role": "user", "content": repair_prompt}],
            temperature=0.2,
            max_tokens=1200,
        )


class LLMQuizGrader:
    def __init__(
        self,
        client: LLMClient,
        registry: PromptRegistry = prompt_registry,
    ) -> None:
        self._client = client
        self._registry = registry

    async def grade(
        self,
        *,
        concept: ConceptNode,
        questions: list[QuizQuestion],
        answers: list[QuizAnswer],
    ) -> QuizEvaluation:
        prompt = self._registry.render(
            "quiz_grader",
            {
                "concept_title": concept.title,
                "bloom_target": concept.bloom_level,
                "questions": json.dumps(
                    [question.model_dump(mode="json") for question in questions],
                    indent=2,
                ),
                "answers": json.dumps(
                    [answer.model_dump(mode="json") for answer in answers],
                    indent=2,
                ),
            },
            version=1,
        )
        raw = await self._client.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1600,
        )
        return await self._parse_or_repair(raw, questions=questions)

    async def _parse_or_repair(self, raw: str, *, questions: list[QuizQuestion]) -> QuizEvaluation:
        try:
            return _parse_evaluation_output(raw, questions=questions)
        except Exception as exc:
            repaired = await self._repair(raw, str(exc), questions=questions)
            try:
                return _parse_evaluation_output(repaired, questions=questions)
            except Exception as repair_exc:
                raise QuizGradingError(
                    f"Quiz grading returned invalid JSON after repair: {repair_exc}"
                ) from repair_exc

    async def _repair(self, raw: str, error: str, *, questions: list[QuizQuestion]) -> str:
        repair_prompt = (
            "The following quiz_grader JSON failed validation. Return only corrected JSON.\n\n"
            f"QUESTION IDS: {', '.join(question.id for question in questions)}\n"
            f"ERROR: {error}\n\n"
            f"JSON:\n{raw}"
        )
        return await self._client.chat(
            [{"role": "user", "content": repair_prompt}],
            temperature=0.2,
            max_tokens=1600,
        )


async def generate_quiz_card(
    session: AsyncSession,
    generator: QuizGenerator,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    quiz_type: QuizType,
    force_new: bool = False,
) -> LevelUpCard:
    _, concept = await validate_concept_scope(
        session,
        workspace_id=workspace_id,
        trail_id=trail_id,
        concept_id=concept_id,
    )
    concept_uuid = concept.id
    await _lock_quiz_draft_generation(session, concept_id=concept_uuid, quiz_type=quiz_type)

    if force_new:
        await session.execute(
            delete(QuizDraft).where(
                QuizDraft.concept_id == concept_uuid,
                QuizDraft.quiz_type == quiz_type,
            )
        )
        await session.flush()

    draft = await session.scalar(
        select(QuizDraft).where(
            QuizDraft.concept_id == concept_uuid,
            QuizDraft.quiz_type == quiz_type,
        )
    )
    if draft is not None:
        questions = [QuizQuestion.model_validate(question) for question in draft.questions_json]
        return LevelUpCard(concept_id=concept_uuid, quiz_type=quiz_type, questions=questions)

    prior_quiz_context = await format_prior_quiz_context(
        session,
        workspace_id=workspace_id,
        concept_id=concept_uuid,
    )
    questions = await generator.generate(
        concept=concept,
        quiz_type=quiz_type,
        prior_quiz_context=prior_quiz_context,
    )
    try:
        session.add(
            QuizDraft(
                concept_id=concept_uuid,
                quiz_type=quiz_type,
                questions_json=[question.model_dump(mode="json") for question in questions],
            )
        )
        await session.commit()
    except IntegrityError:
        await session.rollback()
        draft = await session.scalar(
            select(QuizDraft).where(
                QuizDraft.concept_id == concept_uuid,
                QuizDraft.quiz_type == quiz_type,
            )
        )
        if draft is None:
            raise
        questions = [QuizQuestion.model_validate(question) for question in draft.questions_json]
    return LevelUpCard(concept_id=concept_uuid, quiz_type=quiz_type, questions=questions)


async def grade_quiz_submission(
    session: AsyncSession,
    grader: QuizGrader,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    quiz_type: QuizType,
    questions: list[QuizQuestion],
    answers: list[QuizAnswer],
) -> GradeResult:
    _, concept = await validate_concept_scope(
        session,
        workspace_id=workspace_id,
        trail_id=trail_id,
        concept_id=concept_id,
    )
    ordered_answers = _validate_submission(questions=questions, answers=answers)
    evaluation = await grader.grade(concept=concept, questions=questions, answers=ordered_answers)
    passed = evaluation.score >= PASS_THRESHOLD
    visible_feedback = evaluation.overall_feedback.strip()
    attempt_feedback = _format_feedback(questions=questions, evaluation=evaluation)

    attempt = await store_quiz_attempt(
        session,
        concept_id=concept.id,
        quiz_type=quiz_type,
        questions=questions,
        answers=ordered_answers,
        evaluator_feedback=attempt_feedback,
        passed=passed,
        score=evaluation.score,
    )
    await record_quiz_learning_evidence(
        session,
        workspace_id=workspace_id,
        concept=concept,
        attempt=attempt,
        quiz_type=quiz_type,
        questions=questions,
        evaluation=evaluation,
        passed=passed,
    )
    await session.execute(
        delete(QuizDraft).where(
            QuizDraft.concept_id == concept.id,
            QuizDraft.quiz_type == quiz_type,
        )
    )

    if quiz_type == "level_up":
        mastery_state = await apply_level_up_result(
            session,
            workspace_id=workspace_id,
            concept=concept,
            score=evaluation.score,
        )
    else:
        mastery_state = await get_mastery_state(
            session,
            workspace_id=workspace_id,
            concept=concept,
        )

    await session.commit()

    return GradeResult(
        passed=passed,
        score=evaluation.score,
        feedback=visible_feedback,
        per_question=evaluation.per_question,
        mastery_status=cast(MasteryStatus, mastery_state.status),
        attempt_id=attempt.id,
    )


async def list_quiz_attempts(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    quiz_type: QuizType | None = None,
    limit: int = 10,
) -> list[QuizAttemptRead]:
    _, concept = await validate_concept_scope(
        session,
        workspace_id=workspace_id,
        trail_id=trail_id,
        concept_id=concept_id,
    )
    limit = max(1, min(limit, 50))
    statement = (
        select(QuizAttempt)
        .where(QuizAttempt.concept_id == concept.id)
        .order_by(QuizAttempt.created_at.desc())
        .limit(limit)
    )
    if quiz_type is not None:
        statement = statement.where(QuizAttempt.quiz_type == quiz_type)
    attempts = list(await session.scalars(statement))
    return [_attempt_to_read(attempt) for attempt in attempts]


async def _lock_quiz_draft_generation(
    session: AsyncSession,
    *,
    concept_id: uuid.UUID,
    quiz_type: QuizType,
) -> None:
    """Serialize PostgreSQL draft generation so duplicate requests reuse one LLM call."""
    connection = await session.connection()
    if connection.dialect.name != "postgresql":
        return
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": _quiz_draft_lock_key(concept_id, quiz_type)},
    )


def _quiz_draft_lock_key(concept_id: uuid.UUID, quiz_type: QuizType) -> int:
    digest = blake2b(f"{concept_id}:{quiz_type}".encode("ascii"), digest_size=8).digest()
    return int.from_bytes(digest, "big") & 0x7FFFFFFFFFFFFFFF


def _attempt_to_read(attempt: QuizAttempt) -> QuizAttemptRead:
    return QuizAttemptRead(
        id=attempt.id,
        concept_id=attempt.concept_id,
        quiz_type=cast(QuizType, attempt.quiz_type),
        questions=[QuizQuestion.model_validate(question) for question in attempt.questions_json],
        answers=[QuizAnswer.model_validate(answer) for answer in attempt.answers_json],
        evaluator_feedback=attempt.evaluator_feedback,
        passed=attempt.passed,
        score=attempt.score,
        created_at=attempt.created_at,
    )


def _parse_generation_output(raw: str) -> list[QuizQuestion]:
    data = _parse_json(raw)
    return QuizGenerationOutput.model_validate(data).questions


def _parse_evaluation_output(raw: str, *, questions: list[QuizQuestion]) -> QuizEvaluation:
    data = _parse_json(raw)
    evaluation = QuizEvaluation.model_validate(data)
    expected_ids = [question.id for question in questions]
    per_question_ids = [item.question_id for item in evaluation.per_question]
    if sorted(expected_ids) != sorted(per_question_ids):
        raise ValueError("grader feedback must cover each question exactly once")
    return evaluation


def _parse_json(raw: str) -> dict:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    return json.loads(cleaned)


def _validate_submission(
    *,
    questions: list[QuizQuestion],
    answers: list[QuizAnswer],
) -> list[QuizAnswer]:
    question_by_id = {question.id: question for question in questions}
    if len(question_by_id) != len(questions):
        raise QuizValidationError("quiz questions must have unique ids")

    answer_by_id = {answer.question_id: answer for answer in answers}
    if len(answer_by_id) != len(answers):
        raise QuizValidationError("answers must reference each question at most once")

    missing = sorted(
        question_id for question_id in question_by_id if question_id not in answer_by_id
    )
    unknown = sorted(answer_id for answer_id in answer_by_id if answer_id not in question_by_id)
    if missing or unknown:
        issues: list[str] = []
        if missing:
            issues.append(f"missing answers for: {', '.join(missing)}")
        if unknown:
            issues.append(f"unknown question ids: {', '.join(unknown)}")
        raise QuizValidationError("; ".join(issues))

    return [answer_by_id[question.id] for question in questions]


def _format_feedback(*, questions: list[QuizQuestion], evaluation: QuizEvaluation) -> str:
    question_by_id = {question.id: question for question in questions}
    sections = [evaluation.overall_feedback.strip()]
    per_question_by_id = {item.question_id: item for item in evaluation.per_question}
    for question in questions:
        item = per_question_by_id.get(question.id)
        if item is None:
            # Defensive: the real grader path guarantees full coverage via
            # _parse_evaluation_output, but skip rather than crash if a custom
            # grader returns an incomplete evaluation.
            continue
        sections.append(f"{question_by_id[question.id].mastery_label}: {item.feedback.strip()}")
    return "\n\n".join(section for section in sections if section)
