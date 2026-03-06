"""Pydantic v2 models mirroring every JSON schema used in LLM structured-output calls."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Raw graph extraction
# ---------------------------------------------------------------------------

class RawConceptItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    context_snippet: str | None
    description: str | None
    tier: Literal["umbrella", "topic", "subtopic", "granular"] | None


class RawEdgeItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    src_name: str
    tgt_name: str
    relation_type: str
    description: str | None
    keywords: list[str]
    weight: int


class RawGraphResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concepts: list[RawConceptItem]
    edges: list[RawEdgeItem]


# ---------------------------------------------------------------------------
# Disambiguation
# ---------------------------------------------------------------------------

class DisambiguationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["MERGE_INTO", "CREATE_NEW", "LINK_ONLY"]
    confidence: float
    merge_into_id: int | None
    merge_into_name: str | None
    alias_to_add: str | None
    proposed_description: str | None
    link_to_id: int | None
    link_to_name: str | None
    link_relation_type: str | None
    proposed_tier: str | None


class DisambiguationBatchDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_ref: str
    operations: list[DisambiguationResponse]


class DisambiguationBatchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decisions: list[DisambiguationBatchDecision]


# ---------------------------------------------------------------------------
# Query analysis
# ---------------------------------------------------------------------------

class QueryAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["learn", "practice", "level_up", "explore", "social", "clarify"]
    requested_mode: Literal["socratic", "direct", "unknown"]
    needs_retrieval: bool
    should_offer_level_up: bool
    high_level_keywords: list[str]
    low_level_keywords: list[str]
    concept_hints: list[str]


# ---------------------------------------------------------------------------
# Quiz grading
# ---------------------------------------------------------------------------

class QuizGradingItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: int
    score: float = Field(ge=0.0, le=1.0)
    critical_misconception: bool
    feedback: str

    @field_validator("feedback")
    @classmethod
    def _feedback_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("feedback must not be empty")
        return v


class QuizGradingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[QuizGradingItem]
    overall_feedback: str

    @field_validator("overall_feedback")
    @classmethod
    def _overall_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("overall_feedback must not be empty")
        return v
