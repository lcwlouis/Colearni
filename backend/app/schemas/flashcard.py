from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CardType = Literal["basic", "cloze", "reverse"]


# ---------------------------------------------------------------------------
# Strict generator output schema (extra="forbid") — mirrors quiz/primer output.
# ---------------------------------------------------------------------------


class GeneratedCard(BaseModel):
    """One atomic card emitted by the generator.

    ``source_ref`` must reference real grounding material (a source_revision_id
    the backend provided); cards whose ref is unknown are dropped so the model
    can never invent a citation.
    """

    model_config = ConfigDict(extra="forbid")

    front: str = Field(min_length=1)
    back: str = Field(min_length=1)
    hint: str | None = None
    source_ref: str | None = None
    card_type: CardType = "basic"


class FlashcardGenerationOutput(BaseModel):
    """The generator contract: cards + an honest ``exhausted`` decline.

    When the model has no more useful facts it returns ``cards: []`` with
    ``exhausted: true`` and a short ``reason`` instead of padding garbage.
    """

    model_config = ConfigDict(extra="forbid")

    cards: list[GeneratedCard] = Field(default_factory=list)
    exhausted: bool = False
    reason: str = ""


# ---------------------------------------------------------------------------
# Read schemas (returned by the API).
# ---------------------------------------------------------------------------


class FlashcardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    deck_id: uuid.UUID
    front: str
    back: str
    hint: str | None = None
    source_ref: str | None = None
    card_type: str
    box: int
    interval_days: int
    last_reviewed: datetime | None = None
    due: datetime | None = None
    reps: int
    lapses: int
    created_at: datetime


class FlashcardDeckRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    trail_id: uuid.UUID
    concept_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    cards: list[FlashcardRead] = Field(default_factory=list)


class FlashcardGenerateRequest(BaseModel):
    """Generate (or extend) a concept's deck.

    ``extend`` appends new, non-duplicate cards to the existing deck; ``force``
    regenerates from scratch (drops existing cards). Both default off, in which
    case an existing deck is returned unchanged (idempotent).
    """

    extend: bool = False
    force: bool = False


class FlashcardGenerateResponse(BaseModel):
    """Deck after generation plus the generator's decline signal."""

    deck: FlashcardDeckRead
    exhausted: bool = False
    reason: str = ""


class FlashcardReviewRequest(BaseModel):
    recalled: bool
