"""Chat session, request, and stream-event schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, field_validator

from core.schemas.assistant import AssistantResponseEnvelope, GenerationTrace, GroundingMode

ConceptSwitchDecision = Literal["accept", "reject"]

ChatMessageType = Literal["user", "assistant", "system", "tool", "card"]


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


class ChatRespondRequest(BaseModel):
    """Input payload for /chat/respond."""

    workspace_id: int = Field(gt=0)
    query: str = Field(min_length=1)
    session_id: int | None = Field(default=None, gt=0)
    user_id: int | None = Field(default=None, gt=0)
    concept_id: int | None = Field(default=None, gt=0)
    suggested_concept_id: int | None = Field(default=None, gt=0)
    concept_switch_decision: ConceptSwitchDecision | None = None
    top_k: int = Field(default=5, ge=1)
    grounding_mode: GroundingMode | None = None

    @field_validator("query")
    @classmethod
    def _normalize_query(cls, value: str) -> str:
        return _require_non_empty(value, "query")


class ChatSessionSummary(BaseModel):
    session_id: int = Field(gt=0)
    public_id: str = Field(min_length=1)
    workspace_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    title: str | None = None
    last_activity_at: datetime


class ChatSessionListResponse(BaseModel):
    workspace_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    sessions: list[ChatSessionSummary]


class ChatMessageRecord(BaseModel):
    message_id: int = Field(gt=0)
    session_id: int = Field(gt=0)
    type: ChatMessageType
    payload: dict[str, object]
    created_at: datetime


class ChatMessagesResponse(BaseModel):
    workspace_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    session_id: int = Field(gt=0)
    messages: list[ChatMessageRecord]


class OnboardingSuggestedTopic(BaseModel):
    concept_id: int = Field(gt=0)
    canonical_name: str
    description: str | None = None
    degree: int = Field(ge=0)


class OnboardingStatusResponse(BaseModel):
    has_documents: bool
    has_active_concepts: bool
    suggested_topics: list[OnboardingSuggestedTopic] = Field(default_factory=list)


# ── Stream-event schemas (G0) ────────────────────────────────────────


class ChatPhase(str, Enum):
    """Backend lifecycle phases for chat generation."""

    THINKING = "thinking"
    SEARCHING = "searching"
    RESPONDING = "responding"
    FINALIZING = "finalizing"


class ChatStreamStatusEvent(BaseModel):
    """Phase transition event sent over SSE."""

    event: Literal["status"] = "status"
    phase: ChatPhase


class ChatStreamDeltaEvent(BaseModel):
    """Incremental text chunk from the LLM."""

    event: Literal["delta"] = "delta"
    text: str


class ChatStreamTraceEvent(BaseModel):
    """Safe operational trace emitted near end-of-stream."""

    event: Literal["trace"] = "trace"
    trace: GenerationTrace


class ChatStreamFinalEvent(BaseModel):
    """Terminal success event carrying the full response envelope."""

    event: Literal["final"] = "final"
    envelope: AssistantResponseEnvelope


class ChatStreamErrorEvent(BaseModel):
    """Terminal error event."""

    event: Literal["error"] = "error"
    message: str
    phase: ChatPhase | None = None


ChatStreamEvent = Annotated[
    Union[
        ChatStreamStatusEvent,
        ChatStreamDeltaEvent,
        ChatStreamTraceEvent,
        ChatStreamFinalEvent,
        ChatStreamErrorEvent,
    ],
    Field(discriminator="event"),
]
