import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .concept import ConceptEdgeRead, ConceptNodeRead
from .mastery import MasteryRecordRead
from .types import TargetDepth


class TrailGenerateRequest(BaseModel):
    """Public request body for POST /api/workspaces/{workspace_id}/trails/generate.

    workspace_id comes from the URL path. title is generated server-side.
    """

    model_config = ConfigDict(extra="forbid")

    topic: str
    goal: str
    target_depth: TargetDepth
    max_nodes: int = Field(default=40, ge=10, le=100)
    # Optional free-text description of what the learner already knows about the
    # topic, captured at creation and fed read-only into the tutor (Phase 13.5d).
    prior_knowledge: str | None = Field(default=None, max_length=2000)


class TrailInsert(BaseModel):
    """Internal schema: used by the service to insert a Trail after generation."""

    workspace_id: uuid.UUID
    title: str
    topic: str
    goal: str
    target_depth: TargetDepth
    prior_knowledge: str | None = None


class TrailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    title: str
    topic: str
    goal: str
    target_depth: TargetDepth
    prior_knowledge: str | None = None
    created_at: datetime
    node_count: int = 0
    edge_count: int = 0


class TrailGraphRead(BaseModel):
    nodes: list[ConceptNodeRead]
    edges: list[ConceptEdgeRead]
    mastery: dict[uuid.UUID, MasteryRecordRead] = Field(default_factory=dict)


class TrailGenerateResponse(BaseModel):
    trail: TrailRead
    graph: TrailGraphRead


class TrailListResponse(BaseModel):
    trails: list[TrailRead]


class MasterySummary(BaseModel):
    total: int
    not_started: int
    learning: int
    needs_review: int
    mastered: int


class TrailDetailResponse(BaseModel):
    trail: TrailRead
    graph: TrailGraphRead
    mastery_summary: MasterySummary


class NextConceptResponse(BaseModel):
    concept_id: uuid.UUID | None
    concept_title: str | None
    reason: str
    all_mastered: bool
    mastery_status: str | None = None
    concept_level: str | None = None
