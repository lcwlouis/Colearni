import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .trail import TrailGraphRead, TrailRead
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


class ImportManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    topic: str | None = None
    goal: str | None = None
    target_depth: TargetDepth | None = None
    version: str
    pack_type: Literal["structure"]
    content_included: bool
    hydration_supported: bool


class ImportGraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    node_type: NodeType
    concept_level: ConceptLevel
    difficulty: Difficulty | None = None
    bloom_level: BloomLevel | None = None


class ImportGraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    relation_type: RelationType


class ImportGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[ImportGraphNode] = Field(default_factory=list)
    edges: list[ImportGraphEdge] = Field(default_factory=list)


class ImportConceptSourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    relation: str


class ImportConcept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    node_type: NodeType
    concept_level: ConceptLevel
    parents: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    children: list[str] = Field(default_factory=list)
    learning_objectives: list[str] = Field(default_factory=list)
    mastery_check_labels: list[str] = Field(default_factory=list)
    source_refs: list[ImportConceptSourceRef] = Field(default_factory=list)
    content_included: bool = False
    hydration_required: bool = False


class ImportSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    url: str | None = None
    origin: SourceOrigin
    access: SourceAccess
    license: str | None = None
    include_on_public_export: bool
    content_included: bool = False


class ImportResearchSelectedSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    workspace_id: uuid.UUID | None = None
    source_id: str | None = None
    title: str | None = None
    url: str | None = None
    origin: SourceOrigin | None = None
    source_type: str | None = None
    access: SourceAccess | None = None
    license: str | None = None
    include_on_public_export: bool | None = None
    relation: str | None = None
    reason: str | None = None
    query: str | None = None


class ImportResearchExcludedSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str | None = None
    title: str | None = None
    reason: str


class ImportResearchTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str | None = None
    generated_by: str | None = None
    queries: list[str] = Field(default_factory=list)
    selected_public_sources: list[ImportResearchSelectedSource] = Field(default_factory=list)
    selected_sources: list[ImportResearchSelectedSource] = Field(default_factory=list)
    excluded_sources: list[ImportResearchExcludedSource] = Field(default_factory=list)


class ImportTrailPack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest: ImportManifest
    graph: ImportGraph
    concepts: dict[str, ImportConcept] = Field(default_factory=dict)
    sources: list[ImportSource] = Field(default_factory=list)
    research_trace: ImportResearchTrace = Field(default_factory=ImportResearchTrace)


class TrailPackImportReport(BaseModel):
    trail_id: uuid.UUID
    concepts_imported: int
    edges_imported: int
    sources_available: int
    sources_missing: int
    hydration_required: bool
    warnings: list[str] = Field(default_factory=list)


class TrailPackImportResponse(BaseModel):
    trail: TrailRead
    graph: TrailGraphRead
    report: TrailPackImportReport


class ResearchTraceResponse(BaseModel):
    trace: dict[str, Any]


class HydrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_id: uuid.UUID | None = None
    source_ids: list[uuid.UUID] = Field(default_factory=list)
    use_model_knowledge: bool = False


class HydrationSkippedSource(BaseModel):
    source_id: uuid.UUID
    reason: str


class HydrationResponse(BaseModel):
    hydrated_concepts: int
    private_records_created: int
    skipped_sources: list[HydrationSkippedSource] = Field(default_factory=list)
