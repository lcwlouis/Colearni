// Frontend types for the LOCKED artifact ENVELOPE contract shared with the
// backend (see docs/REBUILD_PLAN.md → Phase 15a / 15e). These mirror the
// versioned lenient READ schema: fields may be missing on malformed data, so
// the renderer must always be able to degrade to `text_fallback`.

export type ArtifactKind =
  | "worked_example"
  | "comparison_card"
  | "timeline"
  | "mini_graph"
  | "simulation_slider";

export type ArtifactVisibility = "local_only" | "source_derived";

export interface ArtifactCitation {
  source_revision_id: string;
  quote: string | null;
  line_start: number | null;
  line_end: number | null;
}

export interface ArtifactProvenance {
  source_ids: string[];
  visibility: ArtifactVisibility;
  citations: ArtifactCitation[];
}

export interface WorkedExampleStep {
  label: string;
  detail: string;
}

export interface WorkedExampleData {
  steps: WorkedExampleStep[];
  final_answer: string | null;
}

export interface ComparisonCriterion {
  label: string;
  // One value per item in `items`; length must equal `items.length`.
  values: string[];
}

export interface ComparisonCardData {
  items: string[];
  criteria: ComparisonCriterion[];
}

export interface TimelineEvent {
  label: string;
  // Free-form date/ordering label (e.g. "1969", "Step 2").
  when: string;
  note: string | null;
}

export interface TimelineData {
  events: TimelineEvent[];
}

export interface MiniGraphNode {
  id: string;
  label: string;
}

export interface MiniGraphEdge {
  source: string;
  target: string;
  label: string | null;
}

export interface MiniGraphData {
  nodes: MiniGraphNode[];
  edges: MiniGraphEdge[];
}

// simulation_slider — interactive but TRUSTED-TEMPLATE (closed enum + hardcoded
// compute). `precomputed` is the backend-owned oracle/render hint.
export type SimKind = "linear" | "quadratic" | "exponential" | "supply_demand";

export interface SimulationParameter {
  name: string;
  label: string;
  min: number;
  max: number;
  default: number;
  step: number | null;
}

export interface SimulationRange {
  min: number;
  max: number;
}

export interface SimulationPoint {
  x: number;
  y: number;
}

export interface SimulationBounds {
  min: number;
  max: number;
}

export interface SimulationPrecomputed {
  at_defaults: SimulationPoint[];
  y_bounds: SimulationBounds;
}

export interface SimulationSliderData {
  sim_kind: SimKind;
  parameters: SimulationParameter[];
  x_label: string;
  y_label: string;
  x_range: SimulationRange | null;
  prompt: string;
  precomputed: SimulationPrecomputed | null;
}

export type ArtifactData =
  | WorkedExampleData
  | ComparisonCardData
  | TimelineData
  | MiniGraphData
  | SimulationSliderData;

export interface ArtifactEnvelope<TData = ArtifactData> {
  artifact_version: number;
  kind: ArtifactKind;
  title: string;
  caption: string | null;
  // REQUIRED on the wire — the universal safe degrade target.
  text_fallback: string;
  provenance: ArtifactProvenance;
  data: TData;
}

export type WorkedExampleEnvelope = ArtifactEnvelope<WorkedExampleData>;
export type ComparisonCardEnvelope = ArtifactEnvelope<ComparisonCardData>;
export type TimelineEnvelope = ArtifactEnvelope<TimelineData>;
export type MiniGraphEnvelope = ArtifactEnvelope<MiniGraphData>;
export type SimulationSliderEnvelope = ArtifactEnvelope<SimulationSliderData>;

// Lenient READ row returned by the artifact API (mirrors
// backend.app.schemas.artifact.ArtifactRead). `payload` is the stored validated
// envelope; it is typed as the envelope but must still be treated defensively by
// the renderer, which degrades to `text_fallback` on malformed data.
export interface ArtifactRead {
  id: string;
  workspace_id: string;
  trail_id: string;
  concept_id: string | null;
  artifact_type: string;
  title: string;
  visibility: string;
  payload: ArtifactEnvelope;
  created_at: string;
}
