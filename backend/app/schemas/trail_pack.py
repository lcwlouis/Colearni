import uuid
from typing import Literal

from pydantic import BaseModel, Field

from .types import (
    BloomLevel,
    ConceptLevel,
    Difficulty,
    NodeType,
    RelationType,
    SourceAccess,
    SourceOrigin,
    TargetDepth,
)


class TrailPackManifest(BaseModel):
    id: str
    title: str
    topic: str | None = None
    goal: str | None = None
    target_depth: TargetDepth | None = None
    version: str = "1.0.0"
    pack_type: Literal["structure"] = "structure"
    content_included: bool = False
    hydration_supported: bool = True


class TrailPackGraphNode(BaseModel):
    id: str
    title: str
    node_type: NodeType
    concept_level: ConceptLevel
    difficulty: Difficulty | None = None
    bloom_level: BloomLevel | None = None


class TrailPackGraphEdge(BaseModel):
    source: str
    target: str
    relation_type: RelationType


class TrailPackGraph(BaseModel):
    nodes: list[TrailPackGraphNode] = Field(default_factory=list)
    edges: list[TrailPackGraphEdge] = Field(default_factory=list)


class TrailPackConceptSourceRef(BaseModel):
    source_id: uuid.UUID
    relation: str


class TrailPackConcept(BaseModel):
    id: str
    title: str
    node_type: NodeType
    concept_level: ConceptLevel
    parents: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    children: list[str] = Field(default_factory=list)
    learning_objectives: list[str] = Field(default_factory=list)
    mastery_check_labels: list[str] = Field(default_factory=list)
    source_refs: list[TrailPackConceptSourceRef] = Field(default_factory=list)
    content_included: bool = False
    hydration_required: bool = False


class TrailPackSource(BaseModel):
    id: uuid.UUID
    title: str
    url: str | None
    origin: SourceOrigin
    access: SourceAccess
    license: str | None
    include_on_public_export: bool
    content_included: bool = False


class TrailPack(BaseModel):
    manifest: TrailPackManifest
    graph: TrailPackGraph
    concepts: dict[str, TrailPackConcept] = Field(default_factory=dict)
    sources: list[TrailPackSource] = Field(default_factory=list)
    research_trace: dict = Field(default_factory=dict)


class TrailPackExportIncludedReport(BaseModel):
    concepts: int
    edges: int
    source_links: int
    has_research_trace: bool


class TrailPackExportExcludedReport(BaseModel):
    uploaded_files: int
    chunks: int
    embeddings: int
    private_notes: int
    mastery_records: bool


class TrailPackExportReport(BaseModel):
    included: TrailPackExportIncludedReport
    excluded: TrailPackExportExcludedReport


class TrailPackExportResponse(BaseModel):
    pack: TrailPack
    report: TrailPackExportReport
