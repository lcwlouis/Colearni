import dagre from "dagre";

import type { ConceptEdge, ConceptNode } from "@/lib/types";

export type GraphLayoutMode = "hierarchy" | "radial" | "freeform" | "compact";

export interface GraphPosition {
  x: number;
  y: number;
}

export interface LayoutGraphInput {
  mode: GraphLayoutMode;
  nodes: ConceptNode[];
  edges: ConceptEdge[];
  selectedNodeId: string | null;
  existingPositions?: Map<string, GraphPosition>;
}

const NODE_WIDTH = 220;
const NODE_HEIGHT = 92;

export function layoutGraph({
  mode,
  nodes,
  edges,
  selectedNodeId,
  existingPositions,
}: LayoutGraphInput): Map<string, GraphPosition> {
  if (mode === "freeform" && existingPositions && existingPositions.size > 0) {
    const fallback = layoutDagre(nodes, edges, "hierarchy");
    const positions = new Map<string, GraphPosition>();
    nodes.forEach((node) => {
      positions.set(node.id, existingPositions.get(node.id) ?? fallback.get(node.id) ?? { x: 0, y: 0 });
    });
    return positions;
  }
  if (mode === "radial") {
    return layoutRadial(nodes, edges, selectedNodeId);
  }
  return layoutDagre(nodes, edges, mode === "compact" ? "compact" : "hierarchy");
}

function layoutDagre(
  nodes: ConceptNode[],
  edges: ConceptEdge[],
  mode: "hierarchy" | "compact",
): Map<string, GraphPosition> {
  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph(
    mode === "compact"
      ? { rankdir: "TB", nodesep: 52, ranksep: 72 }
      : { rankdir: "TB", nodesep: 120, ranksep: 150 },
  );

  nodes.forEach((node) => graph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT }));
  edges.forEach((edge) => graph.setEdge(edge.source_node_id, edge.target_node_id));
  dagre.layout(graph);

  const positions = new Map<string, GraphPosition>();
  nodes.forEach((node, index) => {
    const point = graph.node(node.id) ?? fallbackPosition(index);
    positions.set(node.id, {
      x: point.x - NODE_WIDTH / 2,
      y: point.y - NODE_HEIGHT / 2,
    });
  });
  return positions;
}

function layoutRadial(
  nodes: ConceptNode[],
  edges: ConceptEdge[],
  selectedNodeId: string | null,
): Map<string, GraphPosition> {
  const centerId = selectedNodeId ?? nodes[0]?.id ?? null;
  if (!centerId) {
    return new Map();
  }

  const neighborIds = new Set<string>();
  edges.forEach((edge) => {
    if (edge.source_node_id === centerId) {
      neighborIds.add(edge.target_node_id);
    }
    if (edge.target_node_id === centerId) {
      neighborIds.add(edge.source_node_id);
    }
  });

  const positions = new Map<string, GraphPosition>([[centerId, { x: 0, y: 0 }]]);
  const neighbors = nodes.filter((node) => neighborIds.has(node.id) && node.id !== centerId);
  placeRing(positions, neighbors, 320);

  const remaining = nodes.filter((node) => !positions.has(node.id));
  placeRing(positions, remaining, 640);
  return positions;
}

function placeRing(
  positions: Map<string, GraphPosition>,
  nodes: ConceptNode[],
  radius: number,
): void {
  const count = Math.max(nodes.length, 1);
  nodes.forEach((node, index) => {
    const angle = (Math.PI * 2 * index) / count;
    positions.set(node.id, {
      x: Math.round(Math.cos(angle) * radius),
      y: Math.round(Math.sin(angle) * radius),
    });
  });
}

function fallbackPosition(index: number): GraphPosition {
  return {
    x: 120 + (index % 5) * 260,
    y: 120 + Math.floor(index / 5) * 140,
  };
}
