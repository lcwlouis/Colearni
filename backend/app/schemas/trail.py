import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .concept import ConceptEdgeRead, ConceptNodeRead
from .types import TargetDepth


class TrailGenerateRequest(BaseModel):
    """Public request body for POST /api/workspaces/{workspace_id}/trails/generate.

    workspace_id comes from the URL path. title is generated server-side.
    """

    model_config = ConfigDict(extra="forbid")

    topic: str
    goal: str
    target_depth: TargetDepth


class TrailInsert(BaseModel):
    """Internal schema: used by the service to insert a Trail after generation."""

    workspace_id: uuid.UUID
    title: str
    topic: str
    goal: str
    target_depth: TargetDepth


class TrailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    title: str
    topic: str
    goal: str
    target_depth: TargetDepth
    created_at: datetime
    node_count: int = 0
    edge_count: int = 0


class TrailGraphRead(BaseModel):
    nodes: list[ConceptNodeRead]
    edges: list[ConceptEdgeRead]


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
