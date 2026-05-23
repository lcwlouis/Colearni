import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.models.base import Base
from backend.app.models.concept import ConceptNode
from backend.app.models.mastery import MasteryRecord, QuizAttempt, QuizDraft
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.schemas.mastery import QuizAnswer, QuizEvaluation, QuizQuestion
from backend.app.services.quizzes import (
    LLMQuizGenerator,
    LLMQuizGrader,
    QuizValidationError,
    generate_quiz_card,
    grade_quiz_submission,
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
        self.calls: list[tuple[str, str]] = []

    async def generate(self, *, concept: ConceptNode, quiz_type: str) -> list[QuizQuestion]:
        self.calls.append((concept.title, quiz_type))
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
                {
                    "question_id": question.id,
                    "score": self.score,
                    "feedback": f"Feedback for {question.id}",
                }
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
    assert generator.calls == [("Derivatives", "level_up")]


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
    assert generator.calls == [("Derivatives", "level_up")]


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
        fake_session,
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
    assert first_generator.calls == [("Derivatives", "level_up")]
    assert second_generator.calls == [("Derivatives", "level_up")]


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
    record = await session.scalar(
        select(MasteryRecord).where(MasteryRecord.concept_id == concept.id)
    )
    assert record is not None
    assert record.status == "mastered"
    attempt = await session.scalar(select(QuizAttempt).where(QuizAttempt.id == result.attempt_id))
    assert attempt is not None
    assert attempt.quiz_type == "level_up"
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
    generator = LLMQuizGenerator(client=client)

    questions = await generator.generate(concept=concept, quiz_type="level_up")

    assert [question.id for question in questions] == ["q1", "q2"]
    prompt = client.calls[0][0]["content"]
    assert "Derivatives" in prompt
    assert "explain_derivative" in prompt
    assert "apply_derivative" in prompt
    assert "level_up" in prompt


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
            """
        ]
    )
    generator = LLMQuizGenerator(client=client)

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
    grader = LLMQuizGrader(client=client)
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
            """
        ]
    )
    grader = LLMQuizGrader(client=client)
    questions = FakeQuizGenerator().questions
    answers = [
        QuizAnswer(question_id="q1", answer="A derivative measures change."),
        QuizAnswer(question_id="q2", answer="At x=3, x^2 has derivative 6."),
    ]

    evaluation = await grader.grade(concept=concept, questions=questions, answers=answers)

    assert evaluation.score == pytest.approx(0.75)
    assert len(client.calls) == 2
    assert "QUESTION IDS:" in client.calls[1][0]["content"]
