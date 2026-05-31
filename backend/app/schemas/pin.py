from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel

from backend.app.schemas.artifact import ArtifactRead
from backend.app.schemas.flashcard import FlashcardDeckRead
from backend.app.schemas.mastery import QuizAttemptRead

PinItemType = Literal["artifact", "quiz_attempt", "flashcard", "concept"]


class PinRequest(BaseModel):
    item_type: PinItemType
    item_id: str


class ConceptPinItem(BaseModel):
    concept_id: uuid.UUID
    concept_title: str
    trail_id: uuid.UUID
    trail_title: str


class PinListResponse(BaseModel):
    """Aggregated pins for a trail, grouped by item type.

    Each list is the existing read shape for that item type so the frontend can
    reuse ``ArtifactRenderer`` (artifacts) and the quiz-attempt rendering.
    """

    artifacts: list[ArtifactRead]
    quiz_attempts: list[QuizAttemptRead]
    flashcards: list[FlashcardDeckRead] = []
    concepts: list[ConceptPinItem] = []
