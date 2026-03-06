"""Quiz and mastery schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

QuizItemType = Literal["short_answer", "mcq"]
QuizItemResult = Literal["correct", "partial", "incorrect"]
MasteryStatus = Literal["locked", "learning", "learned"]


class QuizItemSummary(BaseModel):
    item_id: int = Field(gt=0)
    position: int = Field(ge=1)
    item_type: QuizItemType
    prompt: str = Field(min_length=1)
    choices: list[QuizChoiceSummary] | None


class QuizChoiceSummary(BaseModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class QuizCreateResponse(BaseModel):
    quiz_id: int = Field(gt=0)
    workspace_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    concept_id: int = Field(gt=0)
    status: str = Field(min_length=1)
    items: list[QuizItemSummary] = Field(min_length=1)


class QuizFeedbackItem(BaseModel):
    item_id: int = Field(gt=0)
    item_type: QuizItemType
    result: QuizItemResult
    is_correct: bool
    critical_misconception: bool
    feedback: str = Field(min_length=1)
    score: float | None = Field(default=None, ge=0.0, le=1.0)


class PracticeQuizSubmitResponse(BaseModel):
    quiz_id: int = Field(gt=0)
    attempt_id: int = Field(gt=0)
    score: float = Field(ge=0.0, le=1.0)
    passed: bool
    critical_misconception: bool
    overall_feedback: str = Field(min_length=1)
    items: list[QuizFeedbackItem] = Field(min_length=1)
    replayed: bool
    retry_hint: str | None


class LevelUpQuizSubmitResponse(PracticeQuizSubmitResponse):
    mastery_status: MasteryStatus
    mastery_score: float = Field(ge=0.0, le=1.0)


class PracticeQuizAttemptSummary(BaseModel):
    attempt_id: int = Field(gt=0)
    score: float = Field(ge=0.0, le=1.0)
    passed: bool
    critical_misconception: bool
    overall_feedback: str = Field(min_length=1)
    graded_at: datetime
    grading_items: list[QuizFeedbackItem] = Field(default_factory=list)


class PracticeQuizHistoryEntry(BaseModel):
    quiz_id: int = Field(gt=0)
    workspace_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    concept_id: int | None = Field(default=None, gt=0)
    concept_name: str | None = None
    status: str = Field(min_length=1)
    item_count: int = Field(ge=0)
    created_at: datetime
    latest_attempt: PracticeQuizAttemptSummary | None = None


class PracticeQuizHistoryListResponse(BaseModel):
    workspace_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    concept_id: int | None = Field(default=None, gt=0)
    quizzes: list[PracticeQuizHistoryEntry]


class PracticeQuizDetailResponse(PracticeQuizHistoryEntry):
    items: list[QuizItemSummary] = Field(min_length=1)


class LevelUpQuizAttemptSummary(PracticeQuizAttemptSummary):
    pass


class LevelUpQuizHistoryEntry(BaseModel):
    quiz_id: int = Field(gt=0)
    workspace_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    concept_id: int | None = Field(default=None, gt=0)
    concept_name: str | None = None
    status: str = Field(min_length=1)
    item_count: int = Field(ge=0)
    created_at: datetime
    latest_attempt: LevelUpQuizAttemptSummary | None = None


class LevelUpQuizHistoryListResponse(BaseModel):
    workspace_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    concept_id: int | None = Field(default=None, gt=0)
    quizzes: list[LevelUpQuizHistoryEntry]


class LevelUpQuizDetailResponse(LevelUpQuizHistoryEntry):
    items: list[QuizItemSummary] = Field(min_length=1)


class LevelUpPromoteToPracticeResponse(BaseModel):
    source_quiz_id: int = Field(gt=0)
    practice_quiz: QuizCreateResponse
