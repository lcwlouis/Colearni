from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NoteRead(BaseModel):
    """A persisted note returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    trail_id: uuid.UUID
    concept_id: uuid.UUID | None = None
    title: str | None = None
    body: str
    created_at: datetime
    updated_at: datetime


class NoteListResponse(BaseModel):
    notes: list[NoteRead]


class NoteCreateRequest(BaseModel):
    """Create a note attached to a trail (and optionally a concept).

    ``body`` is required free-form markdown; ``title`` is an optional short
    label; ``concept_id`` (when present) pins the note to a concept in the trail.
    """

    title: str | None = Field(default=None, max_length=200)
    body: str = Field(min_length=1)
    concept_id: uuid.UUID | None = None


class NoteUpdateRequest(BaseModel):
    """Partial update of a note's title and/or body.

    Both fields are optional so the client can patch either independently.
    ``title`` may be set to ``null`` to clear it; ``body`` (when present) must
    be non-empty. At least one field must be provided.
    """

    title: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, min_length=1)
