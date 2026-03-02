import { describe, it, expect } from "vitest";
import { buildSearchIndex, searchNodes } from "./search";
import type { GraphSubgraphNode } from "@/lib/api/types";

function makeNode(
  concept_id: number,
  canonical_name: string,
  description = "",
): GraphSubgraphNode {
  return {
    concept_id,
    canonical_name,
    description,
    hop_distance: 0,
    mastery_status: null,
    mastery_score: null,
  };
}

const NODES: GraphSubgraphNode[] = [
  makeNode(1, "Machine Learning", "A branch of artificial intelligence"),
  makeNode(2, "Neural Networks", "Computing systems inspired by biological neural networks"),
  makeNode(3, "Linear Algebra", "Mathematical discipline dealing with vectors"),
];

describe("searchNodes", () => {
  const index = buildSearchIndex(NODES);

  it("returns empty set for empty query", () => {
    expect(searchNodes(index, "")).toEqual(new Set());
    expect(searchNodes(index, "   ")).toEqual(new Set());
  });

  it("finds node by exact match", () => {
    const result = searchNodes(index, "Machine Learning");
    expect(result.has("1")).toBe(true);
  });

  it("finds node by prefix match", () => {
    const result = searchNodes(index, "Mach");
    expect(result.has("1")).toBe(true);
  });

  it("finds node by fuzzy match", () => {
    const result = searchNodes(index, "Machnie");
    expect(result.has("1")).toBe(true);
  });

  it("finds node by description match", () => {
    const result = searchNodes(index, "biological");
    expect(result.has("2")).toBe(true);
  });

  it("returns empty set for no match", () => {
    const result = searchNodes(index, "xyzzyplugh");
    expect(result.size).toBe(0);
  });
});
