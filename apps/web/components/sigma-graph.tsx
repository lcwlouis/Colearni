"use client";

import { useRef, useMemo } from "react";
import { SigmaContainer } from "@react-sigma/core";
import "@react-sigma/core/lib/style.css";
import type { GraphSubgraphNode, GraphSubgraphEdge } from "@/lib/api/types";
import { buildGraphologyGraph } from "@/lib/graph/transform";
import { DEFAULT_SIGMA_SETTINGS } from "@/lib/graph/constants";

// --- Same props interface as ConceptGraph (concept-graph.tsx) ---
type Props = {
  nodes: GraphSubgraphNode[];
  edges: GraphSubgraphEdge[];
  selectedId?: number;
  onSelect: (conceptId: number) => void;
  onBackgroundClick?: () => void;
  width?: number;
  height?: number;
  focusNodeId?: number | null;
  searchHighlight?: string;
  onResetViewReady?: (resetFn: () => void) => void;
  filteredTiers?: ReadonlySet<string>;
};

/**
 * Sigma.js-based graph visualisation — drop-in replacement for ConceptGraph.
 *
 * UXG.1: scaffold only — renders an empty Sigma canvas.
 * Future slices will add:
 *   UXG.2  – node/edge population, mastery colours, tier sizing
 *   UXG.3  – ForceAtlas2 layout
 *   UXG.4  – selection, focus-mode, search highlight
 *   UXG.5  – drag, zoom-to-fit, reset-view callback
 */
export default function SigmaGraph({
  nodes,
  edges,
  selectedId,
  onSelect,
  onBackgroundClick,
  width,
  height,
  focusNodeId,
  searchHighlight,
  onResetViewReady,
  filteredTiers,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Build graphology instance from API data (UXG.2)
  const graph = useMemo(
    () => buildGraphologyGraph(nodes, edges, filteredTiers),
    [nodes, edges, filteredTiers],
  );

  // TODO (UXG.3): wire ForceAtlas2 layout
  // TODO (UXG.4): handle selectedId, focusNodeId, searchHighlight
  // TODO (UXG.5): expose onResetViewReady, drag behaviour, onBackgroundClick

  // Suppress unused-variable warnings until future slices consume these props
  void selectedId;
  void onSelect;
  void onBackgroundClick;
  void focusNodeId;
  void searchHighlight;
  void onResetViewReady;

  if (nodes.length === 0) {
    return <p style={{ color: "var(--muted)" }}>No graph data yet.</p>;
  }

  return (
    <div
      ref={containerRef}
      style={{
        width: width ?? "100%",
        height: height ?? "100%",
        minHeight: 200,
      }}
    >
      <SigmaContainer
        graph={graph}
        style={{ width: "100%", height: "100%" }}
        settings={DEFAULT_SIGMA_SETTINGS}
      />
    </div>
  );
}
