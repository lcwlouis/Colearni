import { describe, expect, test } from "vitest";

import { layoutGraph } from "@/app/trails/[id]/components/graphLayout";
import type { ConceptEdge, ConceptNode } from "@/lib/types";

const nodes: ConceptNode[] = [
  node("root", "Graph Viewer", "umbrella"),
  node("search", "Search Concepts", "topic"),
  node("panel", "Concept Panel", "subtopic"),
  node("detail", "Detail Fields", "granular"),
];

const edges: ConceptEdge[] = [
  edge("e1", "root", "search", "contains"),
  edge("e2", "search", "panel", "prerequisite"),
  edge("e3", "panel", "detail", "related"),
];

describe("graphLayout", () => {
  test("hierarchy returns positions for every node", () => {
    const positions = layoutGraph({ mode: "hierarchy", nodes, edges, selectedNodeId: null });

    expect(positions.size).toBe(nodes.length);
    expect(positions.get("root")).toBeDefined();
  });

  test("radial layout centers the selected node", () => {
    const positions = layoutGraph({ mode: "radial", nodes, edges, selectedNodeId: "panel" });

    expect(positions.get("panel")).toEqual({ x: 0, y: 0 });
    expect(positions.get("search")?.x).not.toBe(0);
  });

  test("radial layout centers the strongest umbrella node when nothing is selected", () => {
    const shuffledNodes = [
      node("basis", "Basis", "topic"),
      node("linear-algebra", "Linear Algebra", "umbrella"),
      node("vectors", "Vectors", "topic"),
      node("matrices", "Matrices", "topic"),
    ];
    const shuffledEdges = [
      edge("e1", "linear-algebra", "vectors", "contains"),
      edge("e2", "linear-algebra", "matrices", "contains"),
      edge("e3", "vectors", "basis", "prerequisite"),
    ];

    const positions = layoutGraph({
      mode: "radial",
      nodes: shuffledNodes,
      edges: shuffledEdges,
      selectedNodeId: null,
    });

    expect(positions.get("linear-algebra")).toEqual({ x: 0, y: 0 });
    expect(positions.get("basis")).not.toEqual({ x: 0, y: 0 });
  });

  test("compact layout is a distinct horizontal view", () => {
    const hierarchyPositions = layoutGraph({ mode: "hierarchy", nodes, edges, selectedNodeId: null });
    const compactPositions = layoutGraph({ mode: "compact", nodes, edges, selectedNodeId: null });

    expect(compactPositions.get("detail")?.x).toBeGreaterThan(hierarchyPositions.get("detail")?.x ?? 0);
  });

  test("freeform preserves existing positions", () => {
    const existingPositions = new Map([["root", { x: 123, y: 456 }]]);

    const positions = layoutGraph({
      mode: "freeform",
      nodes,
      edges,
      selectedNodeId: null,
      existingPositions,
    });

    expect(positions.get("root")).toEqual({ x: 123, y: 456 });
  });
});

function node(id: string, title: string, concept_level: ConceptNode["concept_level"]): ConceptNode {
  return {
    id,
    trail_id: "trail-1",
    slug: id,
    title,
    node_type: "concept",
    concept_level,
    difficulty: "beginner",
    bloom_level: "understand",
    mastery_check_labels: [],
    metadata_json: {},
  };
}

function edge(
  id: string,
  source_node_id: string,
  target_node_id: string,
  relation_type: ConceptEdge["relation_type"],
): ConceptEdge {
  return {
    id,
    trail_id: "trail-1",
    source_node_id,
    target_node_id,
    relation_type,
  };
}
