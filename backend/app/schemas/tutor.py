"""Pydantic schemas for tutor chat request/response types."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TutorMode = Literal["socratic", "direct", "repair", "quiz_prompt", "explore", "free_explore"]
TutorStreamStatus = Literal[
    "selecting_mode",
    "thinking",
    "calling_tool",
    "tool_called",
    "tool_complete",
    "responding",
    "retrying_without_thinking",
]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., max_length=4000)
    conversation_id: uuid.UUID | None = None
    regenerate: bool = False
    replace_latest_user: bool = False

    @field_validator("message", mode="before")
    @classmethod
    def message_not_blank(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            raise ValueError("message must not be blank")
        return v


class ConversationReasoningPart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "status",
        "thinking",
        "tool_call",
        "tool_result",
        "suggest_quiz",
        "suggest_flashcards",
        "suggest_artifact",
    ]
    status: TutorStreamStatus | None = None
    text: str | None = None
    name: str | None = None
    mode: TutorMode | None = None
    query: str | None = None
    result: str | None = None
    # suggest_quiz parts (Phase 14): the tutor's opt-in quiz suggestion. The
    # backend stays the owner of the quiz draft; this only carries the intent so
    # the CTA rehydrates with the rest of the turn trace.
    quiz_type: Literal["level_up", "practice"] | None = None
    reason: str | None = None
    # suggest_artifact parts (Phase 15f): the tutor's opt-in artifact suggestion.
    # The backend stays the owner of artifact generation/persistence; this only
    # carries the intent (kind + reason) so the CTA rehydrates on reload.
    artifact_kind: (
        Literal[
            "worked_example",
            "comparison_card",
            "timeline",
            "mini_graph",
            "simulation_slider",
        ]
        | None
    ) = None


class ConversationMessage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    reasoning: str | None = None
    reasoning_parts: list[ConversationReasoningPart] = Field(default_factory=list)
    mode: TutorMode | None = None
    created_at: datetime

    @field_validator("reasoning_parts", mode="before")
    @classmethod
    def reasoning_parts_default_empty(cls, v: object) -> object:
        return [] if v is None else v


class ConversationHistoryResponse(BaseModel):
    conversation_id: uuid.UUID | None
    messages: list[ConversationMessage]


class ConversationThreadSummary(BaseModel):
    id: uuid.UUID
    title: str
    preview: str | None = None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ConversationThreadUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=120)

    @field_validator("title", mode="before")
    @classmethod
    def title_not_blank(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            raise ValueError("title must not be blank")
        return v


class ConversationThreadListResponse(BaseModel):
    conversations: list[ConversationThreadSummary]
