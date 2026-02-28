"""Flashcard and practice session schemas."""

from __future__ import annotations

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
