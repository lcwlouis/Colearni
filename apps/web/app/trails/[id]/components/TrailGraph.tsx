"use client";

import "@xyflow/react/dist/style.css";

import dagre from "dagre";
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
  ConceptEdge,
  ConceptLevel,
  ConceptNode,
  MasteryStatus,
  Trail,
  TrailGraph as TrailGraphData,
  RelationType,
} from "@/lib/types";

import { ConceptPanel } from "./ConceptPanel";

const levels: ConceptLevel[] = ["umbrella", "topic", "subtopic", "granular"];

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
  const [flow, setFlow] = useState<ReactFlowInstance | null>(null);
  const [detail, setDetail] = useState<ConceptDetail | null>(null);
  const [panelError, setPanelError] = useState("");

  const visibleNodeIds = useMemo(
    () =>
      new Set(
        graph.nodes
          .filter((node) => visibleLevels.has(node.concept_level))
          .map((node) => node.id),
      ),
    [graph.nodes, visibleLevels],
  );
  const flowNodes = useMemo(
    () => layoutNodes(graph.nodes, visibleNodeIds, query),
    [graph.nodes, query, visibleNodeIds],
  );
  const flowEdges = useMemo(
    () => layoutEdges(graph.edges, visibleNodeIds),
    [graph.edges, visibleNodeIds],
  );

  async function openConcept(conceptId: string) {
    setPanelError("");
    try {
      setDetail(await getConcept(workspaceId, trail.id, conceptId));
    } catch (exc) {
      setPanelError(exc instanceof Error ? exc.message : "Could not load concept");
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

  return (
    <section className="relative flex min-h-0 flex-1">
      <div className="h-full w-full">
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          fitView
          minZoom={0.15}
          onInit={setFlow}
          onNodeClick={(_, node) => openConcept(node.id)}
          nodesDraggable
        >
          <Background color="#cbd5e1" gap={28} />
          <MiniMap pannable zoomable nodeStrokeWidth={3} />
          <Controls />
          <Panel position="top-left">
            <div className="flex w-[min(92vw,680px)] flex-col gap-3 rounded-md border border-slate-200 bg-white/95 p-3 shadow-sm backdrop-blur">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search concepts"
                  className="h-9 min-w-0 flex-1 rounded-md border border-slate-300 px-3 text-sm outline-none focus:border-blue-500"
                />
                <button
                  type="button"
                  onClick={() => flow?.fitView({ padding: 0.18 })}
                  className="h-9 rounded-md border border-slate-300 px-3 text-sm font-medium hover:bg-slate-50"
                >
                  Fit view
                </button>
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
              </div>
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

function layoutNodes(
  concepts: ConceptNode[],
  visibleNodeIds: Set<string>,
  query: string,
): Node[] {
  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({ rankdir: "TB", nodesep: 70, ranksep: 95 });
  const normalizedQuery = query.trim().toLowerCase();
  const visibleConcepts = concepts.filter((concept) => visibleNodeIds.has(concept.id));

  visibleConcepts.forEach((concept) => graph.setNode(concept.id, { width: 190, height: 72 }));
  dagre.layout(graph);

  return visibleConcepts.map((concept, index) => {
    const point = graph.node(concept.id) ?? { x: 120 + (index % 5) * 220, y: 90 + index * 90 };
    const matches = normalizedQuery.length === 0 || concept.title.toLowerCase().includes(normalizedQuery);
    return {
      id: concept.id,
      position: { x: point.x - 95, y: point.y - 36 },
      data: {
        label: (
          <NodeLabel
            title={concept.title}
            level={concept.concept_level}
            difficulty={concept.difficulty}
            status="not_started"
          />
        ),
      },
      style: nodeStyle("not_started", concept.concept_level, matches),
    };
  });
}

function layoutEdges(edges: ConceptEdge[], visibleNodeIds: Set<string>): Edge[] {
  return edges
    .filter((edge) => visibleNodeIds.has(edge.source_node_id) && visibleNodeIds.has(edge.target_node_id))
    .map((edge) => ({
      id: edge.id,
      source: edge.source_node_id,
      target: edge.target_node_id,
      markerEnd:
        edge.relation_type === "prerequisite"
          ? { type: MarkerType.ArrowClosed, color: edgeColor(edge.relation_type) }
          : undefined,
      style: edgeStyle(edge.relation_type),
    }));
}

function NodeLabel({
  title,
  level,
  difficulty,
}: {
  title: string;
  level: ConceptLevel;
  difficulty: string;
  status: MasteryStatus;
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

function nodeStyle(status: MasteryStatus, level: ConceptLevel, matchesSearch: boolean) {
  const statusColors: Record<MasteryStatus, string> = {
    not_started: "#f8fafc",
    learning: "#dbeafe",
    needs_review: "#ffedd5",
    mastered: "#dcfce7",
  };
  const borderByLevel: Record<ConceptLevel, string> = {
    umbrella: "3px solid #0f172a",
    topic: "2px solid #334155",
    subtopic: "2px dashed #64748b",
    granular: "1px solid #94a3b8",
  };
  return {
    width: 190,
    minHeight: 72,
    borderRadius: 8,
    border: borderByLevel[level],
    background: matchesSearch ? statusColors[status] : "#f1f5f9",
    opacity: matchesSearch ? 1 : 0.32,
    boxShadow: matchesSearch ? "0 10px 24px rgba(15, 23, 42, 0.10)" : "none",
  };
}

function edgeStyle(relationType: RelationType) {
  const style = { stroke: edgeColor(relationType), strokeWidth: 1.8 };
  if (relationType === "contains") {
    return { ...style, strokeDasharray: "7 5" };
  }
  if (relationType === "application") {
    return { ...style, strokeDasharray: "2 4" };
  }
  if (relationType === "related") {
    return { ...style, strokeWidth: 1 };
  }
  return style;
}

function edgeColor(relationType: RelationType) {
  if (relationType === "prerequisite") {
    return "#1d4ed8";
  }
  if (relationType === "contains") {
    return "#475569";
  }
  if (relationType === "application") {
    return "#ea580c";
  }
  return "#94a3b8";
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
