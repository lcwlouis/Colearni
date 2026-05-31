"use client";

import "@xyflow/react/dist/style.css";

import {
  type MouseEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Background,
  Controls,
  type Edge,
  MarkerType,
  MiniMap,
  type Node,
  Panel,
  ReactFlow,
  type ReactFlowInstance,
} from "@xyflow/react";
import {
  Crosshair,
  Eye,
  Map as MapIcon,
  Maximize2,
  SlidersHorizontal,
} from "lucide-react";

import { getConcept } from "@/lib/api";
import type {
  ConceptDetail,
  ConceptLevel,
  ConceptNode,
  MasteryRecord,
  MasteryStatus,
  Trail,
  TrailGraph as TrailGraphData,
} from "@/lib/types";

import { ConceptPanel } from "./ConceptPanel";
import {
  type GraphLayoutMode,
  type GraphPosition,
  layoutGraph,
} from "./graphLayout";
import {
  buildFocusSet,
  edgeColor,
  edgeStyleFor,
  isFocusedEdge,
  isFocusedNode,
  masteryColors,
  masteryStatusFor,
  nodeStyleFor,
} from "./graphStyles";

const levels: ConceptLevel[] = ["umbrella", "topic", "subtopic", "granular"];
const layoutModes: Array<{ value: GraphLayoutMode; label: string }> = [
  { value: "freeform", label: "Freeform" },
  { value: "hierarchy", label: "Hierarchy" },
  { value: "radial", label: "Radial" },
  { value: "compact", label: "Compact" },
];
const EDGE_LABEL_MIN_ZOOM = 0.78;
// Comfortable, readable zoom used whenever the view recenters on a single
// concept (selection, focus, layout/mode changes). Keep this in sync with the
// "Focus selected" inspect control so focusing never lands on an unreadable,
// zoomed-out view.
const READABLE_FOCUS_ZOOM = 1;
const READABLE_FOCUS_ZOOM_MOBILE = 0.92;
// How long the recommended concept pulses to draw attention before settling
// back to a normal node, if the learner hasn't engaged with the graph yet.
const RECOMMEND_FLASH_MS = 5200;

type GraphViewport = {
  x: number;
  y: number;
  zoom: number;
};

type ViewportTransition = { type: "close"; viewport: GraphViewport };

interface TrailGraphProps {
  workspaceId: string;
  trail: Trail;
  graph: TrailGraphData;
  masterySummary: {
    total: number;
    not_started: number;
    learning: number;
    needs_review: number;
    mastered: number;
  };
  /** When set, this concept is opened automatically once the graph is ready. */
  initialConceptId?: string | null;
  /** When changed to a non-null value, imperatively open that concept panel. */
  focusConceptId?: string | null;
  recommendedConceptId?: string | null;
  onMasteryUpdated?: (
    conceptId: string,
    update: { status: MasteryStatus; score: number },
  ) => void;
}

type GraphMode = "learn" | "inspect";

export function TrailGraph({
  workspaceId,
  trail,
  graph,
  masterySummary,
  initialConceptId,
  focusConceptId,
  recommendedConceptId,
  onMasteryUpdated,
}: TrailGraphProps) {
  const [isMobileViewport, setIsMobileViewport] = useState(false);
  const [mode, setMode] = useState<GraphMode>("learn");
  const [query, setQuery] = useState("");
  const [visibleLevels, setVisibleLevels] = useState<Set<ConceptLevel>>(
    () => new Set(levels),
  );
  const [layoutMode, setLayoutMode] = useState<GraphLayoutMode>("freeform");
  const [toolsExpanded, setToolsExpanded] = useState(false);
  const [legendExpanded, setLegendExpanded] = useState(false);
  const [neighborsOnly, setNeighborsOnly] = useState(false);
  const [showEdgeLabels, setShowEdgeLabels] = useState(true);
  const [edgeLabelsZoomedIn, setEdgeLabelsZoomedIn] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [positions, setPositions] = useState<Map<string, GraphPosition>>(
    new Map(),
  );
  const [focusRevision, setFocusRevision] = useState(0);
  const [flow, setFlow] = useState<ReactFlowInstance | null>(null);
  const [detail, setDetail] = useState<ConceptDetail | null>(null);
  const [panelError, setPanelError] = useState("");
  const lastViewState = useRef({
    layoutMode,
    mode,
    selectedNodeId,
    visibleCount: 0,
  });
  const graphFrameRef = useRef<HTMLDivElement | null>(null);
  const viewportRef = useRef<GraphViewport | null>(null);
  const overviewViewportRef = useRef<GraphViewport | null>(null);
  const pendingViewportTransitionRef = useRef<ViewportTransition | null>(null);
  const pendingFocusRef = useRef<{
    conceptId: string;
    zoom: number;
  } | null>(null);
  const wasDetailOpenRef = useRef(false);
  const conceptLoadRequestRef = useRef(0);

  const selectedNode = useMemo(
    () => graph.nodes.find((node) => node.id === selectedNodeId) ?? null,
    [graph.nodes, selectedNodeId],
  );
  const focusSet = useMemo(
    () => buildFocusSet(graph.edges, selectedNodeId),
    [graph.edges, selectedNodeId],
  );
  const statusCounts = useMemo(
    () => countMasteryStatuses(graph.nodes, graph.mastery),
    [graph.mastery, graph.nodes],
  );

  // The recommended concept gets a brief, tasteful attention pulse when the
  // graph first loads instead of a persistent highlight. It stops the moment
  // the learner engages (selects any concept) or after a short timeout. The
  // recommendation is stable for the page's lifetime, so a single timeout that
  // arms once the id is available is sufficient.
  const [flashTimedOut, setFlashTimedOut] = useState(false);
  useEffect(() => {
    if (!recommendedConceptId || flashTimedOut) {
      return;
    }
    const timer = window.setTimeout(
      () => setFlashTimedOut(true),
      RECOMMEND_FLASH_MS,
    );
    return () => window.clearTimeout(timer);
  }, [recommendedConceptId, flashTimedOut]);
  const flashConceptId =
    !flashTimedOut && !selectedNodeId ? (recommendedConceptId ?? null) : null;

  const isLearnMode = mode === "learn";
  // In Learn Mode, focus the selected neighborhood to reduce clutter even if
  // the user hasn't toggled the explicit power-user "Neighbors only" filter.
  const effectiveNeighborsOnly =
    neighborsOnly || (isLearnMode && Boolean(selectedNodeId));
  const effectiveShowEdgeLabels = showEdgeLabels && edgeLabelsZoomedIn;
  const mobileCardHeightPx = 104;
  const controlsBottomOffset =
    isMobileViewport && detail ? mobileCardHeightPx + 16 : 16;

  const visibleNodeIds = useMemo(() => {
    const levelVisible = new Set(
      graph.nodes
        .filter((node) => visibleLevels.has(node.concept_level))
        .map((node) => node.id),
    );
    if (!effectiveNeighborsOnly || !selectedNodeId) {
      return levelVisible;
    }
    return new Set(
      [...levelVisible].filter((nodeId) => isFocusedNode(nodeId, focusSet)),
    );
  }, [
    effectiveNeighborsOnly,
    focusSet,
    graph.nodes,
    selectedNodeId,
    visibleLevels,
  ]);

  const computedPositions = useMemo(
    () =>
      layoutGraph({
        mode: layoutMode,
        nodes: graph.nodes.filter((node) => visibleNodeIds.has(node.id)),
        edges: graph.edges.filter(
          (edge) =>
            visibleNodeIds.has(edge.source_node_id) &&
            visibleNodeIds.has(edge.target_node_id),
        ),
        selectedNodeId,
        existingPositions: positions,
      }),
    [
      graph.edges,
      graph.nodes,
      layoutMode,
      positions,
      selectedNodeId,
      visibleNodeIds,
    ],
  );

  const flowNodes = useMemo(
    () =>
      buildFlowNodes(
        graph.nodes,
        visibleNodeIds,
        computedPositions,
        query,
        focusSet,
        graph.mastery,
        flashConceptId,
      ),
    [
      computedPositions,
      focusSet,
      graph.mastery,
      graph.nodes,
      query,
      flashConceptId,
      visibleNodeIds,
    ],
  );
  const flowEdges = useMemo(
    () =>
      buildFlowEdges(
        graph.edges,
        visibleNodeIds,
        focusSet,
        effectiveShowEdgeLabels,
      ),
    [effectiveShowEdgeLabels, focusSet, graph.edges, visibleNodeIds],
  );

  const queueFocusConcept = useCallback((conceptId: string, zoom: number) => {
    pendingFocusRef.current = { conceptId, zoom };
    setFocusRevision((current) => current + 1);
  }, []);

  const updateEdgeLabelZoom = useCallback((zoom: number) => {
    const next = zoom >= EDGE_LABEL_MIN_ZOOM;
    setEdgeLabelsZoomedIn((current) => (current === next ? current : next));
  }, []);

  const handleViewportChange = useCallback(
    (viewport: GraphViewport) => {
      viewportRef.current = viewport;
      updateEdgeLabelZoom(viewport.zoom);
    },
    [updateEdgeLabelZoom],
  );

  const fitVisibleGraph = useCallback(
    (padding: number) => {
      window.requestAnimationFrame(() => {
        if (!flow) {
          return;
        }
        void flow.fitView({ padding, duration: 220 }).then(() => {
          viewportRef.current = flow.getViewport();
          updateEdgeLabelZoom(flow.getZoom());
        });
      });
    },
    [flow, updateEdgeLabelZoom],
  );

  useEffect(() => {
    if (!flow || flowNodes.length === 0) {
      return;
    }

    const previous = lastViewState.current;
    const layoutChanged = previous.layoutMode !== layoutMode;
    const modeChanged = previous.mode !== mode;
    const selectionCleared =
      previous.selectedNodeId !== null && selectedNodeId === null;
    const visibleCountChanged = previous.visibleCount !== flowNodes.length;
    lastViewState.current = {
      layoutMode,
      mode,
      selectedNodeId,
      visibleCount: flowNodes.length,
    };

    if (selectedNodeId) {
      if (layoutChanged || modeChanged) {
        queueFocusConcept(
          selectedNodeId,
          window.innerWidth < 768
            ? READABLE_FOCUS_ZOOM_MOBILE
            : READABLE_FOCUS_ZOOM,
        );
      }
      return;
    }

    if (
      selectionCleared ||
      pendingViewportTransitionRef.current?.type === "close"
    ) {
      return;
    }

    if (layoutChanged || modeChanged || visibleCountChanged) {
      fitVisibleGraph(window.innerWidth < 768 ? 0.18 : 0.24);
    }
  }, [
    flow,
    flowNodes.length,
    layoutMode,
    mode,
    selectedNodeId,
    computedPositions,
    fitVisibleGraph,
    queueFocusConcept,
  ]);

  async function openConcept(
    conceptId: string,
    options?: { focusViewport?: boolean; preserveOverview?: boolean },
  ) {
    const detailWasOpen = Boolean(detail);
    const preserveOverview = options?.preserveOverview ?? !detailWasOpen;
    if (preserveOverview && !detailWasOpen) {
      const currentViewport = flow?.getViewport() ?? viewportRef.current;
      if (currentViewport) {
        overviewViewportRef.current = currentViewport;
      }
    }

    const requestId = ++conceptLoadRequestRef.current;
    setSelectedNodeId(conceptId);
    setPanelError("");
    try {
      const conceptDetail = await getConcept(workspaceId, trail.id, conceptId);
      if (requestId !== conceptLoadRequestRef.current) {
        return;
      }
      setDetail(conceptDetail);
      // Recenter on the selected concept at a readable zoom. Previously this
      // reused the current (often fully-zoomed-out "overview") zoom, which left
      // the focused node tiny and unreadable. Clamp up to the comfortable
      // focus zoom, but never zoom the learner back OUT if they were already
      // closer in.
      const readableZoom =
        window.innerWidth < 768
          ? READABLE_FOCUS_ZOOM_MOBILE
          : READABLE_FOCUS_ZOOM;
      const currentZoom =
        overviewViewportRef.current?.zoom ??
        flow?.getZoom() ??
        viewportRef.current?.zoom ??
        readableZoom;
      const nextZoom = options?.focusViewport
        ? readableZoom
        : Math.max(currentZoom, readableZoom);
      queueFocusConcept(conceptId, nextZoom);
    } catch (exc) {
      if (requestId !== conceptLoadRequestRef.current) {
        return;
      }
      if (!detailWasOpen) {
        overviewViewportRef.current = null;
      }
      setPanelError(
        exc instanceof Error ? exc.message : "Could not load concept",
      );
    }
  }

  // Auto-open a concept if the page was opened with `?concept=<id>`.
  const autoOpenRef = useRef(false);
  useEffect(() => {
    if (autoOpenRef.current || !initialConceptId) {
      return;
    }
    if (graph.nodes.some((node) => node.id === initialConceptId)) {
      autoOpenRef.current = true;
      // Defer past render so we don't trigger cascading setState in this effect.
      queueMicrotask(() => {
        void openConcept(initialConceptId, {
          focusViewport: true,
          preserveOverview: false,
        });
      });
    }
    // openConcept depends on stable props; safe to omit from deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph.nodes, initialConceptId]);

  // Imperatively open a concept when the parent requests it (e.g. "Focus concept" banner).
  // Unlike initialConceptId this fires every time focusConceptId changes to a non-null value.
  const lastFocusRef = useRef<string | null>(null);
  useEffect(() => {
    if (!focusConceptId || focusConceptId === lastFocusRef.current) {
      return;
    }
    if (graph.nodes.some((node) => node.id === focusConceptId)) {
      lastFocusRef.current = focusConceptId;
      queueMicrotask(() => {
        void openConcept(focusConceptId, {
          focusViewport: true,
          preserveOverview: false,
        });
      });
    }
    // openConcept is stable; safe to omit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusConceptId, graph.nodes]);

  function handleMasteryUpdated(
    conceptId: string,
    update: { status: MasteryStatus; score: number },
  ) {
    setDetail((prev) => {
      if (!prev || prev.concept.id !== conceptId) {
        return prev;
      }
      const updatedRecord: MasteryRecord = {
        ...prev.mastery,
        status: update.status,
        score: update.score,
        updated_at: new Date().toISOString(),
      };
      return { ...prev, mastery: updatedRecord };
    });
    onMasteryUpdated?.(conceptId, update);
  }

  function clearSelection() {
    conceptLoadRequestRef.current += 1;
    pendingFocusRef.current = null;
    if (detail && overviewViewportRef.current) {
      pendingViewportTransitionRef.current = {
        type: "close",
        viewport: overviewViewportRef.current,
      };
    }
    setSelectedNodeId(null);
    setDetail(null);
    setPanelError("");
  }

  function handleGraphSurfaceClick(event: MouseEvent<HTMLElement>) {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    if (
      target.closest(
        [
          ".react-flow__node",
          ".react-flow__edge",
          ".react-flow__panel",
          ".react-flow__controls",
          ".react-flow__minimap",
          ".react-flow__attribution",
        ].join(","),
      )
    ) {
      return;
    }
    if (target.closest(".react-flow")) {
      clearSelection();
    }
  }

  function handleSearchChange(value: string) {
    setQuery(value);
    const normalizedQuery = value.trim().toLowerCase();
    if (!normalizedQuery) {
      return;
    }
    const match = graph.nodes.find((node) =>
      node.title.toLowerCase().includes(normalizedQuery),
    );
    if (!match) {
      return;
    }
    setSelectedNodeId(match.id);
    setDetail(null);
    queueFocusConcept(match.id, READABLE_FOCUS_ZOOM);
  }

  function toggleLevel(level: ConceptLevel) {
    setVisibleLevels((current) => {
      const next = new Set(current);
      if (next.has(level)) {
        next.delete(level);
      } else {
        next.add(level);
      }
      return next;
    });
  }

  function setReadableZoom() {
    fitVisibleGraph(window.innerWidth < 768 ? 0.18 : 0.24);
  }

  function centerSelected() {
    if (!selectedNodeId) {
      fitVisibleGraph(0.24);
      return;
    }
    queueFocusConcept(selectedNodeId, READABLE_FOCUS_ZOOM);
  }

  function changeLayoutMode(mode: GraphLayoutMode) {
    setLayoutMode(mode);
  }

  function initializeFlow(instance: ReactFlowInstance) {
    setFlow(instance);
    handleViewportChange(instance.getViewport());
    window.requestAnimationFrame(() => {
      void instance
        .fitView({
          padding: window.innerWidth < 768 ? 0.14 : 0.22,
          duration: 180,
        })
        .then(() => handleViewportChange(instance.getViewport()));
    });
  }

  useEffect(() => {
    if (!flow || !selectedNodeId) {
      return;
    }
    const pending = pendingFocusRef.current;
    if (!pending || pending.conceptId !== selectedNodeId) {
      return;
    }
    const point = computedPositions.get(pending.conceptId);
    if (!point) {
      return;
    }
    pendingFocusRef.current = null;
    window.requestAnimationFrame(() => {
      void flow
        .setCenter(point.x + 110, point.y + 46, {
          zoom: pending.zoom,
          duration: 220,
        })
        .then(() => {
          viewportRef.current = flow.getViewport();
          updateEdgeLabelZoom(flow.getZoom());
        });
    });
  }, [computedPositions, flow, focusRevision, selectedNodeId, updateEdgeLabelZoom]);

  useEffect(() => {
    if (!flow) {
      return;
    }

    const detailOpen = Boolean(detail);
    const wasDetailOpen = wasDetailOpenRef.current;
    if (detailOpen === wasDetailOpen) {
      return;
    }
    wasDetailOpenRef.current = detailOpen;

    const transition = pendingViewportTransitionRef.current;
    if (!transition || detailOpen) {
      return;
    }

    window.requestAnimationFrame(() => {
      viewportRef.current = transition.viewport;
      void flow.setViewport(transition.viewport, { duration: 220 }).then(() => {
        handleViewportChange(flow.getViewport());
      });
      pendingViewportTransitionRef.current = null;
      overviewViewportRef.current = null;
    });
  }, [detail, flow, handleViewportChange]);

  const controlsWidthClass = detail
    ? "w-[min(94vw,680px)] md:w-[min(27vw,230px)] lg:w-[min(34vw,380px)] xl:w-[min(39vw,480px)]"
    : "w-[min(94vw,680px)] md:w-[min(66vw,720px)] lg:w-[min(54vw,720px)]";

  useEffect(() => {
    const mediaQuery = window.matchMedia("(max-width: 767px)");
    const handleChange = (event: MediaQueryListEvent) => {
      setIsMobileViewport(event.matches);
    };

    setIsMobileViewport(mediaQuery.matches);
    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, []);

  return (
    <section className="relative flex min-h-0 flex-1">
      <style>
        {`.react-flow__node:hover [data-node-hover-card] { display: block; }
          @keyframes colearni-node-flash {
            0% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.55); }
            70% { box-shadow: 0 0 0 16px rgba(37, 99, 235, 0); }
            100% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0); }
          }
          .colearni-node-flash::after {
            content: "";
            position: absolute;
            inset: -3px;
            border-radius: 11px;
            pointer-events: none;
            animation: colearni-node-flash 1.5s ease-out 3;
          }
          @media (prefers-reduced-motion: reduce) {
            .colearni-node-flash::after { animation: none; box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.45); }
          }`}
      </style>
      <div
        ref={graphFrameRef}
        data-testid="trail-graph-frame"
        className="w-full md:min-w-0 md:flex-1"
        style={
          isMobileViewport && detail
            ? { height: `calc(100% - ${mobileCardHeightPx}px)` }
            : { height: "100%" }
        }
        onClickCapture={handleGraphSurfaceClick}
      >
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          minZoom={0.12}
          onInit={initializeFlow}
          onMove={(_, viewport) => handleViewportChange(viewport)}
          onNodeClick={(_, node) => openConcept(node.id)}
          onNodeDoubleClick={(_, node) => openConcept(node.id)}
          onPaneClick={clearSelection}
          onNodeDragStop={(_, node) => {
            setLayoutMode("freeform");
            setPositions((current) => {
              const next = new Map(current);
              next.set(node.id, node.position);
              return next;
            });
          }}
          nodesDraggable
        >
          <Background color="#dbe3ee" gap={32} />
          {isLearnMode ? null : (
            <MiniMap
              className="hidden md:block"
              pannable
              zoomable
              nodeStrokeWidth={3}
              position="bottom-left"
              style={{ bottom: 16, left: 76, height: 118, width: 180 }}
            />
          )}
          <Controls
            position="bottom-left"
            style={{ bottom: controlsBottomOffset, left: 12 }}
          />
          <Panel position="top-left">
            <div
              className={`flex ${controlsWidthClass} flex-col gap-2 rounded-md border border-slate-200 bg-white/95 p-2 shadow-sm backdrop-blur md:gap-2.5 md:p-3`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-400">
                    Trail graph
                  </p>
                  <h1 className="truncate text-sm font-semibold text-slate-950 md:text-base">
                    {trail.title}
                  </h1>
                </div>
                <div className="shrink-0 text-right text-[11px] text-slate-500">
                  <div>{graph.nodes.length} concepts</div>
                  <div>{masterySummary.mastered} mastered</div>
                </div>
              </div>
              <div className="flex gap-2 md:items-center">
                <input
                  value={query}
                  onChange={(event) => handleSearchChange(event.target.value)}
                  placeholder="Search concepts"
                  className="h-8 min-w-0 flex-1 rounded-md border border-slate-300 px-2 text-xs outline-none focus:border-blue-500 md:h-9 md:px-3 md:text-sm"
                />
                <div
                  role="group"
                  aria-label="Graph mode"
                  className="inline-flex shrink-0 rounded-md border border-slate-200 bg-slate-100 p-0.5"
                >
                  {(["learn", "inspect"] as GraphMode[]).map((value) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setMode(value)}
                      aria-pressed={mode === value}
                      className={`h-7 rounded px-2 text-xs font-medium transition md:h-8 md:px-3 ${
                        mode === value
                          ? "bg-white text-blue-700 shadow-sm"
                          : "text-slate-600 hover:text-slate-900"
                      }`}
                    >
                      {value === "learn" ? "Learn" : "Inspect"}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {selectedNode ? (
                  <p className="text-xs font-medium text-blue-800">
                    Selected: {selectedNode.title}
                  </p>
                ) : (
                  <p className="text-xs text-slate-500">
                    {isLearnMode
                      ? "Tap a concept to see what it is and what to do next."
                      : "Select a node to highlight its connections."}
                  </p>
                )}
                {!isLearnMode ? (
                  <>
                    <ToolbarButton
                      icon={<SlidersHorizontal size={15} />}
                      label="Tools"
                      onClick={() => setToolsExpanded((current) => !current)}
                      active={toolsExpanded}
                    />
                    <ToolbarButton
                      icon={<MapIcon size={15} />}
                      label="Legend"
                      onClick={() => setLegendExpanded((current) => !current)}
                      active={legendExpanded}
                    />
                  </>
                ) : null}
              </div>
              {!isLearnMode && legendExpanded ? (
                <div>
                  <GraphLegendContent compact={false} />
                </div>
              ) : null}
              {!isLearnMode ? (
                <div
                  data-testid="inspect-tools"
                  className={`${toolsExpanded ? "grid" : "hidden"} gap-2 md:gap-3`}
                >
                  <div className="flex flex-wrap gap-2">
                    <ToolbarButton
                      icon={<Eye size={15} />}
                      label="Readable"
                      onClick={setReadableZoom}
                      subtle
                    />
                    <ToolbarButton
                      icon={<Maximize2 size={15} />}
                      label="Overview"
                      onClick={() =>
                        flow?.fitView({ padding: 0.2, duration: 220 })
                      }
                      subtle
                    />
                    <ToolbarButton
                      icon={<Crosshair size={15} />}
                      label="Focus selected"
                      onClick={centerSelected}
                      subtle
                    />
                  </div>
                  <div className="inline-flex w-fit flex-wrap gap-1 rounded-md border border-slate-200 bg-slate-100 p-1">
                    {layoutModes.map((modeOption) => (
                      <button
                        key={modeOption.value}
                        type="button"
                        onClick={() => changeLayoutMode(modeOption.value)}
                        aria-pressed={layoutMode === modeOption.value}
                        className={`h-8 rounded px-2 text-xs font-medium transition md:px-3 ${
                          layoutMode === modeOption.value
                            ? "bg-white text-blue-700 shadow-sm"
                            : "text-slate-600 hover:bg-white/70 hover:text-slate-900"
                        }`}
                      >
                        {modeOption.label}
                      </button>
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {levels.map((level) => (
                      <FilterPill
                        key={level}
                        active={visibleLevels.has(level)}
                        label={level}
                        onClick={() => toggleLevel(level)}
                      />
                    ))}
                    <FilterPill
                      active={neighborsOnly}
                      label="Neighbors only"
                      onClick={() => setNeighborsOnly((current) => !current)}
                    />
                    <FilterPill
                      active={showEdgeLabels}
                      label="Edge labels"
                      onClick={() => setShowEdgeLabels((current) => !current)}
                    />
                  </div>
                  {showEdgeLabels && !edgeLabelsZoomedIn ? (
                    <p className="text-xs text-slate-500">
                      Edge labels appear when you zoom in closer.
                    </p>
                  ) : null}
                  <div className="grid grid-cols-5 gap-1 text-xs text-slate-600 md:gap-2">
                    <Metric
                      label="Total"
                      value={statusCounts.total || masterySummary.total}
                    />
                    <Metric label="New" value={statusCounts.not_started} />
                    <Metric label="Learning" value={statusCounts.learning} />
                    <Metric label="Review" value={statusCounts.needs_review} />
                    <Metric label="Mastered" value={statusCounts.mastered} />
                  </div>
                </div>
              ) : null}
            </div>
          </Panel>
        </ReactFlow>
      </div>
      {panelError ? (
        <div className="absolute bottom-4 left-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {panelError}
        </div>
      ) : null}
      {detail ? (
        <ConceptPanel
          workspaceId={workspaceId}
          trailId={trail.id}
          detail={detail}
          onClose={clearSelection}
          onSelectConcept={openConcept}
          onMasteryUpdated={handleMasteryUpdated}
        />
      ) : null}
    </section>
  );
}

function buildFlowNodes(
  concepts: ConceptNode[],
  visibleNodeIds: Set<string>,
  positions: Map<string, GraphPosition>,
  query: string,
  focusSet: ReturnType<typeof buildFocusSet>,
  masteryByConcept: TrailGraphData["mastery"],
  flashConceptId?: string | null,
): Node[] {
  const normalizedQuery = query.trim().toLowerCase();

  return concepts
    .filter((concept) => visibleNodeIds.has(concept.id))
    .map((concept, index) => {
      const point = positions.get(concept.id) ?? {
        x: 120 + (index % 5) * 260,
        y: 120 + Math.floor(index / 5) * 140,
      };
      const matches =
        normalizedQuery.length === 0 ||
        concept.title.toLowerCase().includes(normalizedQuery);
      const selected = focusSet.selected === concept.id;
      return {
        id: concept.id,
        position: point,
        className:
          flashConceptId === concept.id ? "colearni-node-flash" : undefined,
        data: {
          label: (
            <NodeLabel node={concept} masteryByConcept={masteryByConcept} />
          ),
        },
        style: nodeStyleFor({
          node: concept,
          status: masteryStatusFor(concept, masteryByConcept),
          matchesSearch: matches,
          focused: isFocusedNode(concept.id, focusSet),
          selected,
        }),
      };
    });
}

function buildFlowEdges(
  edges: TrailGraphData["edges"],
  visibleNodeIds: Set<string>,
  focusSet: ReturnType<typeof buildFocusSet>,
  showLabels: boolean,
): Edge[] {
  return edges
    .filter(
      (edge) =>
        visibleNodeIds.has(edge.source_node_id) &&
        visibleNodeIds.has(edge.target_node_id),
    )
    .map((edge) => {
      const focused = isFocusedEdge(edge, focusSet);
      return {
        id: edge.id,
        source: edge.source_node_id,
        target: edge.target_node_id,
        label: showLabels ? edge.relation_type : undefined,
        labelStyle: showLabels
          ? { fontSize: 10, fill: "#475569", fontWeight: 500 }
          : undefined,
        labelBgStyle: showLabels
          ? { fill: "#ffffff", fillOpacity: 0.85 }
          : undefined,
        labelBgPadding: showLabels ? ([4, 2] as [number, number]) : undefined,
        markerEnd:
          edge.relation_type === "prerequisite"
            ? {
                type: MarkerType.ArrowClosed,
                color: edgeColor(edge.relation_type),
              }
            : undefined,
        style: edgeStyleFor(edge, focused),
      };
    });
}

function NodeLabel({
  node,
  masteryByConcept,
}: {
  node: ConceptNode;
  masteryByConcept: TrailGraphData["mastery"];
}) {
  return (
    <div className="relative flex h-full flex-col justify-between gap-2 p-3 text-left">
      <div className="line-clamp-2 text-sm font-semibold leading-5 text-slate-950">
        {node.title}
      </div>
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] uppercase text-slate-500">
          {node.concept_level}
        </span>
        <span
          title={`Difficulty: ${difficultyName(node.difficulty)}`}
          aria-label={`Difficulty: ${difficultyName(node.difficulty)}`}
          className="rounded bg-white/70 px-1.5 py-0.5 text-[10px] font-semibold text-slate-700"
        >
          {difficultyLabel(node.difficulty)}
        </span>
      </div>
      <NodeHoverPanel node={node} masteryByConcept={masteryByConcept} />
    </div>
  );
}

function NodeHoverPanel({
  node,
  masteryByConcept,
}: {
  node: ConceptNode;
  masteryByConcept: TrailGraphData["mastery"];
}) {
  return (
    <div
      data-node-hover-card
      className="pointer-events-none absolute left-0 top-full z-50 mt-2 hidden w-72 rounded-md border border-slate-200 bg-white/95 p-3 text-xs text-slate-700 shadow-lg backdrop-blur"
    >
      <div className="text-sm font-semibold text-slate-950">
        Title: {node.title}
      </div>
      <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1">
        <div>Level: {node.concept_level}</div>
        <div>Type: {node.node_type}</div>
        <div>Bloom: {node.bloom_level}</div>
        <div>Difficulty: {difficultyName(node.difficulty)}</div>
        <div className="col-span-2">
          Status: {statusLabel(masteryStatusFor(node, masteryByConcept))}
        </div>
      </div>
    </div>
  );
}

function difficultyLabel(difficulty: string) {
  return difficulty === "advanced"
    ? "A"
    : difficulty === "intermediate"
      ? "I"
      : "B";
}

function difficultyName(difficulty: string) {
  if (difficulty === "advanced") {
    return "Advanced";
  }
  if (difficulty === "intermediate") {
    return "Intermediate";
  }
  return "Beginner";
}

function statusLabel(status: MasteryStatus) {
  if (status === "learning") {
    return "Learning";
  }
  if (status === "needs_review") {
    return "Needs review";
  }
  if (status === "mastered") {
    return "Mastered";
  }
  return "Not started";
}

function GraphLegendContent({ compact }: { compact: boolean }) {
  return (
    <div
      className={`grid max-h-[42vh] w-full gap-4 overflow-y-auto rounded-md border border-slate-200 bg-white/95 p-4 text-xs text-slate-700 shadow-sm backdrop-blur md:max-h-none ${
        compact ? "md:mr-[28rem]" : "md:grid-cols-3"
      }`}
    >
      <div className="flex items-center justify-between md:col-span-3">
        <div className="font-semibold text-slate-900">Legend</div>
      </div>
      <div>
        <div className="font-semibold text-slate-900">Learning status</div>
        <div className="mt-2 grid gap-1">
          <LegendSwatch color={masteryColors.not_started} label="New" />
          <LegendSwatch color={masteryColors.learning} label="Learning" />
          <LegendSwatch color={masteryColors.needs_review} label="Review" />
          <LegendSwatch color={masteryColors.mastered} label="Mastered" />
        </div>
      </div>
      <div>
        <div className="font-semibold text-slate-900">Edges</div>
        <div className="mt-2 grid gap-1">
          <EdgeLegend relation="prerequisite" label="A -> B: A before B" />
          <EdgeLegend relation="contains" label="A -> B: A contains B" />
          <EdgeLegend relation="application" label="A -> B: A applies to B" />
          <EdgeLegend relation="related" label="Related connection" />
        </div>
      </div>
      <div>
        <div className="font-semibold text-slate-900">Difficulty</div>
        <div className="mt-2 grid gap-1">
          <div>B = Beginner</div>
          <div>I = Intermediate</div>
          <div>A = Advanced</div>
        </div>
      </div>
    </div>
  );
}

function LegendSwatch({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <span
        className="h-3 w-3 rounded border border-slate-300"
        style={{ background: color }}
      />
      <span>{label}</span>
    </div>
  );
}

function EdgeLegend({
  relation,
  label,
}: {
  relation: TrailGraphData["edges"][number]["relation_type"];
  label: string;
}) {
  const dashed =
    relation === "contains"
      ? "7 5"
      : relation === "application"
        ? "2 4"
        : undefined;
  return (
    <div className="flex items-center gap-2">
      <svg aria-hidden="true" width="42" height="10" viewBox="0 0 42 10">
        <line
          x1="1"
          y1="5"
          x2="36"
          y2="5"
          stroke={edgeColor(relation)}
          strokeWidth={relation === "related" ? 1.3 : 2}
          strokeDasharray={dashed}
        />
        {relation !== "related" ? (
          <path d="M36 1 L41 5 L36 9 Z" fill={edgeColor(relation)} />
        ) : null}
      </svg>
      <span>{label}</span>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="min-w-0 rounded border border-slate-200 bg-slate-50 px-2 py-1">
      <div className="font-semibold text-slate-950">{value}</div>
      <div className="truncate">{label}</div>
    </div>
  );
}

function ToolbarButton({
  active,
  icon,
  label,
  onClick,
  subtle = false,
}: {
  active?: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
  subtle?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active ? true : undefined}
      className={`inline-flex h-8 shrink-0 items-center gap-2 rounded-md border px-3 text-xs font-medium transition md:h-9 md:text-sm ${
        active
          ? "border-blue-200 bg-blue-50 text-blue-800 shadow-sm"
          : subtle
            ? "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50"
            : "border-slate-300 bg-white text-slate-900 shadow-sm hover:border-slate-400 hover:bg-slate-50"
      }`}
    >
      <span className="text-current" aria-hidden="true">
        {icon}
      </span>
      <span>{label}</span>
    </button>
  );
}

function FilterPill({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`inline-flex h-8 items-center gap-2 rounded-full border px-3 text-xs font-medium transition ${
        active
          ? "border-blue-200 bg-blue-50 text-blue-800"
          : "border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-800"
      }`}
    >
      <span
        aria-hidden="true"
        className={`h-2 w-2 rounded-full ${active ? "bg-blue-500" : "bg-slate-300"}`}
      />
      {label}
    </button>
  );
}

function countMasteryStatuses(
  nodes: ConceptNode[],
  masteryByConcept: TrailGraphData["mastery"],
) {
  return nodes.reduce(
    (summary, node) => {
      summary.total += 1;
      summary[masteryStatusFor(node, masteryByConcept)] += 1;
      return summary;
    },
    {
      total: 0,
      not_started: 0,
      learning: 0,
      needs_review: 0,
      mastered: 0,
    },
  );
}
