import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { TrailGraph } from "@/app/trails/[id]/components/TrailGraph";
import type { ConceptEdge, ConceptNode, Trail } from "@/lib/types";

vi.mock("@xyflow/react", async () => {
  const actual = await vi.importActual<typeof import("@xyflow/react")>("@xyflow/react");
  return {
    ...actual,
    ReactFlow: ({ nodes }: { nodes: Array<{ data: { label: string } }> }) => (
      <div>
        {nodes.map((node) => (
          <span key={node.data.label}>{node.data.label}</span>
        ))}
      </div>
    ),
    Background: () => null,
    Controls: () => null,
    MiniMap: () => null,
    Panel: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  };
});

const trail: Trail = {
  id: "trail-1",
  workspace_id: "workspace-1",
  title: "Linear Algebra",
  topic: "Matrices",
  goal: "Understand matrix transformations",
  target_depth: "apply",
  created_at: "2026-01-01T00:00:00Z",
  node_count: 3,
  edge_count: 2,
};

const nodes: ConceptNode[] = [
  node("vectors", "Vectors", "topic"),
  node("matrices", "Matrices", "topic"),
  node("basis", "Basis", "subtopic"),
];

const edges: ConceptEdge[] = [
  edge("edge-1", "vectors", "matrices", "prerequisite"),
  edge("edge-2", "matrices", "basis", "contains"),
];

describe("TrailGraph", () => {
  test("renders graph node labels", () => {
    render(
      <TrailGraph
        workspaceId="workspace-1"
        trail={trail}
        graph={{ nodes, edges }}
        masterySummary={{
          total: 3,
          not_started: 3,
          learning: 0,
          needs_review: 0,
          mastered: 0,
        }}
      />,
    );

    expect(screen.getByText("Vectors")).toBeInTheDocument();
    expect(screen.getByText("Matrices")).toBeInTheDocument();
    expect(screen.getByText("Basis")).toBeInTheDocument();
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
    mastery_check_labels: [`check_${id}`],
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
