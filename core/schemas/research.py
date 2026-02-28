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
