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
  MasteryStatus,
  Trail,
  TrailGraph as TrailGraphData,
} from "@/lib/types";

import { ConceptPanel } from "./ConceptPanel";
import { type GraphLayoutMode, type GraphPosition, layoutGraph } from "./graphLayout";
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
}

export function TrailGraph({ workspaceId, trail, graph, masterySummary }: TrailGraphProps) {
  const [query, setQuery] = useState("");
  const [visibleLevels, setVisibleLevels] = useState<Set<ConceptLevel>>(
    () => new Set(levels),
  );
  const [layoutMode, setLayoutMode] = useState<GraphLayoutMode>("freeform");
  const [toolsExpanded, setToolsExpanded] = useState(true);
  const [legendExpanded, setLegendExpanded] = useState(false);
  const [neighborsOnly, setNeighborsOnly] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [positions, setPositions] = useState<Map<string, GraphPosition>>(new Map());
  const [flow, setFlow] = useState<ReactFlowInstance | null>(null);
  const [detail, setDetail] = useState<ConceptDetail | null>(null);
  const [panelError, setPanelError] = useState("");
  const lastViewState = useRef({ layoutMode, selectedNodeId, visibleCount: 0 });

  const selectedNode = useMemo(
    () => graph.nodes.find((node) => node.id === selectedNodeId) ?? null,
    [graph.nodes, selectedNodeId],
  );
  const focusSet = useMemo(
    () => buildFocusSet(graph.edges, selectedNodeId),
    [graph.edges, selectedNodeId],
  );
  const statusCounts = useMemo(() => countMasteryStatuses(graph.nodes), [graph.nodes]);

  const visibleNodeIds = useMemo(() => {
    const levelVisible = new Set(
      graph.nodes
        .filter((node) => visibleLevels.has(node.concept_level))
        .map((node) => node.id),
    );
    if (!neighborsOnly || !selectedNodeId) {
      return levelVisible;
    }
    return new Set(
      [...levelVisible].filter((nodeId) => isFocusedNode(nodeId, focusSet)),
    );
  }, [focusSet, graph.nodes, neighborsOnly, selectedNodeId, visibleLevels]);

  const computedPositions = useMemo(
    () =>
      layoutGraph({
        mode: layoutMode,
        nodes: graph.nodes.filter((node) => visibleNodeIds.has(node.id)),
        edges: graph.edges.filter(
          (edge) =>
            visibleNodeIds.has(edge.source_node_id) && visibleNodeIds.has(edge.target_node_id),
        ),
        selectedNodeId,
        existingPositions: positions,
      }),
    [graph.edges, graph.nodes, layoutMode, positions, selectedNodeId, visibleNodeIds],
  );

  const flowNodes = useMemo(
    () => buildFlowNodes(graph.nodes, visibleNodeIds, computedPositions, query, focusSet),
    [computedPositions, focusSet, graph.nodes, query, visibleNodeIds],
  );
  const flowEdges = useMemo(
    () => buildFlowEdges(graph.edges, visibleNodeIds, focusSet),
    [focusSet, graph.edges, visibleNodeIds],
  );

  const focusConceptInView = useCallback(
    (conceptId: string, zoom: number) => {
      const point = computedPositions.get(conceptId);
      if (point) {
        void flow?.setCenter(point.x + 110, point.y + 46, { zoom, duration: 220 });
      }
    },
    [computedPositions, flow],
  );

  const fitVisibleGraph = useCallback(
    (padding: number) => {
      window.requestAnimationFrame(() => {
        void flow?.fitView({ padding, duration: 220 });
      });
    },
    [flow],
  );

  useEffect(() => {
    if (!flow || flowNodes.length === 0) {
      return;
    }

    const previous = lastViewState.current;
    const layoutChanged = previous.layoutMode !== layoutMode;
    const selectionChanged = previous.selectedNodeId !== selectedNodeId;
    const visibleCountChanged = previous.visibleCount !== flowNodes.length;
    lastViewState.current = { layoutMode, selectedNodeId, visibleCount: flowNodes.length };

    if (selectedNodeId) {
      if (selectionChanged || layoutChanged) {
        focusConceptInView(selectedNodeId, window.innerWidth < 768 ? 0.92 : 1);
      }
      return;
    }

    if (layoutChanged || visibleCountChanged) {
      fitVisibleGraph(window.innerWidth < 768 ? 0.18 : 0.24);
    }
  }, [
    flow,
    flowNodes.length,
    layoutMode,
    selectedNodeId,
    computedPositions,
    fitVisibleGraph,
    focusConceptInView,
  ]);

  async function openConcept(conceptId: string) {
    setSelectedNodeId(conceptId);
    setPanelError("");
    try {
      setDetail(await getConcept(workspaceId, trail.id, conceptId));
    } catch (exc) {
      setPanelError(exc instanceof Error ? exc.message : "Could not load concept");
    }
  }

  function clearSelection() {
    setSelectedNodeId(null);
    setDetail(null);
    setPanelError("");
    fitVisibleGraph(window.innerWidth < 768 ? 0.26 : 0.3);
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
    focusConceptInView(match.id, 0.95);
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
    focusConceptInView(selectedNodeId, 1);
  }

  function changeLayoutMode(mode: GraphLayoutMode) {
    setLayoutMode(mode);
  }

  function initializeFlow(instance: ReactFlowInstance) {
    setFlow(instance);
    window.requestAnimationFrame(() => {
      void instance.fitView({
        padding: window.innerWidth < 768 ? 0.14 : 0.22,
        duration: 180,
      });
    });
  }

  return (
    <section className="relative flex min-h-0 flex-1">
      <style>
        {".react-flow__node:hover [data-node-hover-card] { display: block; }"}
      </style>
      <div className="h-full w-full" onClickCapture={handleGraphSurfaceClick}>
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          minZoom={0.12}
          onInit={initializeFlow}
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
          <MiniMap
            className="hidden md:block"
            pannable
            zoomable
            nodeStrokeWidth={3}
            position="bottom-left"
            style={{ bottom: 16, left: 76, height: 118, width: 180 }}
          />
          <Controls
            position="bottom-left"
            style={{ bottom: 16, left: 12 }}
          />
          <Panel position="top-left">
            <div className="flex w-[min(94vw,720px)] flex-col gap-2 rounded-md border border-slate-200 bg-white/95 p-2 shadow-sm backdrop-blur md:w-[min(70vw,760px)] md:gap-3 md:p-3 lg:w-[min(58vw,780px)]">
              <div className="flex gap-2 md:items-center">
                <input
                  value={query}
                  onChange={(event) => handleSearchChange(event.target.value)}
                  placeholder="Search concepts"
                  className="h-8 min-w-0 flex-1 rounded-md border border-slate-300 px-2 text-xs outline-none focus:border-blue-500 md:h-9 md:px-3 md:text-sm"
                />
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
              </div>
              {selectedNode ? (
                <p className="text-xs font-medium text-blue-800">Selected: {selectedNode.title}</p>
              ) : (
                <p className="text-xs text-slate-500">Select a node to highlight its connections.</p>
              )}
              {legendExpanded ? (
                <div>
                  <GraphLegendContent compact={false} />
                </div>
              ) : null}
              <div className={`${toolsExpanded ? "grid" : "hidden"} gap-2 md:gap-3`}>
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
                    onClick={() => flow?.fitView({ padding: 0.2, duration: 220 })}
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
                  {layoutModes.map((mode) => (
                    <button
                      key={mode.value}
                      type="button"
                      onClick={() => changeLayoutMode(mode.value)}
                      aria-pressed={layoutMode === mode.value}
                      className={`h-8 rounded px-2 text-xs font-medium transition md:px-3 ${
                        layoutMode === mode.value
                          ? "bg-white text-blue-700 shadow-sm"
                          : "text-slate-600 hover:bg-white/70 hover:text-slate-900"
                      }`}
                    >
                      {mode.label}
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
                </div>
                <div className="grid grid-cols-5 gap-1 text-xs text-slate-600 md:gap-2">
                  <Metric label="Total" value={statusCounts.total || masterySummary.total} />
                  <Metric label="New" value={statusCounts.not_started} />
                  <Metric label="Learning" value={statusCounts.learning} />
                  <Metric label="Review" value={statusCounts.needs_review} />
                  <Metric label="Mastered" value={statusCounts.mastered} />
                </div>
              </div>
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
          detail={detail}
          onClose={clearSelection}
          onSelectConcept={openConcept}
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
        data: {
          label: <NodeLabel node={concept} />,
        },
        style: nodeStyleFor({
          node: concept,
          status: masteryStatusFor(concept),
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
): Edge[] {
  return edges
    .filter(
      (edge) => visibleNodeIds.has(edge.source_node_id) && visibleNodeIds.has(edge.target_node_id),
    )
    .map((edge) => {
      const focused = isFocusedEdge(edge, focusSet);
      return {
        id: edge.id,
        source: edge.source_node_id,
        target: edge.target_node_id,
        markerEnd:
          edge.relation_type === "prerequisite"
            ? { type: MarkerType.ArrowClosed, color: edgeColor(edge.relation_type) }
            : undefined,
        style: edgeStyleFor(edge, focused),
      };
    });
}

function NodeLabel({
  node,
}: {
  node: ConceptNode;
}) {
  return (
    <div className="relative flex h-full flex-col justify-between gap-2 p-3 text-left">
      <div className="line-clamp-2 text-sm font-semibold leading-5 text-slate-950">
        {node.title}
      </div>
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] uppercase text-slate-500">{node.concept_level}</span>
        <span
          title={`Difficulty: ${difficultyName(node.difficulty)}`}
          aria-label={`Difficulty: ${difficultyName(node.difficulty)}`}
          className="rounded bg-white/70 px-1.5 py-0.5 text-[10px] font-semibold text-slate-700"
        >
          {difficultyLabel(node.difficulty)}
        </span>
      </div>
      <NodeHoverPanel node={node} />
    </div>
  );
}

function NodeHoverPanel({ node }: { node: ConceptNode }) {
  return (
    <div
      data-node-hover-card
      className="pointer-events-none absolute left-0 top-full z-50 mt-2 hidden w-72 rounded-md border border-slate-200 bg-white/95 p-3 text-xs text-slate-700 shadow-lg backdrop-blur"
    >
      <div className="text-sm font-semibold text-slate-950">Title: {node.title}</div>
      <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1">
        <div>Level: {node.concept_level}</div>
        <div>Type: {node.node_type}</div>
        <div>Bloom: {node.bloom_level}</div>
        <div>Difficulty: {difficultyName(node.difficulty)}</div>
        <div className="col-span-2">Status: {statusLabel(masteryStatusFor(node))}</div>
      </div>
    </div>
  );
}

function difficultyLabel(difficulty: string) {
  return difficulty === "advanced" ? "A" : difficulty === "intermediate" ? "I" : "B";
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

function GraphLegendContent({
  compact,
}: {
  compact: boolean;
}) {
  return (
    <div
      className={`grid max-h-[42vh] w-full gap-3 overflow-y-auto rounded-md border border-slate-200 bg-white/95 p-3 text-xs text-slate-700 shadow-sm backdrop-blur md:w-[min(88vw,660px)] md:max-h-none ${
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
      <span className="h-3 w-3 rounded border border-slate-300" style={{ background: color }} />
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
    relation === "contains" ? "7 5" : relation === "application" ? "2 4" : undefined;
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

function countMasteryStatuses(nodes: ConceptNode[]) {
  return nodes.reduce(
    (summary, node) => {
      summary.total += 1;
      summary[masteryStatusFor(node)] += 1;
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
