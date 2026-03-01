"""Research agent schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ResearchSourceCreate(BaseModel):
    url: str = Field(min_length=1)
    label: str | None = None


class ResearchSourceSummary(BaseModel):
    source_id: int = Field(gt=0)
    url: str
    label: str | None = None
    active: bool


class ResearchRunSummary(BaseModel):
    run_id: int = Field(gt=0)
    status: Literal["pending", "running", "completed", "failed"]
    candidates_found: int = Field(ge=0)
    started_at: datetime
    finished_at: datetime | None = None


class ResearchCandidateSummary(BaseModel):
    candidate_id: int = Field(gt=0)
    source_url: str
    title: str | None = None
    snippet: str | None = None
    status: Literal["pending", "approved", "rejected", "ingested"]


class ResearchCandidateReviewRequest(BaseModel):
    status: Literal["approved", "rejected"]


class TopicPlanRequest(BaseModel):
    """Request body for topic planning."""
    goal: str = Field(min_length=1, max_length=500)


class TopicExecuteRequest(BaseModel):
    """Request body to execute query planning on an approved topic proposal."""
    topic: str = Field(min_length=1)
    subtopics: list[str] = Field(default_factory=list)
    source_classes: list[str] = Field(default_factory=list)
    rationale: str = ""
    priority: Literal["high", "medium", "low"] = "medium"


class QueryPlanResponse(BaseModel):
    """Response from query plan execution."""
    run_id: int = Field(gt=0)
    topic: str
    queries_planned: int = Field(ge=0)
    candidates_inserted: int = Field(ge=0)


class TopicProposalResponse(BaseModel):
    """A single topic proposal returned by the planner."""
    topic: str
    subtopics: list[str] = Field(default_factory=list)
    source_classes: list[str] = Field(default_factory=list)
    rationale: str = ""
    priority: Literal["high", "medium", "low"] = "medium"


class CandidatePromoteRequest(BaseModel):
    """Request to promote an approved candidate through the promotion policy."""
    has_quiz_gate: bool = False
    quiz_passed: bool = False


class CandidatePromotionResponse(BaseModel):
    """Result of running a candidate through the promotion policy."""
    candidate_id: int = Field(gt=0)
    action: Literal["promote", "defer", "reject", "quiz_gate"]
    reason: str = ""
    promoted: bool = False
