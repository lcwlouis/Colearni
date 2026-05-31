"use client";

import { Component, type ReactNode } from "react";

import { ComparisonCard } from "@/components/artifacts/ComparisonCard";
import { ArtifactTextFallback } from "@/components/artifacts/ArtifactTextFallback";
import { MiniGraphCard } from "@/components/artifacts/MiniGraphCard";
import { SimulationSliderCard } from "@/components/artifacts/SimulationSliderCard";
import { TimelineCard } from "@/components/artifacts/TimelineCard";
import { WorkedExampleCard } from "@/components/artifacts/WorkedExampleCard";
import type { ArtifactEnvelope, ArtifactKind } from "@/lib/artifacts";

// The kind -> component REGISTRY. This map is the SINGLE extension point: later
// templates (timeline, mini_graph, simulation_slider, ...) are added here and
// nowhere else. Every entry receives the full envelope and is responsible for
// degrading to `text_fallback` on invalid data of its own kind.
const ARTIFACT_REGISTRY: Record<
  ArtifactKind,
  (props: { envelope: ArtifactEnvelope }) => ReactNode
> = {
  worked_example: WorkedExampleCard,
  comparison_card: ComparisonCard,
  timeline: TimelineCard,
  mini_graph: MiniGraphCard,
  simulation_slider: SimulationSliderCard,
};

// Function components cannot catch render errors, so a class-based boundary is
// required. On ANY thrown render error it degrades to `text_fallback`, mirroring
// the Mermaid `catch -> textContent` path in markdown-text.tsx.
export class ArtifactErrorBoundary extends Component<
  { fallbackText?: string | null; children: ReactNode },
  { hasError: boolean }
> {
  constructor(props: { fallbackText?: string | null; children: ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return <ArtifactTextFallback text={this.props.fallbackText} />;
    }
    return this.props.children;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/**
 * Public entry point for rendering a validated artifact envelope.
 *
 * Given an `envelope` of UNKNOWN shape, it:
 *  1. Reads `text_fallback` defensively (used as the universal degrade target).
 *  2. Dispatches on `envelope.kind` via {@link ARTIFACT_REGISTRY}.
 *  3. Wraps the chosen template in an error boundary.
 *
 * On any of: missing/unknown `kind`, a non-object envelope, or a thrown render
 * error, it renders {@link ArtifactTextFallback}.
 */
export function ArtifactRenderer({ envelope }: { envelope: unknown }) {
  if (!isRecord(envelope)) {
    return <ArtifactTextFallback text={null} />;
  }

  const fallbackText =
    typeof envelope.text_fallback === "string" ? envelope.text_fallback : null;

  const kind = envelope.kind;
  const Component =
    typeof kind === "string"
      ? ARTIFACT_REGISTRY[kind as ArtifactKind]
      : undefined;

  if (!Component) {
    return <ArtifactTextFallback text={fallbackText} />;
  }

  return (
    <ArtifactErrorBoundary fallbackText={fallbackText}>
      <Component envelope={envelope as unknown as ArtifactEnvelope} />
    </ArtifactErrorBoundary>
  );
}
