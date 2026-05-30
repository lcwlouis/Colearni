from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.agents.llm_client import LLMClient
from backend.app.models.base import Base
from backend.app.models.concept import ConceptNode
from backend.app.models.learner_state import LearnerState, QuizAttemptSummary
from backend.app.models.mastery import MasteryRecord, QuizAttempt, QuizDraft
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.schemas.mastery import (
    PerQuestionEvaluation,
    QuizAnswer,
    QuizEvaluation,
    QuizQuestion,
)
from backend.app.services.quizzes import (
    LLMQuizGenerator,
    LLMQuizGrader,
    QuizValidationError,
    generate_quiz_card,
    grade_quiz_submission,
    list_quiz_attempts,
)


class FakeLLMClient:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.calls: list[list[dict]] = []

    async def chat(self, messages: list[dict], **_: object) -> str:
        self.calls.append(messages)
        return self.responses.pop(0)


class FakeQuizGenerator:
    def __init__(self, questions: list[QuizQuestion] | None = None):
        self.questions = questions or [
            QuizQuestion(
                id="q1",
                type="short_answer",
                prompt="Explain derivatives in your own words.",
                mastery_label="explain_derivative",
                difficulty="standard",
            ),
            QuizQuestion(
                id="q2",
                type="long_answer",
                prompt="Apply a derivative to a small example.",
                mastery_label="apply_derivative",
                difficulty="challenge",
            ),
        ]
        self.calls: list[tuple[str, str, str]] = []

    async def generate(
        self,
        *,
        concept: ConceptNode,
        quiz_type: str,
        prior_quiz_context: str = "",
    ) -> list[QuizQuestion]:
        self.calls.append((concept.title, quiz_type, prior_quiz_context))
        return self.questions


class FakeQuizGrader:
    def __init__(self, score: float, feedback: str = "Overall feedback"):
        self.score = score
        self.feedback = feedback

    async def grade(
        self,
        *,
        concept: ConceptNode,
        questions: list[QuizQuestion],
        answers: list[QuizAnswer],
    ) -> QuizEvaluation:
        return QuizEvaluation(
            score=self.score,
            passed=self.score >= 0.7,
            per_question=[
                PerQuestionEvaluation(
                    question_id=question.id,
                    score=self.score,
                    feedback=f"Feedback for {question.id}",
                )
                for question in questions
            ],
            overall_feedback=self.feedback,
        )


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


async def _seed_concept(session):
    workspace = Workspace(name="Quiz Workspace")
    session.add(workspace)
    await session.flush()
    trail = Trail(
        workspace_id=workspace.id,
        title="Calculus",
        topic="Calculus",
        goal="Understand derivatives",
        target_depth="apply",
    )
    session.add(trail)
    await session.flush()
    concept = ConceptNode(
        trail_id=trail.id,
        slug="derivatives",
        title="Derivatives",
        node_type="concept",
        concept_level="topic",
        difficulty="beginner",
        bloom_level="apply",
        mastery_check_labels=["explain_derivative", "apply_derivative"],
        metadata_json={},
    )
    session.add(concept)
    await session.commit()
    return workspace, trail, concept


async def test_generate_quiz_card_uses_mastery_labels(session):
    workspace, trail, concept = await _seed_concept(session)
    generator = FakeQuizGenerator()

    card = await generate_quiz_card(
        session,
        generator,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        quiz_type="level_up",
    )

    assert card.quiz_type == "level_up"
    assert card.concept_id == concept.id
    assert [question.mastery_label for question in card.questions] == [
        "explain_derivative",
        "apply_derivative",
    ]
    assert generator.calls == [
        ("Derivatives", "level_up", "No prior quiz attempts for this concept.")
    ]


async def test_generate_quiz_card_reuses_existing_draft(session):
    workspace, trail, concept = await _seed_concept(session)
    generator = FakeQuizGenerator()

    first = await generate_quiz_card(
        session,
        generator,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        quiz_type="level_up",
    )
    second = await generate_quiz_card(
        session,
        generator,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        quiz_type="level_up",
    )

    assert second.questions == first.questions
    assert generator.calls == [
        ("Derivatives", "level_up", "No prior quiz attempts for this concept.")
    ]


async def test_duplicate_draft_recovery_does_not_access_expired_concept(monkeypatch):
    concept_id = __import__("uuid").uuid4()
    question = QuizQuestion(
        id="q1",
        type="short_answer",
        prompt="Explain derivatives.",
        mastery_label="explain_derivative",
        difficulty="standard",
    )
    second_question = QuizQuestion(
        id="q2",
        type="long_answer",
        prompt="Apply derivatives.",
        mastery_label="apply_derivative",
        difficulty="challenge",
    )

    class ExpiringConcept:
        title = "Derivatives"
        concept_level = "topic"
        difficulty = "beginner"
        bloom_level = "apply"
        mastery_check_labels = ["explain_derivative"]
        metadata_json = {}
        _id_reads = 0

        @property
        def id(self):
            self._id_reads += 1
            if self._id_reads > 1:
                raise AssertionError("concept.id was accessed after rollback")
            return concept_id

    class FakeConnection:
        class dialect:
            name = "sqlite"

    class FakeSession:
        def __init__(self):
            self.scalar_calls = 0
            self.rolled_back = False

        async def connection(self):
            return FakeConnection()

        async def scalar(self, _statement):
            self.scalar_calls += 1
            if self.scalar_calls == 1:
                return None
            return type(
                "Draft",
                (),
                {
                    "questions_json": [
                        question.model_dump(mode="json"),
                        second_question.model_dump(mode="json"),
                    ]
                },
            )()

        async def scalars(self, _statement):
            return []

        def add(self, _value):
            return None

        async def commit(self):
            raise IntegrityError("insert", {}, Exception("duplicate"))

        async def rollback(self):
            self.rolled_back = True

    async def fake_validate_concept_scope(*_args, **_kwargs):
        return None, ExpiringConcept()

    monkeypatch.setattr(
        "backend.app.services.quizzes.validate_concept_scope",
        fake_validate_concept_scope,
    )
    fake_session = FakeSession()

    card = await generate_quiz_card(
        cast(AsyncSession, fake_session),
        FakeQuizGenerator([question, second_question]),
        workspace_id=__import__("uuid").uuid4(),
        trail_id=__import__("uuid").uuid4(),
        concept_id=concept_id,
        quiz_type="level_up",
    )

    assert fake_session.rolled_back is True
    assert card.concept_id == concept_id
    assert card.questions == [question, second_question]


async def test_force_new_quiz_card_replaces_draft(session):
    workspace, trail, concept = await _seed_concept(session)
    first_generator = FakeQuizGenerator()
    second_generator = FakeQuizGenerator(
        [
            QuizQuestion(
                id="q3",
                type="multiple_choice",
                prompt="Compare derivatives and finite differences.",
                mastery_label="compare_derivative",
                difficulty="light",
                options=["Both describe change", "Both are always constant", "Neither uses rates"],
            ),
            QuizQuestion(
                id="q4",
                type="short_answer",
                prompt="Explain derivative notation.",
                mastery_label="explain_notation",
                difficulty="standard",
            ),
        ]
    )

    await generate_quiz_card(
        session,
        first_generator,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        quiz_type="level_up",
    )
    fresh = await generate_quiz_card(
        session,
        second_generator,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        quiz_type="level_up",
        force_new=True,
    )

    assert [question.id for question in fresh.questions] == ["q3", "q4"]
    assert first_generator.calls == [
        ("Derivatives", "level_up", "No prior quiz attempts for this concept.")
    ]
    assert second_generator.calls == [
        ("Derivatives", "level_up", "No prior quiz attempts for this concept.")
    ]


async def test_legacy_question_types_are_normalized():
    question = QuizQuestion.model_validate(
        {
            "id": "q1",
            "type": "explain",
            "prompt": "Explain it.",
            "mastery_label": "explain_derivative",
        }
    )

    assert question.type == "long_answer"


async def test_multi_select_question_requires_options():
    with pytest.raises(ValueError):
        QuizQuestion.model_validate(
            {
                "id": "q1",
                "type": "multi_select",
                "prompt": "Select all prime numbers.",
                "mastery_label": "identify_primes",
            }
        )


async def test_ordering_question_requires_options():
    with pytest.raises(ValueError):
        QuizQuestion.model_validate(
            {
                "id": "q1",
                "type": "ordering",
                "prompt": "Order these steps from top to bottom.",
                "mastery_label": "order_steps",
            }
        )


async def test_cloze_question_rejects_options():
    with pytest.raises(ValueError):
        QuizQuestion.model_validate(
            {
                "id": "q1",
                "type": "cloze",
                "prompt": "The capital of France is ____.",
                "mastery_label": "recall_capital",
                "options": ["Paris", "Lyon"],
            }
        )


async def test_new_question_types_parse_successfully():
    multi_select = QuizQuestion.model_validate(
        {
            "id": "q1",
            "type": "multi_select",
            "prompt": "Select all prime numbers.",
            "mastery_label": "identify_primes",
            "options": ["2", "3", "4", "9"],
        }
    )
    ordering = QuizQuestion.model_validate(
        {
            "id": "q2",
            "type": "ordering",
            "prompt": "Order these steps from top to bottom.",
            "mastery_label": "order_steps",
            "options": ["Compile", "Plan", "Run"],
        }
    )
    cloze = QuizQuestion.model_validate(
        {
            "id": "q3",
            "type": "cloze",
            "prompt": "The capital of France is ____.",
            "mastery_label": "recall_capital",
        }
    )

    assert multi_select.type == "multi_select"
    assert multi_select.options == ["2", "3", "4", "9"]
    assert ordering.type == "ordering"
    assert ordering.options == ["Compile", "Plan", "Run"]
    assert cloze.type == "cloze"
    assert cloze.options is None


async def test_level_up_pass_updates_mastered_and_stores_attempt(session):
    workspace, trail, concept = await _seed_concept(session)
    questions = FakeQuizGenerator().questions
    await generate_quiz_card(
        session,
        FakeQuizGenerator(questions),
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        quiz_type="level_up",
    )
    result = await grade_quiz_submission(
        session,
        FakeQuizGrader(0.85),
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        quiz_type="level_up",
        questions=questions,
        answers=[
            QuizAnswer(question_id="q1", answer="A derivative measures change."),
            QuizAnswer(question_id="q2", answer="The derivative of x^2 at x=3 is 6."),
        ],
    )

    assert result.passed is True
    assert result.mastery_status == "mastered"
    assert result.feedback == "Overall feedback"
    record = await session.scalar(
        select(MasteryRecord).where(MasteryRecord.concept_id == concept.id)
    )
    assert record is not None
    assert record.status == "mastered"
    attempt = await session.scalar(select(QuizAttempt).where(QuizAttempt.id == result.attempt_id))
    assert attempt is not None
    assert attempt.quiz_type == "level_up"
    assert "explain_derivative: Feedback for q1" in attempt.evaluator_feedback
    attempt_summary = await session.scalar(
        select(QuizAttemptSummary).where(QuizAttemptSummary.quiz_attempt_id == attempt.id)
    )
    assert attempt_summary is not None
    assert "answered strongly" in str(attempt_summary.question_fingerprints_json)
    learner_state = await session.scalar(
        select(LearnerState).where(LearnerState.concept_id == concept.id)
    )
    assert learner_state is not None
    assert learner_state.next_repair_targets_json == []
    assert "latest level-up passed" in learner_state.summary_text
    draft = await session.scalar(select(QuizDraft).where(QuizDraft.concept_id == concept.id))
    assert draft is None


async def test_level_up_fail_updates_needs_review(session):
    workspace, trail, concept = await _seed_concept(session)
    questions = FakeQuizGenerator().questions
    result = await grade_quiz_submission(
        session,
        FakeQuizGrader(0.5),
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        quiz_type="level_up",
        questions=questions,
        answers=[
            QuizAnswer(question_id="q1", answer="Unsure."),
            QuizAnswer(question_id="q2", answer="Not sure."),
        ],
    )

    assert result.passed is False
    assert result.mastery_status == "needs_review"
    record = await session.scalar(
        select(MasteryRecord).where(MasteryRecord.concept_id == concept.id)
    )
    assert record is not None
    assert record.status == "needs_review"
    learner_state = await session.scalar(
        select(LearnerState).where(LearnerState.concept_id == concept.id)
    )
    assert learner_state is not None
    assert [item["mastery_label"] for item in learner_state.next_repair_targets_json] == [
        "explain_derivative",
        "apply_derivative",
    ]


async def test_later_pass_supersedes_old_failed_quiz_bias(session):
    workspace, trail, concept = await _seed_concept(session)
    questions = FakeQuizGenerator().questions

    await grade_quiz_submission(
        session,
        FakeQuizGrader(0.45),
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        quiz_type="level_up",
        questions=questions,
        answers=[
            QuizAnswer(question_id="q1", answer="Unsure."),
            QuizAnswer(question_id="q2", answer="Not sure."),
        ],
    )
    failed_state = await session.scalar(
        select(LearnerState).where(LearnerState.concept_id == concept.id)
    )
    assert failed_state is not None
    assert failed_state.next_repair_targets_json

    await grade_quiz_submission(
        session,
        FakeQuizGrader(0.95),
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        quiz_type="level_up",
        questions=questions,
        answers=[
            QuizAnswer(question_id="q1", answer="A derivative measures change."),
            QuizAnswer(question_id="q2", answer="Use the derivative to find the rate."),
        ],
    )

    passed_state = await session.scalar(
        select(LearnerState).where(LearnerState.concept_id == concept.id)
    )
    assert passed_state is not None
    assert passed_state.next_repair_targets_json == []
    assert "latest level-up passed" in passed_state.summary_text


class PartialQuizGrader:
    """Grader that omits a per-question entry, simulating an under-returning model."""

    def __init__(self, score: float, graded_only: set[str]):
        self.score = score
        self.graded_only = graded_only

    async def grade(self, *, concept, questions, answers):
        return QuizEvaluation(
            score=self.score,
            passed=self.score >= 0.7,
            per_question=[
                PerQuestionEvaluation(
                    question_id=question.id,
                    score=self.score,
                    feedback=f"Feedback for {question.id}",
                )
                for question in questions
                if question.id in self.graded_only
            ],
            overall_feedback="Partial feedback",
        )


async def test_missing_per_question_grade_is_not_counted_as_strength(session):
    workspace, trail, concept = await _seed_concept(session)
    questions = FakeQuizGenerator().questions  # q1 explain, q2 apply

    # q1 is graded strongly; q2 has no per-question entry at all.
    await grade_quiz_submission(
        session,
        PartialQuizGrader(0.95, graded_only={"q1"}),
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        quiz_type="practice",
        questions=questions,
        answers=[
            QuizAnswer(question_id="q1", answer="A derivative measures change."),
            QuizAnswer(question_id="q2", answer="Some attempt."),
        ],
    )

    summary = await session.scalar(select(QuizAttemptSummary))
    assert summary is not None
    strength_labels = [item["mastery_label"] for item in summary.strengths_json]
    # Only the graded question counts as a strength; the ungraded one is skipped,
    # never silently treated as a passing 1.0.
    assert strength_labels == ["explain_derivative"]
    gap_labels = [item["mastery_label"] for item in summary.gaps_json]
    assert "apply_derivative" not in gap_labels


async def test_prior_quiz_context_is_passed_to_generation_without_answers_or_feedback(session):
    workspace, trail, concept = await _seed_concept(session)
    questions = FakeQuizGenerator().questions
    await grade_quiz_submission(
        session,
        FakeQuizGrader(0.9, feedback="Detailed grading feedback"),
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        quiz_type="level_up",
        questions=questions,
        answers=[
            QuizAnswer(question_id="q1", answer="A derivative measures change."),
            QuizAnswer(question_id="q2", answer="The derivative of x^2 is 2x."),
        ],
    )

    generator = FakeQuizGenerator()
    await generate_quiz_card(
        session,
        generator,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        quiz_type="level_up",
    )

    prior_context = generator.calls[0][2]
    assert "explain_derivative" in prior_context
    assert "answered strongly" in prior_context
    assert "Explain derivatives in your own words" in prior_context
    assert "A derivative measures change" not in prior_context
    assert "Detailed grading feedback" not in prior_context


async def test_list_quiz_attempts_returns_newest_first_and_filters_type(session):
    workspace, trail, concept = await _seed_concept(session)
    questions = FakeQuizGenerator().questions
    first = await grade_quiz_submission(
        session,
        FakeQuizGrader(0.9),
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        quiz_type="practice",
        questions=questions,
        answers=[
            QuizAnswer(question_id="q1", answer="Practice answer 1"),
            QuizAnswer(question_id="q2", answer="Practice answer 2"),
        ],
    )
    second = await grade_quiz_submission(
        session,
        FakeQuizGrader(0.8),
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        quiz_type="level_up",
        questions=questions,
        answers=[
            QuizAnswer(question_id="q1", answer="Level answer 1"),
            QuizAnswer(question_id="q2", answer="Level answer 2"),
        ],
    )
    first_record = await session.get(QuizAttempt, first.attempt_id)
    second_record = await session.get(QuizAttempt, second.attempt_id)
    assert first_record is not None
    assert second_record is not None
    first_record.created_at = datetime.now(UTC) - timedelta(minutes=5)
    second_record.created_at = datetime.now(UTC)
    await session.commit()

    attempts = await list_quiz_attempts(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
    )
    level_attempts = await list_quiz_attempts(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        quiz_type="level_up",
    )

    assert [attempt.id for attempt in attempts] == [second.attempt_id, first.attempt_id]
    assert [attempt.quiz_type for attempt in level_attempts] == ["level_up"]
    assert level_attempts[0].questions[0].prompt == questions[0].prompt
    assert level_attempts[0].answers[0].answer == "Level answer 1"


async def test_practice_grade_does_not_update_mastery(session):
    workspace, trail, concept = await _seed_concept(session)
    questions = FakeQuizGenerator().questions
    result = await grade_quiz_submission(
        session,
        FakeQuizGrader(0.9),
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        quiz_type="practice",
        questions=questions,
        answers=[
            QuizAnswer(question_id="q1", answer="A derivative measures change."),
            QuizAnswer(question_id="q2", answer="At x=3, x^2 has derivative 6."),
        ],
    )

    assert result.mastery_status == "not_started"
    record = await session.scalar(
        select(MasteryRecord).where(MasteryRecord.concept_id == concept.id)
    )
    assert record is None


async def test_grade_rejects_missing_answer(session):
    workspace, trail, concept = await _seed_concept(session)
    questions = FakeQuizGenerator().questions

    with pytest.raises(QuizValidationError, match="missing answers"):
        await grade_quiz_submission(
            session,
            FakeQuizGrader(0.9),
            workspace_id=workspace.id,
            trail_id=trail.id,
            concept_id=concept.id,
            quiz_type="level_up",
            questions=questions,
            answers=[QuizAnswer(question_id="q1", answer="Only one answer")],
        )


async def test_grade_rejects_unknown_answer_id(session):
    workspace, trail, concept = await _seed_concept(session)
    questions = FakeQuizGenerator().questions

    with pytest.raises(QuizValidationError, match="unknown question ids"):
        await grade_quiz_submission(
            session,
            FakeQuizGrader(0.9),
            workspace_id=workspace.id,
            trail_id=trail.id,
            concept_id=concept.id,
            quiz_type="level_up",
            questions=questions,
            answers=[
                QuizAnswer(question_id="q1", answer="Answer one"),
                QuizAnswer(question_id="q999", answer="Unknown"),
            ],
        )


async def test_llm_quiz_generator_renders_prompt_and_parses_questions(session):
    _, _, concept = await _seed_concept(session)
    client = FakeLLMClient(
        [
            """
            {
              "questions": [
                {
                  "id": "q1",
                  "type": "multiple_choice",
                  "prompt": "Explain derivatives.",
                  "mastery_label": "explain_derivative",
                  "difficulty": "light",
                  "options": ["A rate of change", "A total amount", "A shape"]
                },
                {
                  "id": "q2",
                  "type": "short_answer",
                  "prompt": "Apply derivatives.",
                  "mastery_label": "apply_derivative",
                  "difficulty": "standard"
                }
              ]
            }
            """
        ]
    )
    generator = LLMQuizGenerator(client=cast(LLMClient, client))

    questions = await generator.generate(
        concept=concept,
        quiz_type="level_up",
        prior_quiz_context="Avoid repeating q1.",
    )

    assert [question.id for question in questions] == ["q1", "q2"]
    prompt = client.calls[0][0]["content"]
    assert "Derivatives" in prompt
    assert "explain_derivative" in prompt
    assert "apply_derivative" in prompt
    assert "level_up" in prompt
    assert "Avoid repeating q1." in prompt


async def test_llm_quiz_generator_repairs_invalid_json_once(session):
    _, _, concept = await _seed_concept(session)
    client = FakeLLMClient(
        [
            "not json",
            """
            {
              "questions": [
                {
                  "id": "q1",
                  "type": "multiple_choice",
                  "prompt": "Explain derivatives.",
                  "mastery_label": "explain_derivative",
                  "difficulty": "light",
                  "options": ["A rate of change", "A total amount", "A shape"]
                },
                {
                  "id": "q2",
                  "type": "short_answer",
                  "prompt": "Apply derivatives.",
                  "mastery_label": "apply_derivative",
                  "difficulty": "standard"
                }
              ]
            }
            """,
        ]
    )
    generator = LLMQuizGenerator(client=cast(LLMClient, client))

    questions = await generator.generate(concept=concept, quiz_type="practice")

    assert len(questions) == 2
    assert len(client.calls) == 2
    assert "ERROR:" in client.calls[1][0]["content"]


async def test_llm_quiz_grader_renders_prompt_and_parses_feedback(session):
    _, _, concept = await _seed_concept(session)
    client = FakeLLMClient(
        [
            """
            {
              "score": 0.8,
              "passed": true,
              "per_question": [
                {
                  "question_id": "q1",
                  "score": 0.8,
                  "feedback": "Strong explanation."
                },
                {
                  "question_id": "q2",
                  "score": 0.8,
                  "feedback": "Good application."
                }
              ],
              "overall_feedback": "Solid understanding."
            }
            """
        ]
    )
    grader = LLMQuizGrader(client=cast(LLMClient, client))
    questions = FakeQuizGenerator().questions
    answers = [
        QuizAnswer(question_id="q1", answer="A derivative measures change."),
        QuizAnswer(question_id="q2", answer="At x=3, x^2 has derivative 6."),
    ]

    evaluation = await grader.grade(concept=concept, questions=questions, answers=answers)

    assert evaluation.score == pytest.approx(0.8)
    prompt = client.calls[0][0]["content"]
    assert "Derivatives" in prompt
    assert "apply" in prompt
    assert "A derivative measures change." in prompt


async def test_llm_quiz_grader_repairs_invalid_json_once(session):
    _, _, concept = await _seed_concept(session)
    client = FakeLLMClient(
        [
            "bad json",
            """
            {
              "score": 0.75,
              "passed": true,
              "per_question": [
                {
                  "question_id": "q1",
                  "score": 0.7,
                  "feedback": "Good."
                },
                {
                  "question_id": "q2",
                  "score": 0.8,
                  "feedback": "Nice application."
                }
              ],
              "overall_feedback": "You passed."
            }
            """,
        ]
    )
    grader = LLMQuizGrader(client=cast(LLMClient, client))
    questions = FakeQuizGenerator().questions
    answers = [
        QuizAnswer(question_id="q1", answer="A derivative measures change."),
        QuizAnswer(question_id="q2", answer="At x=3, x^2 has derivative 6."),
    ]

    evaluation = await grader.grade(concept=concept, questions=questions, answers=answers)

    assert evaluation.score == pytest.approx(0.75)
    assert len(client.calls) == 2
    assert "QUESTION IDS:" in client.calls[1][0]["content"]
