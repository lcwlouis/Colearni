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
      ? { rankdir: "LR", nodesep: 44, ranksep: 96 }
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
  const centerId = selectedNodeId ?? findRadialCenter(nodes, edges);
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

function findRadialCenter(nodes: ConceptNode[], edges: ConceptEdge[]): string | null {
  if (nodes.length === 0) {
    return null;
  }

  const scores = new Map<string, number>();
  nodes.forEach((node) => {
    scores.set(node.id, node.concept_level === "umbrella" ? 1000 : 0);
  });

  edges.forEach((edge) => {
    const sourceWeight = edge.relation_type === "contains" ? 10 : 4;
    const targetWeight = edge.relation_type === "contains" ? 3 : 4;
    scores.set(edge.source_node_id, (scores.get(edge.source_node_id) ?? 0) + sourceWeight);
    scores.set(edge.target_node_id, (scores.get(edge.target_node_id) ?? 0) + targetWeight);
  });

  return [...nodes].sort((left, right) => {
    const scoreDelta = (scores.get(right.id) ?? 0) - (scores.get(left.id) ?? 0);
    if (scoreDelta !== 0) {
      return scoreDelta;
    }
    return left.title.localeCompare(right.title);
  })[0]?.id ?? null;
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
