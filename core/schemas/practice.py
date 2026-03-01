"""Flashcard and practice session schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

FlashcardSelfRating = Literal["again", "hard", "good", "easy"]


class PracticeFlashcard(BaseModel):
    front: str = Field(min_length=1)
    back: str = Field(min_length=1)
    hint: str = Field(min_length=1)


class PracticeFlashcardsResponse(BaseModel):
    workspace_id: int = Field(gt=0)
    concept_id: int = Field(gt=0)
    concept_name: str = Field(min_length=1)
    flashcards: list[PracticeFlashcard] = Field(min_length=1)


class StatefulFlashcard(BaseModel):
    flashcard_id: str = Field(min_length=1)
    front: str = Field(min_length=1)
    back: str = Field(min_length=1)
    hint: str = Field(min_length=1)
    self_rating: FlashcardSelfRating | None = None
    passed: bool = False
    due_at: datetime | None = None
    interval_days: float | None = Field(default=None, ge=0.0)


class StatefulFlashcardsResponse(BaseModel):
    workspace_id: int = Field(gt=0)
    concept_id: int = Field(gt=0)
    concept_name: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    flashcards: list[StatefulFlashcard]
    has_more: bool = True
    exhausted_reason: str | None = None


class FlashcardRateRequest(BaseModel):
    flashcard_id: str = Field(min_length=1)
    self_rating: FlashcardSelfRating


class FlashcardRateResponse(BaseModel):
    flashcard_id: str
    self_rating: FlashcardSelfRating
    passed: bool


class FlashcardRunSummary(BaseModel):
    run_id: str = Field(min_length=1)
    workspace_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    concept_id: int = Field(gt=0)
    concept_name: str = Field(min_length=1)
    item_count: int = Field(ge=0)
    has_more: bool
    exhausted_reason: str | None = None
    created_at: datetime


class FlashcardRunListResponse(BaseModel):
    workspace_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    concept_id: int | None = Field(default=None, gt=0)
    runs: list[FlashcardRunSummary]


class FlashcardRunDetailResponse(BaseModel):
    run_id: str = Field(min_length=1)
    workspace_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    concept_id: int = Field(gt=0)
    concept_name: str = Field(min_length=1)
    item_count: int = Field(ge=0)
    has_more: bool
    exhausted_reason: str | None = None
    created_at: datetime
    flashcards: list[StatefulFlashcard]
