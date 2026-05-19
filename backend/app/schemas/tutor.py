"""Pydantic schemas for tutor chat request/response types."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TutorMode = Literal["socratic", "direct", "repair", "quiz_prompt", "explore"]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., max_length=4000)
    conversation_id: uuid.UUID | None = None

    @field_validator("message", mode="before")
    @classmethod
    def message_not_blank(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            raise ValueError("message must not be blank")
        return v


class ConversationMessage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    reasoning: str | None = None
    mode: TutorMode | None = None
    created_at: datetime


class ConversationHistoryResponse(BaseModel):
    conversation_id: uuid.UUID | None
    messages: list[ConversationMessage]
