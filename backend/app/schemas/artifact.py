from __future__ import annotations

import math
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from backend.app.services.simulations import SIMULATION_PARAM_NAMES

ArtifactKind = Literal[
    "worked_example",
    "comparison_card",
    "timeline",
    "mini_graph",
    "simulation_slider",
]
SimKind = Literal["linear", "quadratic", "exponential", "supply_demand"]
ArtifactVisibility = Literal["local_only", "source_derived"]


# ---------------------------------------------------------------------------
# Strict output schemas (extra="forbid") — the LOCKED envelope contract.
# ---------------------------------------------------------------------------


class ArtifactCitationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_revision_id: str
    quote: str | None = None
    line_start: int | None = None
    line_end: int | None = None


class ArtifactProvenanceOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_ids: list[str] = Field(default_factory=list)
    visibility: ArtifactVisibility
    citations: list[ArtifactCitationOutput] = Field(default_factory=list)


class WorkedExampleStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    detail: str


class WorkedExampleData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: list[WorkedExampleStep]
    final_answer: str | None = None


class ComparisonCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    values: list[str]


class ComparisonCardData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[str]
    criteria: list[ComparisonCriterion]

    @model_validator(mode="after")
    def _check_value_lengths(self) -> ComparisonCardData:
        expected = len(self.items)
        for index, criterion in enumerate(self.criteria):
            if len(criterion.values) != expected:
                raise ValueError(
                    f"comparison_card criteria[{index}] '{criterion.label}' has "
                    f"{len(criterion.values)} values but expected {expected} "
                    "(one per item)"
                )
        return self


class TimelineEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    # Free-form ordering/date string (e.g. "1969", "Step 2", "c. 400 BCE")
    # kept as a string for flexibility across calendars and orderings.
    when: str
    note: str | None = None


class TimelineData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[TimelineEvent]

    @model_validator(mode="after")
    def _check_events(self) -> TimelineData:
        if not self.events:
            raise ValueError("timeline requires at least one event")
        return self


MINI_GRAPH_MAX_NODES = 20
MINI_GRAPH_MAX_EDGES = 40


class MiniGraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str


class MiniGraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    label: str | None = None


class MiniGraphData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[MiniGraphNode]
    edges: list[MiniGraphEdge]

    @model_validator(mode="after")
    def _check_bounds(self) -> MiniGraphData:
        if not self.nodes:
            raise ValueError("mini_graph requires at least one node")
        if len(self.nodes) > MINI_GRAPH_MAX_NODES:
            raise ValueError(
                f"mini_graph allows at most {MINI_GRAPH_MAX_NODES} nodes (got {len(self.nodes)})"
            )
        if len(self.edges) > MINI_GRAPH_MAX_EDGES:
            raise ValueError(
                f"mini_graph allows at most {MINI_GRAPH_MAX_EDGES} edges (got {len(self.edges)})"
            )
        node_ids = {node.id for node in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValueError("mini_graph node ids must be unique")
        for index, edge in enumerate(self.edges):
            if edge.source not in node_ids:
                raise ValueError(
                    f"mini_graph edges[{index}] source '{edge.source}' is not a known node id"
                )
            if edge.target not in node_ids:
                raise ValueError(
                    f"mini_graph edges[{index}] target '{edge.target}' is not a known node id"
                )
        return self


# ---------------------------------------------------------------------------
# simulation_slider — interactive but TRUSTED-TEMPLATE (closed enum + hardcoded
# compute). The LLM only emits a validated data payload; the backend owns the
# ``precomputed`` oracle (see backend.app.services.simulations).
# ---------------------------------------------------------------------------

SIMULATION_MAX_PARAMS = 3


class SimulationParameter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    label: str
    min: float
    max: float
    default: float
    step: float | None = None


class SimulationRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min: float
    max: float


class SimulationPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float


class SimulationBounds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min: float
    max: float


class SimulationPrecomputed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    at_defaults: list[SimulationPoint]
    y_bounds: SimulationBounds


class SimulationSliderData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sim_kind: SimKind
    parameters: list[SimulationParameter]
    x_label: str
    y_label: str
    x_range: SimulationRange | None = None
    # Predict-then-check prompt shown alongside the interactive plot.
    prompt: str
    # Backend-owned oracle. The model MAY omit it; the service computes and
    # overwrites it from the trusted compute functions before persistence.
    precomputed: SimulationPrecomputed | None = None

    @model_validator(mode="after")
    def _check(self) -> SimulationSliderData:
        if not self.parameters:
            raise ValueError("simulation_slider requires at least one parameter")
        if len(self.parameters) > SIMULATION_MAX_PARAMS:
            raise ValueError(
                f"simulation_slider allows at most {SIMULATION_MAX_PARAMS} parameters "
                f"(got {len(self.parameters)})"
            )

        names = [param.name for param in self.parameters]
        if len(set(names)) != len(names):
            raise ValueError("simulation_slider parameter names must be unique")
        expected = SIMULATION_PARAM_NAMES[self.sim_kind]
        if sorted(names) != sorted(expected):
            raise ValueError(
                f"simulation_slider sim_kind '{self.sim_kind}' requires parameters "
                f"{list(expected)} (got {names})"
            )

        for param in self.parameters:
            for field_name, value in (
                ("min", param.min),
                ("max", param.max),
                ("default", param.default),
            ):
                if not math.isfinite(value):
                    raise ValueError(
                        f"simulation_slider parameter '{param.name}' {field_name} must be finite"
                    )
            if not (param.min <= param.default <= param.max):
                raise ValueError(
                    f"simulation_slider parameter '{param.name}' must satisfy min <= default <= max"
                )
            if param.step is not None and (not math.isfinite(param.step) or param.step <= 0):
                raise ValueError(
                    f"simulation_slider parameter '{param.name}' step must be a "
                    "finite positive number"
                )

        if self.x_range is not None:
            if not math.isfinite(self.x_range.min) or not math.isfinite(self.x_range.max):
                raise ValueError("simulation_slider x_range bounds must be finite")
            if self.x_range.min >= self.x_range.max:
                raise ValueError("simulation_slider x_range must satisfy min < max")

        return self


class _ArtifactEnvelopeBase(BaseModel):
    """Shared strict-envelope fields + version/text_fallback validation."""

    model_config = ConfigDict(extra="forbid")

    artifact_version: int
    title: str
    caption: str | None = None
    text_fallback: str = Field(min_length=1)
    provenance: ArtifactProvenanceOutput

    @field_validator("artifact_version")
    @classmethod
    def _check_version(cls, value: int) -> int:
        if value != 1:
            raise ValueError("artifact_version must be 1")
        return value

    @field_validator("text_fallback")
    @classmethod
    def _check_text_fallback(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text_fallback is required and must be non-empty")
        return value


class WorkedExampleEnvelope(_ArtifactEnvelopeBase):
    kind: Literal["worked_example"]
    data: WorkedExampleData


class ComparisonCardEnvelope(_ArtifactEnvelopeBase):
    kind: Literal["comparison_card"]
    data: ComparisonCardData


class TimelineEnvelope(_ArtifactEnvelopeBase):
    kind: Literal["timeline"]
    data: TimelineData


class MiniGraphEnvelope(_ArtifactEnvelopeBase):
    kind: Literal["mini_graph"]
    data: MiniGraphData


class SimulationSliderEnvelope(_ArtifactEnvelopeBase):
    kind: Literal["simulation_slider"]
    data: SimulationSliderData


# Discriminated strict envelope. Parse via the TypeAdapter in the service.
ArtifactEnvelopeOutput = Annotated[
    WorkedExampleEnvelope
    | ComparisonCardEnvelope
    | TimelineEnvelope
    | MiniGraphEnvelope
    | SimulationSliderEnvelope,
    Field(discriminator="kind"),
]


# ---------------------------------------------------------------------------
# Lenient read schema (tolerant, versioned) returned by the API.
# ---------------------------------------------------------------------------


class ArtifactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    trail_id: uuid.UUID
    concept_id: uuid.UUID | None = None
    artifact_type: str
    title: str
    visibility: str
    # Stored validated envelope dict. Read from the ORM ``payload_json`` column.
    payload: dict = Field(validation_alias=AliasChoices("payload", "payload_json"))
    created_at: datetime


class ArtifactListResponse(BaseModel):
    artifacts: list[ArtifactRead]


class ArtifactBuildRequest(BaseModel):
    """On-demand artifact build request.

    ``concept_id`` is optional: when omitted the artifact is trail-level. The
    backend owns generation/persistence; the request only names the target.
    """

    kind: ArtifactKind
    concept_id: uuid.UUID | None = None
    force_new: bool = False
