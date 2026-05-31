import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { TrailGraph } from "@/app/(app)/trails/[id]/components/TrailGraph";
import type { ConceptEdge, ConceptNode, Trail } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  getConceptSources: vi.fn(async () => ({ sources: [] })),
  streamConceptPrimer: vi.fn(
    async (
      _workspaceId: string,
      _trailId: string,
      _conceptId: string,
      callbacks: {
        onDone: (primer: {
          overview: string;
          key_terms: never[];
          sample_questions: never[];
          version: number;
        }) => void;
      },
    ) => {
      callbacks.onDone({
        overview: "",
        key_terms: [],
        sample_questions: [],
        version: 1,
      });
    },
  ),
  getConcept: vi.fn(
    async (_workspaceId: string, _trailId: string, conceptId: string) => ({
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
      mastery: {
        id: null,
        workspace_id: "workspace-1",
        concept_id: conceptId,
        status: "not_started",
        bloom_level: "understand",
        score: 0,
        updated_at: null,
      },
      sources: [],
    }),
  ),
}));

const {
  mockFitView,
  mockSetViewport,
  mockSetCenter,
  mockGetViewport,
  mockGetZoom,
  getMockViewport,
  resetMockViewport,
  setMockViewport,
  setMobileViewport,
  getMobileViewport,
} = vi.hoisted(() => {
  let mockViewport = { x: 0, y: 0, zoom: 0.5 };
  let mobileViewport = false;

  return {
    mockFitView: vi.fn(async () => true),
    mockSetViewport: vi.fn(
      async (viewport: { x: number; y: number; zoom: number }) => {
        mockViewport = viewport;
        return true;
      },
    ),
    mockSetCenter: vi.fn(
      async (x: number, y: number, options?: { zoom?: number }) => {
        mockViewport = {
          x,
          y,
          zoom: options?.zoom ?? mockViewport.zoom,
        };
        return true;
      },
    ),
    mockGetViewport: vi.fn(() => mockViewport),
    mockGetZoom: vi.fn(() => mockViewport.zoom),
    getMockViewport: () => mockViewport,
    resetMockViewport: () => {
      mockViewport = { x: 0, y: 0, zoom: 0.5 };
    },
    setMockViewport: (viewport: { x: number; y: number; zoom: number }) => {
      mockViewport = viewport;
    },
    setMobileViewport: (mobile: boolean) => {
      mobileViewport = mobile;
    },
    getMobileViewport: () => mobileViewport,
  };
});

vi.mock("@xyflow/react", async () => {
  const React = await import("react");
  const actual =
    await vi.importActual<typeof import("@xyflow/react")>("@xyflow/react");
  const instance = {
    fitView: mockFitView,
    setViewport: mockSetViewport,
    setCenter: mockSetCenter,
    getViewport: mockGetViewport,
    getZoom: mockGetZoom,
  };

  return {
    ...actual,
    ReactFlow: ({
      nodes,
      edges,
      onInit,
      onMove,
      onNodeClick,
      onNodeDoubleClick,
      onPaneClick,
      children,
    }: {
      nodes: Array<{ id: string; data: { label: React.ReactNode } }>;
      edges: Array<{ id: string; label?: React.ReactNode }>;
      onInit?: (instance: {
        fitView: typeof mockFitView;
        setViewport: typeof mockSetViewport;
        setCenter: typeof mockSetCenter;
        getViewport: typeof mockGetViewport;
        getZoom: typeof mockGetZoom;
      }) => void;
      onMove?: (
        _event: unknown,
        viewport: { x: number; y: number; zoom: number },
      ) => void;
      onNodeClick?: (event: unknown, node: { id: string }) => void;
      onNodeDoubleClick?: (event: unknown, node: { id: string }) => void;
      onPaneClick?: () => void;
      children?: React.ReactNode;
    }) => {
      React.useEffect(() => {
        onInit?.(instance);
      }, [onInit]);

      return (
        <div className="react-flow">
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
          <button
            type="button"
            onClick={() => {
              setMockViewport({ x: 120, y: 40, zoom: 0.35 });
              onMove?.(null, getMockViewport());
            }}
          >
            Zoom overview
          </button>
          <button
            type="button"
            onClick={() => {
              setMockViewport({ x: 120, y: 40, zoom: 1 });
              onMove?.(null, getMockViewport());
            }}
          >
            Zoom detail
          </button>
          {edges.map((edge) =>
            edge.label ? <span key={edge.id}>{edge.label}</span> : null,
          )}
          {children}
        </div>
      );
    },
    Background: () => null,
    Controls: ({
      position,
      style,
    }: {
      position?: string;
      style?: { bottom?: number; left?: number };
    }) => (
      <div
        data-testid="reactflow-controls"
        data-position={position}
        data-bottom={style?.bottom}
        data-left={style?.left}
      />
    ),
    MiniMap: () => null,
    Panel: ({ children }: { children: React.ReactNode }) => (
      <div>{children}</div>
    ),
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

const mastery = {
  vectors: {
    id: null,
    workspace_id: "workspace-1",
    concept_id: "vectors",
    status: "learning" as const,
    bloom_level: "understand" as const,
    score: 0.4,
    updated_at: null,
  },
  matrices: {
    id: null,
    workspace_id: "workspace-1",
    concept_id: "matrices",
    status: "mastered" as const,
    bloom_level: "understand" as const,
    score: 0.9,
    updated_at: null,
  },
  basis: {
    id: null,
    workspace_id: "workspace-1",
    concept_id: "basis",
    status: "not_started" as const,
    bloom_level: "understand" as const,
    score: 0,
    updated_at: null,
  },
};

describe("TrailGraph", () => {
  beforeEach(() => {
    resetMockViewport();
    mockFitView.mockClear();
    mockSetViewport.mockClear();
    mockSetCenter.mockClear();
    mockGetViewport.mockClear();
    mockGetZoom.mockClear();
    Object.defineProperty(HTMLDivElement.prototype, "clientWidth", {
      configurable: true,
      get() {
        return document.querySelector('[aria-label="Close"]') ? 700 : 1000;
      },
    });
    setMobileViewport(false);
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      configurable: true,
      value: vi.fn().mockImplementation((query: string) => {
        const isMobileQuery = query.includes("max-width: 767px");
        const matches = isMobileQuery ? getMobileViewport() : false;
        return {
          matches,
          media: query,
          onchange: null,
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          addListener: vi.fn(),
          removeListener: vi.fn(),
          dispatchEvent: vi.fn(),
        };
      }),
    });
  });

  test("renders graph node labels", () => {
    render(
      <TrailGraph
        workspaceId="workspace-1"
        trail={trail}
        graph={{ nodes, edges, mastery }}
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

    expect(
      screen.getByRole("button", { name: "Freeform" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Hierarchy" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Radial" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Neighbors only" }),
    ).toBeInTheDocument();
  });

  test("search focuses a matching concept", async () => {
    renderGraph();

    await userEvent.type(
      screen.getByPlaceholderText("Search concepts"),
      "basis",
    );

    expect(screen.getByText("Basis")).toBeInTheDocument();
    expect(screen.getByText("Selected: Basis")).toBeInTheDocument();
  });

  test("renders graph legends", async () => {
    renderGraph();

    const legendButtons = screen.getAllByRole("button", { name: "Legend" });
    expect(legendButtons.length).toBeGreaterThan(0);
    await userEvent.click(legendButtons[0]);

    expect(screen.getAllByText("Learning status").length).toBeGreaterThan(0);
    expect(screen.getAllByText("A -> B: A before B").length).toBeGreaterThan(0);
    expect(screen.getAllByText("B = Beginner").length).toBeGreaterThan(0);
  });

  test("single click selects and pane click clears selection", async () => {
    renderGraph();

    await userEvent.click(screen.getByRole("button", { name: /Vectors/ }));
    expect(screen.getByText("Selected: Vectors")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Pane" }));
    expect(
      screen.getByText("Select a node to highlight its connections."),
    ).toBeInTheDocument();
  });

  test("uses graph mastery records for summary metrics", () => {
    renderGraph();

    expect(screen.getByText("Learning")).toBeInTheDocument();
    expect(screen.getByText("Mastered")).toBeInTheDocument();
    expect(screen.getAllByText("1").length).toBeGreaterThan(0);
  });

  test("edge labels are on by default but only render when zoomed in", async () => {
    renderGraph();

    expect(
      screen.getByText("Edge labels appear when you zoom in closer."),
    ).toBeInTheDocument();
    expect(screen.queryByText("prerequisite")).not.toBeInTheDocument();
    expect(screen.queryByText("contains")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Zoom detail" }));

    expect(
      screen.queryByText("Edge labels appear when you zoom in closer."),
    ).not.toBeInTheDocument();
    expect(screen.getByText("prerequisite")).toBeInTheDocument();
    expect(screen.getByText("contains")).toBeInTheDocument();
  });

  test("Learn Mode also shows default edge labels when zoomed in", async () => {
    render(
      <TrailGraph
        workspaceId="workspace-1"
        trail={trail}
        graph={{ nodes, edges, mastery }}
        masterySummary={{
          total: 3,
          not_started: 3,
          learning: 0,
          needs_review: 0,
          mastered: 0,
        }}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Zoom detail" }));

    expect(screen.getByText("prerequisite")).toBeInTheDocument();
    expect(screen.getByText("contains")).toBeInTheDocument();
  });

  test("defaults to Learn Mode and hides Inspect-only tools", () => {
    render(
      <TrailGraph
        workspaceId="workspace-1"
        trail={trail}
        graph={{ nodes, edges, mastery }}
        masterySummary={{
          total: 3,
          not_started: 3,
          learning: 0,
          needs_review: 0,
          mastered: 0,
        }}
      />,
    );

    // Learn Mode is the default per docs/FRONTEND.md.
    expect(screen.getByRole("button", { name: "Learn" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "Inspect" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );

    // Power-user controls are hidden in Learn Mode.
    expect(
      screen.queryByRole("button", { name: "Tools" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Legend" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Hierarchy" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Neighbors only" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Edge labels" }),
    ).not.toBeInTheDocument();
  });

  test("opens initial concept when initialConceptId is provided", async () => {
    render(
      <TrailGraph
        workspaceId="workspace-1"
        trail={trail}
        graph={{ nodes, edges, mastery }}
        masterySummary={{
          total: 3,
          not_started: 3,
          learning: 0,
          needs_review: 0,
          mastered: 0,
        }}
        initialConceptId="matrices"
      />,
    );

    await screen.findByText("Selected: Matrices");
  });

  test("preserves the overview framing when opening and closing a concept", async () => {
    render(
      <TrailGraph
        workspaceId="workspace-1"
        trail={trail}
        graph={{ nodes, edges, mastery }}
        masterySummary={{
          total: 3,
          not_started: 3,
          learning: 0,
          needs_review: 0,
          mastered: 0,
        }}
      />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Zoom overview" }),
    );
    mockFitView.mockClear();
    mockSetViewport.mockClear();
    mockSetCenter.mockClear();

    await userEvent.click(screen.getByRole("button", { name: /Vectors/ }));
    await screen.findByRole("button", { name: "Close" });

    await waitFor(() => {
      expect(mockSetCenter).toHaveBeenCalledWith(
        expect.any(Number),
        expect.any(Number),
        expect.objectContaining({ zoom: 1, duration: 220 }),
      );
    });

    const viewportCallsBeforeClose = mockSetViewport.mock.calls.length;
    await userEvent.click(screen.getByRole("button", { name: "Close" }));

    await waitFor(() => {
      expect(mockSetViewport.mock.calls.length).toBeGreaterThan(
        viewportCallsBeforeClose,
      );
    });
  });

  test("keeps mobile graph controls above the slide-up concept card", async () => {
    setMobileViewport(true);
    renderGraph();

    await userEvent.click(screen.getByRole("button", { name: /Vectors/ }));
    await screen.findByRole("button", { name: "Close" });

    expect(screen.getByTestId("trail-graph-frame")).toHaveStyle({
      height: "calc(100% - 104px)",
    });
    expect(screen.getByTestId("reactflow-controls")).toHaveAttribute(
      "data-bottom",
      "120",
    );
  });
});

function renderGraph() {
  render(
    <TrailGraph
      workspaceId="workspace-1"
      trail={trail}
      graph={{ nodes, edges, mastery }}
      masterySummary={{
        total: 3,
        not_started: 3,
        learning: 0,
        needs_review: 0,
        mastered: 0,
      }}
    />,
  );
  // Inspect Mode exposes power-user controls (layout, filters, legend, metrics).
  // Learn Mode (the default) intentionally hides them — see TrailGraph mode toggle.
  act(() => {
    screen.getByRole("button", { name: "Inspect" }).click();
  });
}

function node(
  id: string,
  title: string,
  concept_level: ConceptNode["concept_level"],
): ConceptNode {
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
