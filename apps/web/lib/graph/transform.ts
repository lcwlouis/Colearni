import Graph from "graphology";
import type { GraphSubgraphNode, GraphSubgraphEdge } from "@/lib/api/types";
import { TIER_COLORS, NODE_SIZE_RANGE, EDGE_SIZE_RANGE } from "./constants";

/**
 * Convert API subgraph data into a graphology Graph instance
 * suitable for Sigma.js rendering.
 */
export function buildGraphologyGraph(
  nodes: GraphSubgraphNode[],
  edges: GraphSubgraphEdge[],
  filteredTiers?: ReadonlySet<string>,
): Graph {
  const graph = new Graph();

  // --- Add nodes (skip filtered tiers entirely so layouts ignore them) ---
  for (const node of nodes) {
    if (filteredTiers && filteredTiers.size < 4) {
      if (filteredTiers.size === 0 || !filteredTiers.has(node.tier ?? "")) continue;
    }

    const key = String(node.concept_id);
    graph.addNode(key, {
      label: node.canonical_name,
      color: TIER_COLORS[node.tier ?? ""] ?? TIER_COLORS.granular,
      x: Math.random(),
      y: Math.random(),
      size: NODE_SIZE_RANGE.min, // placeholder; updated after degree computation
      tier: node.tier ?? null,
      conceptId: node.concept_id,
      masteryStatus: node.mastery_status,
    });
  }

  // --- Add edges (skip if endpoint missing) ---
  for (const edge of edges) {
    const src = String(edge.src_concept_id);
    const tgt = String(edge.tgt_concept_id);
    if (!graph.hasNode(src) || !graph.hasNode(tgt)) continue;
    // Skip duplicate edges between the same node pair (non-multi graph)
    if (graph.hasEdge(src, tgt)) continue;

    const w = edge.weight ?? 1;
    const size =
      EDGE_SIZE_RANGE.min +
      (EDGE_SIZE_RANGE.max - EDGE_SIZE_RANGE.min) * Math.sqrt(Math.min(w, 1));

    graph.addEdgeWithKey(String(edge.edge_id), src, tgt, {
      label: edge.description || "",
      size,
      type: "curvedArrow",
    });
  }

  // --- Degree-based node sizing ---
  if (graph.order > 0) {
    let minDeg = Infinity;
    let maxDeg = -Infinity;
    graph.forEachNode((key) => {
      const d = graph.degree(key);
      if (d < minDeg) minDeg = d;
      if (d > maxDeg) maxDeg = d;
    });

    const degRange = maxDeg - minDeg;
    graph.forEachNode((key) => {
      const d = graph.degree(key);
      const ratio = degRange === 0 ? 0 : (d - minDeg) / degRange;
      const size =
        NODE_SIZE_RANGE.min +
        (NODE_SIZE_RANGE.max - NODE_SIZE_RANGE.min) * Math.sqrt(ratio);
      graph.setNodeAttribute(key, "size", size);
    });
  }

  return graph;
}
