import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.app.schemas.types import BloomLevel, MasteryStatus, QuizType


class WorkspaceCreate(BaseModel):
    name: str


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    created_at: datetime


class WorkspaceListResponse(BaseModel):
    workspaces: list[WorkspaceRead]


class MasterySummary(BaseModel):
    total: int
    not_started: int
    learning: int
    needs_review: int
    mastered: int


class ConceptMasteryItem(BaseModel):
    concept_id: uuid.UUID
    concept_title: str
    status: MasteryStatus
    score: float
    bloom_level: BloomLevel


class TrailProgressItem(BaseModel):
    trail_id: uuid.UUID
    trail_title: str
    mastery_summary: MasterySummary
    concepts: list[ConceptMasteryItem]


class WorkspaceProgressResponse(BaseModel):
    trails: list[TrailProgressItem]


class WorkspaceQuizAttemptItem(BaseModel):
    id: uuid.UUID
    concept_id: uuid.UUID
    concept_title: str
    trail_id: uuid.UUID
    trail_title: str
    quiz_type: QuizType
    passed: bool
    score: float
    evaluator_feedback: str
    created_at: datetime


class WorkspaceQuizAttemptsResponse(BaseModel):
    attempts: list[WorkspaceQuizAttemptItem]


class SourceConceptLink(BaseModel):
    concept_id: uuid.UUID
    concept_title: str
    trail_id: uuid.UUID
    trail_title: str
    relation: str


class WorkspaceSourceItem(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    origin: str
    access: str
    title: str
    url: str | None
    license: str | None
    include_on_public_export: bool
    metadata_json: dict
    linked_concepts: list[SourceConceptLink] = []


class WorkspaceSourcesResponse(BaseModel):
    sources: list[WorkspaceSourceItem]
