"use client";

import { useRef, useMemo, useState, useEffect, useCallback } from "react";
import { LayoutControls } from "@/components/sigma-graph/layout-controls";
import { StableSigmaContainer } from "@/components/sigma-graph/stable-sigma-container";
import "@react-sigma/core/lib/style.css";
import type { GraphSubgraphNode, GraphSubgraphEdge } from "@/lib/api/types";
import { buildGraphologyGraph } from "@/lib/graph/transform";
import { buildSearchIndex, searchNodes } from "@/lib/graph/search";
import { DEFAULT_SIGMA_SETTINGS } from "@/lib/graph/sigma-settings";
import { useGraphTheme } from "@/lib/graph/hooks/use-graph-theme";
import { createDrawNodeHover } from "@/lib/graph/draw-hover";
import { GraphReducers } from "@/components/sigma-graph/graph-reducers";
import { GraphFlash } from "@/components/sigma-graph/graph-flash";
import { GraphLayout } from "@/components/sigma-graph/graph-layout";
import type { LayoutType } from "@/components/sigma-graph/graph-layout";
import { GraphEvents } from "@/components/sigma-graph/graph-events";
import { CameraControls } from "@/components/sigma-graph/camera-controls";
import { GraphSkeleton } from "@/components/sigma-graph/graph-skeleton";
import { EmptyState } from "@/components/sigma-graph/empty-state";
import { GraphLegend } from "@/components/sigma-graph/graph-legend";
import { StatusBar } from "@/components/sigma-graph/status-bar";
import { SettingsPanel } from "@/components/sigma-graph/settings-panel";
import { ExpandPruneControls } from "@/components/sigma-graph/expand-prune-controls";
import { GraphSettingsProvider, useGraphSettings } from "@/lib/graph/settings-store";

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
  isLoading?: boolean;
  /** Hide layout controls, camera, settings panel, legend, status bar */
  compact?: boolean;
  activeChatNodeKeys?: Set<string>;
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
export default function SigmaGraph(props: Props) {
  return (
    <GraphSettingsProvider>
      <SigmaGraphInner {...props} />
    </GraphSettingsProvider>
  );
}

function SigmaGraphInner({
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
  isLoading,
  compact,
  activeChatNodeKeys,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [layout, setLayout] = useState<LayoutType>("forceatlas2");
  const [isLayoutRunning, setIsLayoutRunning] = useState(false);
  const settings = useGraphSettings();
  const graphTheme = useGraphTheme();
  const flashRef = useRef(false);

  // Sync layout state when settings change
  useEffect(() => {
    setLayout(settings.defaultLayout as LayoutType);
  }, [settings.defaultLayout]);

  // Merge user settings + theme colors into Sigma renderer settings
  const sigmaSettings = useMemo(
    () => ({
      ...DEFAULT_SIGMA_SETTINGS,
      renderLabels: settings.showLabels,
      labelDensity: settings.labelDensity,
      renderEdgeLabels: settings.showEdgeLabels,
      labelColor: { color: graphTheme.labelColor },
      defaultEdgeColor: graphTheme.defaultEdgeColor,
      defaultNodeColor: graphTheme.defaultNodeColor,
      defaultDrawNodeHover: createDrawNodeHover(graphTheme.hoverBackgroundColor, graphTheme.hoverShadowColor),
    }),
    [settings.showLabels, settings.labelDensity, settings.showEdgeLabels, graphTheme],
  );

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

  // UXG.8: keyboard shortcuts (active when container is focused or hovered)
  const isHovered = useRef(false);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (!isHovered.current && !containerRef.current?.contains(document.activeElement)) return;
    // Ignore when typing in inputs
    const tag = (e.target as HTMLElement)?.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

    switch (e.key) {
      case "+":
      case "=":
        e.preventDefault();
        containerRef.current?.querySelector<HTMLButtonElement>("[aria-label='Zoom in']")?.click();
        break;
      case "-":
        e.preventDefault();
        containerRef.current?.querySelector<HTMLButtonElement>("[aria-label='Zoom out']")?.click();
        break;
      case "r":
        e.preventDefault();
        containerRef.current?.querySelector<HTMLButtonElement>("[aria-label='Reset view']")?.click();
        break;
      case "f":
        e.preventDefault();
        containerRef.current?.querySelector<HTMLButtonElement>("[aria-label='Toggle fullscreen']")?.click();
        break;
    }
  }, [containerRef]);

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  if (isLoading && nodes.length === 0) {
    return <GraphSkeleton />;
  }
  if (!isLoading && nodes.length === 0) {
    return <EmptyState />;
  }

  return (
    <div
      ref={containerRef}
      tabIndex={0}
      onMouseEnter={() => { isHovered.current = true; }}
      onMouseLeave={() => { isHovered.current = false; }}
      style={{
        width: width ?? "100%",
        height: height ?? "100%",
        minHeight: 200,
        position: "relative",
        outline: "none",
        animation: "fadeIn 0.3s ease-in",
      }}
    >
      <StableSigmaContainer
        graph={graph}
        style={{ width: "100%", height: "100%", background: "var(--bg)" }}
        settings={sigmaSettings}
      >
        <GraphLayout layout={layout} isRunning={isLayoutRunning} onAutoStop={() => setIsLayoutRunning(false)} />
        <GraphReducers
          selectedId={selectedId}
          hoveredNode={hoveredNode}
          searchMatchKeys={searchMatchKeys}
          hasSearchQuery={!!searchHighlight?.trim()}
          highlightNeighbors={settings.highlightNeighbors}
          theme={graphTheme}
          activeChatKeys={activeChatNodeKeys}
          flashRef={flashRef}
        />
        <GraphFlash
          active={(activeChatNodeKeys?.size ?? 0) > 0}
          flashRef={flashRef}
        />
        <GraphEvents
          onSelect={onSelect}
          onBackgroundClick={onBackgroundClick}
          onHoverNode={setHoveredNode}
          focusNodeId={focusNodeId}
          onResetViewReady={onResetViewReady}
        />
        {!compact && <CameraControls containerRef={containerRef} />}
        {!compact && <ExpandPruneControls selectedId={selectedId} />}
      </StableSigmaContainer>
      {!compact && (
        <LayoutControls
          layout={layout}
          onLayoutChange={setLayout}
          isRunning={isLayoutRunning}
          onIsRunningChange={setIsLayoutRunning}
        />
      )}
      {!compact && settings.showLegend && <GraphLegend />}
      {!compact && settings.showStatusBar && (
        <StatusBar nodes={nodes} edges={edges} selectedId={selectedId} filteredTiers={filteredTiers} />
      )}
      {!compact && <SettingsPanel onLayoutChange={setLayout} />}
    </div>
  );
}
