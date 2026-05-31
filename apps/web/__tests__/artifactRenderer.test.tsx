import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import {
  ArtifactErrorBoundary,
  ArtifactRenderer,
} from "@/components/artifacts/ArtifactRenderer";
import type {
  ComparisonCardEnvelope,
  MiniGraphEnvelope,
  SimulationSliderEnvelope,
  TimelineEnvelope,
  WorkedExampleEnvelope,
} from "@/lib/artifacts";

// Mermaid is async + DOM-heavy; mock it like TutorPanel.test.tsx so mini_graph
// renders deterministically in jsdom.
vi.mock("mermaid", () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn(async (_id: string, chart: string) => ({
      svg: `<svg xmlns="http://www.w3.org/2000/svg"><text>${chart.trim()}</text></svg>`,
    })),
  },
}));

function workedExampleEnvelope(): WorkedExampleEnvelope {
  return {
    artifact_version: 1,
    kind: "worked_example",
    title: "Solving 2x + 3 = 11",
    caption: "A linear equation worked end to end.",
    text_fallback: "Step 1: subtract 3. Step 2: divide by 2. Answer: x = 4.",
    provenance: {
      source_ids: [],
      visibility: "local_only",
      citations: [],
    },
    data: {
      steps: [
        { label: "Isolate the term", detail: "Subtract 3 from both sides." },
        { label: "Solve for x", detail: "Divide both sides by 2." },
      ],
      final_answer: "x = 4",
    },
  };
}

function comparisonCardEnvelope(): ComparisonCardEnvelope {
  return {
    artifact_version: 1,
    kind: "comparison_card",
    title: "TCP vs UDP",
    caption: null,
    text_fallback:
      "TCP is reliable and ordered; UDP is fast and connectionless.",
    provenance: {
      source_ids: [],
      visibility: "local_only",
      citations: [],
    },
    data: {
      items: ["TCP", "UDP"],
      criteria: [
        { label: "Reliability", values: ["Reliable", "Best-effort"] },
        { label: "Ordering", values: ["Ordered", "Unordered"] },
      ],
    },
  };
}

function timelineEnvelope(): TimelineEnvelope {
  return {
    artifact_version: 1,
    kind: "timeline",
    title: "Space race milestones",
    caption: null,
    text_fallback: "1957 Sputnik. 1969 Apollo 11 lands on the Moon.",
    provenance: {
      source_ids: [],
      visibility: "local_only",
      citations: [],
    },
    data: {
      events: [
        { label: "Sputnik launched", when: "1957", note: null },
        { label: "Apollo 11", when: "1969", note: "First Moon landing" },
      ],
    },
  };
}

function miniGraphEnvelope(): MiniGraphEnvelope {
  return {
    artifact_version: 1,
    kind: "mini_graph",
    title: "Water cycle",
    caption: null,
    text_fallback: "Evaporation leads to condensation leads to precipitation.",
    provenance: {
      source_ids: [],
      visibility: "local_only",
      citations: [],
    },
    data: {
      nodes: [
        { id: "a", label: "Evaporation" },
        { id: "b", label: "Condensation" },
        { id: "c", label: "Precipitation" },
      ],
      edges: [
        { source: "a", target: "b", label: "rises" },
        { source: "b", target: "c", label: null },
      ],
    },
  };
}

function simulationSliderEnvelope(): SimulationSliderEnvelope {
  return {
    artifact_version: 1,
    kind: "simulation_slider",
    title: "Linear function explorer",
    caption: null,
    text_fallback:
      "y = m*x + b. Drag the sliders to change slope and intercept.",
    provenance: {
      source_ids: [],
      visibility: "local_only",
      citations: [],
    },
    data: {
      sim_kind: "linear",
      parameters: [
        { name: "m", label: "Slope", min: -5, max: 5, default: 2, step: 0.1 },
        {
          name: "b",
          label: "Intercept",
          min: -10,
          max: 10,
          default: 1,
          step: null,
        },
      ],
      x_label: "x",
      y_label: "y",
      x_range: { min: 0, max: 10 },
      prompt: "Predict what happens to the line as the slope grows.",
      // Backend-owned oracle (mirrors precompute_simulation at the defaults).
      precomputed: {
        at_defaults: [
          { x: 0, y: 1 },
          { x: 2.5, y: 6 },
          { x: 5, y: 11 },
          { x: 7.5, y: 16 },
          { x: 10, y: 21 },
        ],
        y_bounds: { min: 1, max: 21 },
      },
    },
  };
}

describe("ArtifactRenderer", () => {
  test("renders a valid worked_example with title, steps, and final answer", () => {
    render(<ArtifactRenderer envelope={workedExampleEnvelope()} />);

    expect(screen.getByTestId("artifact-worked-example")).toBeInTheDocument();
    expect(screen.getByText("Solving 2x + 3 = 11")).toBeInTheDocument();
    expect(screen.getByText("Isolate the term")).toBeInTheDocument();
    expect(screen.getByText("Subtract 3 from both sides.")).toBeInTheDocument();
    expect(screen.getByText("Solve for x")).toBeInTheDocument();
    expect(screen.getByText("x = 4")).toBeInTheDocument();
    expect(
      screen.queryByTestId("artifact-text-fallback"),
    ).not.toBeInTheDocument();
  });

  test("renders a valid comparison_card as a table with the right cells", () => {
    render(<ArtifactRenderer envelope={comparisonCardEnvelope()} />);

    const table = screen.getByRole("table");
    expect(table).toBeInTheDocument();

    // Column headers (items).
    expect(
      screen.getByRole("columnheader", { name: "TCP" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: "UDP" }),
    ).toBeInTheDocument();

    // Row headers (criteria) + cells (values).
    expect(
      screen.getByRole("rowheader", { name: "Reliability" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Reliable")).toBeInTheDocument();
    expect(screen.getByText("Best-effort")).toBeInTheDocument();
    expect(screen.getByText("Ordered")).toBeInTheDocument();
    expect(screen.getByText("Unordered")).toBeInTheDocument();

    expect(
      screen.queryByTestId("artifact-text-fallback"),
    ).not.toBeInTheDocument();
  });

  test("renders a valid timeline with events, markers, and notes", () => {
    render(<ArtifactRenderer envelope={timelineEnvelope()} />);

    expect(screen.getByTestId("artifact-timeline")).toBeInTheDocument();
    expect(screen.getByText("Sputnik launched")).toBeInTheDocument();
    expect(screen.getByText("1957")).toBeInTheDocument();
    expect(screen.getByText("Apollo 11")).toBeInTheDocument();
    expect(screen.getByText("First Moon landing")).toBeInTheDocument();
    expect(
      screen.queryByTestId("artifact-text-fallback"),
    ).not.toBeInTheDocument();
  });

  test("degrades a timeline with no events to text_fallback", () => {
    const envelope = timelineEnvelope();
    (envelope.data as { events: unknown }).events = [];

    render(<ArtifactRenderer envelope={envelope} />);

    expect(screen.getByTestId("artifact-text-fallback")).toHaveTextContent(
      "1957 Sputnik. 1969 Apollo 11 lands on the Moon.",
    );
    expect(screen.queryByTestId("artifact-timeline")).not.toBeInTheDocument();
  });

  test("renders a valid mini_graph through the Mermaid flowchart path", async () => {
    render(<ArtifactRenderer envelope={miniGraphEnvelope()} />);

    expect(screen.getByTestId("artifact-mini-graph")).toBeInTheDocument();
    // The mocked Mermaid render echoes the flowchart definition into the SVG.
    expect(await screen.findByText(/flowchart TD/)).toBeInTheDocument();
    expect(
      screen.queryByTestId("artifact-text-fallback"),
    ).not.toBeInTheDocument();
  });

  test("degrades a mini_graph with missing nodes to text_fallback", () => {
    const envelope = miniGraphEnvelope();
    (envelope.data as { nodes: unknown }).nodes = [];

    render(<ArtifactRenderer envelope={envelope} />);

    expect(screen.getByTestId("artifact-text-fallback")).toHaveTextContent(
      "Evaporation leads to condensation leads to precipitation.",
    );
    expect(screen.queryByTestId("artifact-mini-graph")).not.toBeInTheDocument();
  });

  test("renders a valid simulation_slider with sliders, plot, and prompt", () => {
    render(<ArtifactRenderer envelope={simulationSliderEnvelope()} />);

    expect(
      screen.getByTestId("artifact-simulation-slider"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("artifact-simulation-curve")).toBeInTheDocument();
    expect(
      screen.getByText("Predict what happens to the line as the slope grows."),
    ).toBeInTheDocument();
    // One range slider per parameter.
    const sliders = screen.getAllByRole("slider");
    expect(sliders).toHaveLength(2);
    expect(screen.getByLabelText("Slope")).toBeInTheDocument();
    expect(
      screen.queryByTestId("artifact-text-fallback"),
    ).not.toBeInTheDocument();
  });

  test("simulation_slider live-eval at defaults matches precomputed.at_defaults", () => {
    // The default-coefficient curve must trace the backend oracle points. We
    // reconstruct the polyline's first/last y from the rendered points string
    // and confirm the curve spans the full y_bounds (y=1 at x=0, y=21 at x=10).
    render(<ArtifactRenderer envelope={simulationSliderEnvelope()} />);
    const curve = screen.getByTestId("artifact-simulation-curve");
    const points = (curve.getAttribute("points") ?? "")
      .trim()
      .split(" ")
      .map((pair) => pair.split(",").map(Number));
    expect(points).toHaveLength(5);
    // y=1 is the min bound -> bottom of the plot (largest svg-y); y=21 is the
    // max bound -> top of the plot (smallest svg-y). Monotonic increasing data
    // therefore produces strictly decreasing svg-y values.
    const svgYs = points.map((p) => p[1]);
    for (let i = 1; i < svgYs.length; i += 1) {
      expect(svgYs[i]).toBeLessThan(svgYs[i - 1]);
    }
  });

  test("degrades a simulation_slider with an unknown sim_kind to the static plot", () => {
    const envelope = simulationSliderEnvelope();
    (envelope.data as { sim_kind: unknown }).sim_kind = "mystery_curve";

    render(<ArtifactRenderer envelope={envelope} />);

    // Static plot from precomputed survives; no interactive sliders are shown.
    expect(
      screen.getByTestId("artifact-simulation-slider"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("artifact-simulation-curve")).toBeInTheDocument();
    expect(screen.queryAllByRole("slider")).toHaveLength(0);
    expect(
      screen.queryByTestId("artifact-text-fallback"),
    ).not.toBeInTheDocument();
  });

  test("degrades a simulation_slider with missing precomputed to text_fallback", () => {
    const envelope = simulationSliderEnvelope();
    (envelope.data as { precomputed: unknown }).precomputed = null;

    render(<ArtifactRenderer envelope={envelope} />);

    expect(screen.getByTestId("artifact-text-fallback")).toHaveTextContent(
      "Drag the sliders",
    );
    expect(
      screen.queryByTestId("artifact-simulation-slider"),
    ).not.toBeInTheDocument();
  });

  test("degrades an UNKNOWN kind to text_fallback", () => {
    const envelope = {
      artifact_version: 1,
      kind: "mystery_widget",
      title: "Mystery",
      caption: null,
      text_fallback: "This widget kind is not supported yet.",
      provenance: { source_ids: [], visibility: "local_only", citations: [] },
      data: {},
    };

    render(<ArtifactRenderer envelope={envelope} />);

    expect(screen.getByTestId("artifact-text-fallback")).toHaveTextContent(
      "This widget kind is not supported yet.",
    );
    expect(
      screen.queryByTestId("artifact-comparison-card"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("artifact-worked-example"),
    ).not.toBeInTheDocument();
  });

  test("degrades a comparison_card with a values/items length mismatch", () => {
    const envelope = comparisonCardEnvelope();
    // Drop one value so a criterion no longer matches the item count.
    envelope.data.criteria[0].values = ["Reliable"];

    render(<ArtifactRenderer envelope={envelope} />);

    expect(screen.getByTestId("artifact-text-fallback")).toHaveTextContent(
      "TCP is reliable and ordered; UDP is fast and connectionless.",
    );
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  test("degrades a worked_example with missing data to text_fallback", () => {
    const envelope = {
      ...workedExampleEnvelope(),
      data: undefined,
    };

    render(<ArtifactRenderer envelope={envelope} />);

    expect(screen.getByTestId("artifact-text-fallback")).toHaveTextContent(
      "Step 1: subtract 3. Step 2: divide by 2. Answer: x = 4.",
    );
  });

  test("falls back when the envelope is not an object", () => {
    render(<ArtifactRenderer envelope={null} />);

    expect(screen.getByTestId("artifact-text-fallback")).toBeInTheDocument();
  });
});

describe("ArtifactErrorBoundary", () => {
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    // React logs caught render errors to console.error; silence it for clean
    // test output without hiding genuine failures.
    consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  test("catches a thrown render error and shows text_fallback", () => {
    function Throwing(): never {
      throw new Error("render exploded");
    }

    render(
      <ArtifactErrorBoundary fallbackText="Safe degraded text.">
        <Throwing />
      </ArtifactErrorBoundary>,
    );

    expect(screen.getByTestId("artifact-text-fallback")).toHaveTextContent(
      "Safe degraded text.",
    );
  });

  test("shows a generic message when no fallback text is available", () => {
    function Throwing(): never {
      throw new Error("render exploded");
    }

    render(
      <ArtifactErrorBoundary fallbackText={null}>
        <Throwing />
      </ArtifactErrorBoundary>,
    );

    expect(screen.getByTestId("artifact-text-fallback")).toHaveTextContent(
      "could not be displayed",
    );
  });
});
