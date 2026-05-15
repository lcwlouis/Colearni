import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

import { TrailGraph } from "@/app/trails/[id]/components/TrailGraph";
import type { ConceptEdge, ConceptNode, Trail } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  getConcept: vi.fn(async (_workspaceId: string, _trailId: string, conceptId: string) => ({
    concept: {
      id: conceptId,
      trail_id: "trail-1",
      slug: conceptId,
      title: conceptId,
      node_type: "concept",
      concept_level: "topic",
      difficulty: "beginner",
      bloom_level: "understand",
      mastery_check_labels: [],
      metadata_json: {},
    },
    prerequisites: [],
    contained_nodes: [],
    containing_nodes: [],
    related: [],
    mastery: null,
    sources: [],
  })),
}));

vi.mock("@xyflow/react", async () => {
  const actual = await vi.importActual<typeof import("@xyflow/react")>("@xyflow/react");
  return {
    ...actual,
    ReactFlow: ({
      nodes,
      onNodeClick,
      onNodeDoubleClick,
      onPaneClick,
      children,
    }: {
      nodes: Array<{ id: string; data: { label: React.ReactNode } }>;
      onNodeClick?: (event: unknown, node: { id: string }) => void;
      onNodeDoubleClick?: (event: unknown, node: { id: string }) => void;
      onPaneClick?: () => void;
      children?: React.ReactNode;
    }) => (
      <div>
        {nodes.map((node) => (
          <button
            key={node.id}
            type="button"
            onClick={() => onNodeClick?.({}, node)}
            onDoubleClick={() => onNodeDoubleClick?.({}, node)}
          >
            {node.data.label}
          </button>
        ))}
        <button type="button" onClick={() => onPaneClick?.()}>
          Pane
        </button>
        {children}
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

  test("renders layout controls and neighbor toggle", () => {
    renderGraph();

    expect(screen.getByRole("button", { name: "Freeform" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Hierarchy" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Radial" })).toBeInTheDocument();
    expect(screen.getByLabelText("Neighbors only")).toBeInTheDocument();
  });

  test("search focuses a matching concept", async () => {
    renderGraph();

    await userEvent.type(screen.getByPlaceholderText("Search concepts"), "basis");

    expect(screen.getByText("Basis")).toBeInTheDocument();
    expect(screen.getByText("Selected: Basis")).toBeInTheDocument();
  });

  test("renders graph legends", async () => {
    renderGraph();

    expect(screen.getByRole("button", { name: "Legend" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Legend" }));

    expect(screen.getByText("Learning status")).toBeInTheDocument();
    expect(screen.getByText("A -> B: A before B")).toBeInTheDocument();
    expect(screen.getByText("B = Beginner")).toBeInTheDocument();
  });

  test("single click selects and pane click clears selection", async () => {
    renderGraph();

    await userEvent.click(screen.getByRole("button", { name: /Vectors/ }));
    expect(screen.getByText("Selected: Vectors")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Pane" }));
    expect(screen.getByText("Select a node to highlight its connections.")).toBeInTheDocument();
  });
});

function renderGraph() {
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
}

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
