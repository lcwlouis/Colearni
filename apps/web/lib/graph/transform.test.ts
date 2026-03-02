import { describe, it, expect } from "vitest";
import { buildGraphologyGraph } from "./transform";
import { TIER_COLORS, NODE_SIZE_RANGE } from "./constants";
import type { GraphSubgraphNode, GraphSubgraphEdge } from "@/lib/api/types";

function makeNode(overrides: Partial<GraphSubgraphNode> & { concept_id: number; canonical_name: string }): GraphSubgraphNode {
  return {
    description: "",
    hop_distance: 0,
    mastery_status: null,
    mastery_score: null,
    tier: "topic",
    ...overrides,
  };
}

function makeEdge(overrides: Partial<GraphSubgraphEdge> & { edge_id: number; src_concept_id: number; tgt_concept_id: number }): GraphSubgraphEdge {
  return {
    relation_type: "related_to",
    description: "",
    keywords: [],
    weight: 1,
    ...overrides,
  };
}

describe("buildGraphologyGraph", () => {
  it("returns an empty graph for empty inputs", () => {
    const g = buildGraphologyGraph([], []);
    expect(g.order).toBe(0);
    expect(g.size).toBe(0);
  });

  it("creates correct nodes and edges", () => {
    const nodes = [
      makeNode({ concept_id: 1, canonical_name: "Alpha", tier: "umbrella" }),
      makeNode({ concept_id: 2, canonical_name: "Beta", tier: "topic" }),
      makeNode({ concept_id: 3, canonical_name: "Gamma", tier: "subtopic" }),
    ];
    const edges = [
      makeEdge({ edge_id: 10, src_concept_id: 1, tgt_concept_id: 2 }),
      makeEdge({ edge_id: 11, src_concept_id: 2, tgt_concept_id: 3, description: "depends on" }),
    ];

    const g = buildGraphologyGraph(nodes, edges);

    expect(g.order).toBe(3);
    expect(g.size).toBe(2);

    expect(g.getNodeAttribute("1", "label")).toBe("Alpha");
    expect(g.getNodeAttribute("1", "color")).toBe(TIER_COLORS.umbrella);
    expect(g.getNodeAttribute("2", "color")).toBe(TIER_COLORS.topic);
    expect(g.getNodeAttribute("3", "color")).toBe(TIER_COLORS.subtopic);

    expect(g.getEdgeAttribute("11", "label")).toBe("depends on");
  });

  it("hides nodes whose tier is in filteredTiers", () => {
    const nodes = [
      makeNode({ concept_id: 1, canonical_name: "A", tier: "umbrella" }),
      makeNode({ concept_id: 2, canonical_name: "B", tier: "topic" }),
    ];

    const g = buildGraphologyGraph(nodes, [], new Set(["umbrella"]));

    expect(g.getNodeAttribute("1", "hidden")).toBe(true);
    expect(g.getNodeAttribute("2", "hidden")).toBe(false);
  });

  it("assigns larger size to higher-degree nodes", () => {
    const nodes = [
      makeNode({ concept_id: 1, canonical_name: "Hub" }),
      makeNode({ concept_id: 2, canonical_name: "Leaf1" }),
      makeNode({ concept_id: 3, canonical_name: "Leaf2" }),
      makeNode({ concept_id: 4, canonical_name: "Leaf3" }),
    ];
    const edges = [
      makeEdge({ edge_id: 1, src_concept_id: 1, tgt_concept_id: 2 }),
      makeEdge({ edge_id: 2, src_concept_id: 1, tgt_concept_id: 3 }),
      makeEdge({ edge_id: 3, src_concept_id: 1, tgt_concept_id: 4 }),
    ];

    const g = buildGraphologyGraph(nodes, edges);

    const hubSize = g.getNodeAttribute("1", "size") as number;
    const leafSize = g.getNodeAttribute("2", "size") as number;

    expect(hubSize).toBe(NODE_SIZE_RANGE.max);
    expect(leafSize).toBeLessThan(hubSize);
    expect(leafSize).toBeGreaterThanOrEqual(NODE_SIZE_RANGE.min);
  });

  it("skips edges whose source or target node is missing", () => {
    const nodes = [
      makeNode({ concept_id: 1, canonical_name: "A" }),
    ];
    const edges = [
      makeEdge({ edge_id: 99, src_concept_id: 1, tgt_concept_id: 999 }),
    ];

    const g = buildGraphologyGraph(nodes, edges);

    expect(g.order).toBe(1);
    expect(g.size).toBe(0);
  });
});
