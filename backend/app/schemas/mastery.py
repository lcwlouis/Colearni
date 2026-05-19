from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .types import BloomLevel, MasteryStatus, QuizType

QuizQuestionType = Literal["explain", "apply", "compare"]


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

    @field_validator("id", "prompt", "mastery_label", mode="before")
    @classmethod
    def strip_non_blank_strings(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("value must not be blank")
            return stripped
        return value


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


class GradeResult(BaseModel):
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    feedback: str
    mastery_status: MasteryStatus
    attempt_id: uuid.UUID


class QuizGenerationOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    questions: list[QuizQuestion] = Field(min_length=2, max_length=4)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> QuizGenerationOutput:
        question_ids = [question.id for question in self.questions]
        if len(set(question_ids)) != len(question_ids):
            raise ValueError("generated questions must have unique ids")
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
