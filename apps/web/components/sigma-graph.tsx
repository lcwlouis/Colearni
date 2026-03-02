"use client";

import { useRef, useMemo, useState } from "react";
import { SigmaContainer } from "@react-sigma/core";
import "@react-sigma/core/lib/style.css";
import type { GraphSubgraphNode, GraphSubgraphEdge } from "@/lib/api/types";
import { buildGraphologyGraph } from "@/lib/graph/transform";
import { buildSearchIndex, searchNodes } from "@/lib/graph/search";
import { DEFAULT_SIGMA_SETTINGS } from "@/lib/graph/sigma-settings";
import { GraphReducers } from "@/components/sigma-graph/graph-reducers";
import { GraphLayout } from "@/components/sigma-graph/graph-layout";
import type { LayoutType } from "@/components/sigma-graph/graph-layout";
import { GraphEvents } from "@/components/sigma-graph/graph-events";

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
 * UXG.2: node/edge population, mastery colours, tier sizing.
 * UXG.3: core rendering with visual programs and reducers.
 * Future slices will add:
 *   UXG.4  – ForceAtlas2 layout ✅
 *   UXG.5  – interactions: click, hover, drag, zoom-to-node, reset-view ✅
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
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [layout] = useState<LayoutType>("forceatlas2");

  // Build graphology instance from API data (UXG.2)
  const graph = useMemo(
    () => buildGraphologyGraph(nodes, edges, filteredTiers),
    [nodes, edges, filteredTiers],
  );

  // UXG.6: MiniSearch fuzzy graph search
  const searchIndex = useMemo(() => buildSearchIndex(nodes), [nodes]);
  const searchMatchKeys = useMemo(
    () => searchNodes(searchIndex, searchHighlight || ""),
    [searchIndex, searchHighlight],
  );

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
      >
        <GraphLayout layout={layout} />
        <GraphReducers
          selectedId={selectedId}
          hoveredNode={hoveredNode}
          searchMatchKeys={searchMatchKeys}
          hasSearchQuery={!!searchHighlight?.trim()}
        />
        <GraphEvents
          onSelect={onSelect}
          onBackgroundClick={onBackgroundClick}
          onHoverNode={setHoveredNode}
          focusNodeId={focusNodeId}
          onResetViewReady={onResetViewReady}
        />
      </SigmaContainer>
    </div>
  );
}
