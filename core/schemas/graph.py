"""Graph concept and subgraph response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from core.schemas.quizzes import MasteryStatus

LuckyMode = Literal["adjacent", "wildcard"]


class GraphConceptDetail(BaseModel):
    concept_id: int = Field(gt=0)
    canonical_name: str = Field(min_length=1)
    description: str
    aliases: list[str] = Field(default_factory=list)
    degree: int = Field(ge=0)


class GraphConceptDetailResponse(BaseModel):
    workspace_id: int = Field(gt=0)
    concept: GraphConceptDetail


class GraphConceptSummary(BaseModel):
    concept_id: int = Field(gt=0)
    canonical_name: str = Field(min_length=1)
    description: str
    degree: int = Field(ge=0)
    mastery_status: MasteryStatus | None = None
    mastery_score: float | None = Field(default=None, ge=0.0, le=1.0)


class GraphConceptListResponse(BaseModel):
    workspace_id: int = Field(gt=0)
    user_id: int | None = Field(default=None, gt=0)
    concepts: list[GraphConceptSummary]


class GraphSubgraphNode(BaseModel):
    concept_id: int = Field(gt=0)
    canonical_name: str = Field(min_length=1)
    description: str
    hop_distance: int = Field(ge=0)
    mastery_status: MasteryStatus | None = None
    mastery_score: float | None = Field(default=None, ge=0.0, le=1.0)


class GraphSubgraphEdge(BaseModel):
    edge_id: int = Field(gt=0)
    src_concept_id: int = Field(gt=0)
    tgt_concept_id: int = Field(gt=0)
    relation_type: str = Field(min_length=1)
    description: str
    keywords: list[str] = Field(default_factory=list)
    weight: float


class GraphSubgraphResponse(BaseModel):
    workspace_id: int = Field(gt=0)
    root_concept_id: int | None = Field(default=None, gt=0)
    max_hops: int | None = Field(default=None, ge=1)
    nodes: list[GraphSubgraphNode]
    edges: list[GraphSubgraphEdge]
    is_truncated: bool = Field(default=False, description="True when results were capped by max_nodes/max_edges")
    total_concept_count: int | None = Field(default=None, ge=0, description="Total concepts in scope before truncation")


class GraphLuckyAdjacentScoreComponents(BaseModel):
    hop_distance: int = Field(ge=0)
    strongest_link_weight: float


class GraphLuckyWildcardScoreComponents(BaseModel):
    degree: int = Field(ge=0)
    total_incident_weight: float


class GraphLuckyPickAdjacent(BaseModel):
    concept_id: int = Field(gt=0)
    canonical_name: str = Field(min_length=1)
    description: str
    hop_distance: int = Field(ge=0)
    score_components: GraphLuckyAdjacentScoreComponents


class GraphLuckyPickWildcard(BaseModel):
    concept_id: int = Field(gt=0)
    canonical_name: str = Field(min_length=1)
    description: str
    hop_distance: None = None
    score_components: GraphLuckyWildcardScoreComponents


class GraphLuckyResponse(BaseModel):
    workspace_id: int = Field(gt=0)
    seed_concept_id: int = Field(gt=0)
    mode: LuckyMode
    pick: GraphLuckyPickAdjacent | GraphLuckyPickWildcard

    @model_validator(mode="after")
    def _validate_pick_mode(self) -> GraphLuckyResponse:
        if self.mode == "adjacent" and isinstance(self.pick, GraphLuckyPickWildcard):
            raise ValueError("adjacent mode requires adjacent pick payload")
        if self.mode == "wildcard" and isinstance(self.pick, GraphLuckyPickAdjacent):
            raise ValueError("wildcard mode requires wildcard pick payload")
        return self
