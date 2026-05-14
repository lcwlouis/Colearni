"use client";

import "@xyflow/react/dist/style.css";

import { useMemo, useState } from "react";
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

import { getConcept } from "@/lib/api";
import type {
  ConceptDetail,
  ConceptLevel,
  ConceptNode,
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
  nodeStyleFor,
} from "./graphStyles";

const levels: ConceptLevel[] = ["umbrella", "topic", "subtopic", "granular"];
const layoutModes: Array<{ value: GraphLayoutMode; label: string }> = [
  { value: "hierarchy", label: "Hierarchy" },
  { value: "radial", label: "Radial" },
  { value: "freeform", label: "Freeform" },
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
  const [layoutMode, setLayoutMode] = useState<GraphLayoutMode>(
    graph.nodes.length > 50 ? "compact" : "hierarchy",
  );
  const [neighborsOnly, setNeighborsOnly] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [positions, setPositions] = useState<Map<string, GraphPosition>>(new Map());
  const [flow, setFlow] = useState<ReactFlowInstance | null>(null);
  const [detail, setDetail] = useState<ConceptDetail | null>(null);
  const [panelError, setPanelError] = useState("");

  const selectedNode = useMemo(
    () => graph.nodes.find((node) => node.id === selectedNodeId) ?? null,
    [graph.nodes, selectedNodeId],
  );
  const focusSet = useMemo(
    () => buildFocusSet(graph.edges, selectedNodeId),
    [graph.edges, selectedNodeId],
  );

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

  async function openConcept(conceptId: string) {
    setSelectedNodeId(conceptId);
    setPanelError("");
    try {
      setDetail(await getConcept(workspaceId, trail.id, conceptId));
    } catch (exc) {
      setPanelError(exc instanceof Error ? exc.message : "Could not load concept");
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
    const point = computedPositions.get(match.id);
    if (point) {
      void flow?.setCenter(point.x + 110, point.y + 46, { zoom: 0.95, duration: 220 });
    }
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
    void flow?.setViewport({ x: 80, y: 300, zoom: 0.85 }, { duration: 220 });
  }

  function centerSelected() {
    if (!selectedNodeId) {
      void flow?.fitView({ padding: 0.24, duration: 220 });
      return;
    }
    const point = computedPositions.get(selectedNodeId);
    if (point) {
      void flow?.setCenter(point.x + 110, point.y + 46, { zoom: 1, duration: 220 });
    }
  }

  return (
    <section className="relative flex min-h-0 flex-1">
      <div className="h-full w-full">
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          defaultViewport={{ x: 80, y: 300, zoom: 0.85 }}
          minZoom={0.12}
          onInit={setFlow}
          onNodeClick={(_, node) => openConcept(node.id)}
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
          <MiniMap pannable zoomable nodeStrokeWidth={3} />
          <Controls />
          <Panel position="top-left">
            <div className="flex w-[min(72vw,660px)] flex-col gap-3 rounded-md border border-slate-200 bg-white/95 p-3 shadow-sm backdrop-blur">
              <div className="flex flex-col gap-3 md:flex-row md:items-center">
                <input
                  value={query}
                  onChange={(event) => handleSearchChange(event.target.value)}
                  placeholder="Search concepts"
                  className="h-9 min-w-0 flex-1 rounded-md border border-slate-300 px-3 text-sm outline-none focus:border-blue-500"
                />
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={setReadableZoom}
                    className="h-9 rounded-md border border-slate-300 px-3 text-sm font-medium hover:bg-slate-50"
                  >
                    Readable
                  </button>
                  <button
                    type="button"
                    onClick={() => flow?.fitView({ padding: 0.2, duration: 220 })}
                    className="h-9 rounded-md border border-slate-300 px-3 text-sm font-medium hover:bg-slate-50"
                  >
                    Overview
                  </button>
                  <button
                    type="button"
                    onClick={centerSelected}
                    className="h-9 rounded-md border border-slate-300 px-3 text-sm font-medium hover:bg-slate-50"
                  >
                    Focus selected
                  </button>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {layoutModes.map((mode) => (
                  <button
                    key={mode.value}
                    type="button"
                    onClick={() => setLayoutMode(mode.value)}
                    className={`h-8 rounded-md border px-3 text-xs font-medium ${
                      layoutMode === mode.value
                        ? "border-blue-600 bg-blue-50 text-blue-800"
                        : "border-slate-300 text-slate-700 hover:bg-slate-50"
                    }`}
                  >
                    {mode.label}
                  </button>
                ))}
              </div>
              <div className="flex flex-wrap gap-3">
                {levels.map((level) => (
                  <label key={level} className="flex items-center gap-2 text-xs text-slate-700">
                    <input
                      type="checkbox"
                      checked={visibleLevels.has(level)}
                      onChange={() => toggleLevel(level)}
                    />
                    {level}
                  </label>
                ))}
                <label className="flex items-center gap-2 text-xs font-medium text-slate-800">
                  <input
                    type="checkbox"
                    checked={neighborsOnly}
                    onChange={(event) => setNeighborsOnly(event.target.checked)}
                  />
                  Neighbors only
                </label>
              </div>
              {selectedNode ? (
                <p className="text-xs font-medium text-blue-800">Selected: {selectedNode.title}</p>
              ) : (
                <p className="text-xs text-slate-500">Select a node to highlight its connections.</p>
              )}
              <div className="grid grid-cols-5 gap-2 text-xs text-slate-600">
                <Metric label="total" value={masterySummary.total} />
                <Metric label="new" value={masterySummary.not_started} />
                <Metric label="learning" value={masterySummary.learning} />
                <Metric label="review" value={masterySummary.needs_review} />
                <Metric label="mastered" value={masterySummary.mastered} />
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
          onClose={() => setDetail(null)}
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
          label: (
            <NodeLabel
              title={concept.title}
              level={concept.concept_level}
              difficulty={concept.difficulty}
            />
          ),
        },
        style: nodeStyleFor({
          node: concept,
          status: "not_started",
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
  title,
  level,
  difficulty,
}: {
  title: string;
  level: ConceptLevel;
  difficulty: string;
}) {
  return (
    <div className="flex h-full flex-col justify-between gap-2 p-3 text-left">
      <div className="line-clamp-2 text-sm font-semibold leading-5 text-slate-950">{title}</div>
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] uppercase text-slate-500">{level}</span>
        <span className="rounded bg-white/70 px-1.5 py-0.5 text-[10px] font-semibold text-slate-700">
          {difficultyLabel(difficulty)}
        </span>
      </div>
    </div>
  );
}

function difficultyLabel(difficulty: string) {
  return difficulty === "advanced" ? "A" : difficulty === "intermediate" ? "I" : "B";
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-slate-200 bg-slate-50 px-2 py-1">
      <div className="font-semibold text-slate-950">{value}</div>
      <div>{label}</div>
    </div>
  );
}
