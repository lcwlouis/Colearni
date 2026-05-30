from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .types import BloomLevel, MasteryStatus, QuizType

QuizQuestionType = Literal[
    "multiple_choice",
    "short_answer",
    "long_answer",
    "code",
    "multi_select",
    "ordering",
    "cloze",
]
_OPTION_QUESTION_TYPES: frozenset[str] = frozenset({"multiple_choice", "multi_select", "ordering"})
QuizQuestionDifficulty = Literal["light", "standard", "challenge"]
_LEGACY_QUESTION_TYPES: dict[str, QuizQuestionType] = {
    "explain": "long_answer",
    "apply": "long_answer",
    "compare": "long_answer",
}


class MasteryRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = None
    workspace_id: uuid.UUID
    concept_id: uuid.UUID
    status: MasteryStatus
    bloom_level: BloomLevel
    score: float = Field(ge=0.0, le=1.0)
    updated_at: datetime | None = None


class QuizQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=100)
    type: QuizQuestionType
    prompt: str = Field(min_length=1, max_length=2000)
    mastery_label: str = Field(min_length=1, max_length=200)
    difficulty: QuizQuestionDifficulty = "standard"
    options: list[str] | None = Field(default=None, min_length=2, max_length=6)

    @field_validator("type", mode="before")
    @classmethod
    def normalize_legacy_question_type(cls, value: object) -> object:
        # Existing persisted drafts/attempt snapshots may still use the old labels.
        if isinstance(value, str):
            return _LEGACY_QUESTION_TYPES.get(value, value)
        return value

    @field_validator("id", "prompt", "mastery_label", mode="before")
    @classmethod
    def strip_non_blank_strings(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("value must not be blank")
            return stripped
        return value

    @field_validator("options", mode="before")
    @classmethod
    def strip_options(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, list):
            stripped = [item.strip() for item in value if isinstance(item, str) and item.strip()]
            return stripped or None
        return value

    @model_validator(mode="after")
    def validate_options_for_type(self) -> QuizQuestion:
        if self.type in _OPTION_QUESTION_TYPES:
            if not self.options or len(self.options) < 2:
                raise ValueError(f"{self.type} questions require at least two options")
            if len(set(self.options)) != len(self.options):
                raise ValueError(f"{self.type} options must be unique")
        elif self.options:
            raise ValueError(
                "options are only allowed for multiple_choice, multi_select, and ordering questions"
            )
        return self


class QuizAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=1, max_length=100)
    answer: str = Field(min_length=1, max_length=4000)

    @field_validator("question_id", "answer", mode="before")
    @classmethod
    def strip_non_blank_strings(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("value must not be blank")
            return stripped
        return value


class LevelUpCard(BaseModel):
    concept_id: uuid.UUID
    quiz_type: QuizType
    questions: list[QuizQuestion] = Field(min_length=2, max_length=4)


class QuizGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    force_new: bool = False


class QuizGradeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[QuizQuestion] = Field(min_length=1, max_length=4)
    answers: list[QuizAnswer] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def validate_question_and_answer_ids(self) -> QuizGradeRequest:
        question_ids = [question.id for question in self.questions]
        answer_ids = [answer.question_id for answer in self.answers]
        if len(set(question_ids)) != len(question_ids):
            raise ValueError("questions must have unique ids")
        if len(set(answer_ids)) != len(answer_ids):
            raise ValueError("answers must reference each question at most once")
        return self


class PerQuestionEvaluation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    question_id: str = Field(min_length=1, max_length=100)
    score: float = Field(ge=0.0, le=1.0)
    feedback: str = Field(min_length=1, max_length=2000)

    @field_validator("question_id", "feedback", mode="before")
    @classmethod
    def strip_non_blank_strings(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("value must not be blank")
            return stripped
        return value


class GradeResult(BaseModel):
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    feedback: str
    per_question: list[PerQuestionEvaluation] = Field(default_factory=list)
    mastery_status: MasteryStatus
    attempt_id: uuid.UUID


class QuizAttemptRead(BaseModel):
    id: uuid.UUID
    concept_id: uuid.UUID
    quiz_type: QuizType
    questions: list[QuizQuestion]
    answers: list[QuizAnswer]
    evaluator_feedback: str
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    created_at: datetime


class QuizAttemptListResponse(BaseModel):
    attempts: list[QuizAttemptRead]


class QuizGenerationOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    questions: list[QuizQuestion] = Field(min_length=2, max_length=4)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> QuizGenerationOutput:
        question_ids = [question.id for question in self.questions]
        if len(set(question_ids)) != len(question_ids):
            raise ValueError("generated questions must have unique ids")
        return self


class QuizEvaluation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    score: float = Field(ge=0.0, le=1.0)
    passed: bool | None = None
    per_question: list[PerQuestionEvaluation] = Field(default_factory=list)
    overall_feedback: str = Field(min_length=1, max_length=4000)

    @field_validator("overall_feedback", mode="before")
    @classmethod
    def strip_overall_feedback(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("overall_feedback must not be blank")
            return stripped
        return value
