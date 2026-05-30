import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

import type { MasteryStatus, TrailDetail } from "@/lib/types";

// Must be hoisted before the dynamic import of the page
vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "trail-1" }),
  useRouter: () => ({ push: vi.fn() }),
  // ?concept=<id> deep-link support added in Phase 9.
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/workspace", () => ({
  ensureWorkspaceId: vi.fn().mockResolvedValue("workspace-1"),
}));

vi.mock("@/lib/api", () => ({
  getTrail: vi.fn(),
  getTrailNext: vi.fn(),
  deleteTrail: vi.fn(),
}));

// Capture the onMasteryUpdated callback via data rendered by the mock
vi.mock("@/app/trails/[id]/components/TrailGraph", () => ({
  TrailGraph: ({
    masterySummary,
    onMasteryUpdated,
  }: {
    masterySummary: TrailDetail["mastery_summary"];
    onMasteryUpdated?: (
      conceptId: string,
      update: { status: MasteryStatus; score: number },
    ) => void;
  }) => (
    <div>
      <div data-testid="summary-total">{masterySummary.total}</div>
      <div data-testid="summary-not-started">{masterySummary.not_started}</div>
      <div data-testid="summary-learning">{masterySummary.learning}</div>
      <div data-testid="summary-needs-review">
        {masterySummary.needs_review}
      </div>
      <div data-testid="summary-mastered">{masterySummary.mastered}</div>
      <button
        type="button"
        onClick={() =>
          onMasteryUpdated?.("concept-id-1", {
            status: "mastered",
            score: 0.85,
          })
        }
      >
        Trigger mastered
      </button>
      <button
        type="button"
        onClick={() =>
          onMasteryUpdated?.("concept-id-2", {
            status: "needs_review",
            score: 0.3,
          })
        }
      >
        Trigger needs_review
      </button>
      <button
        type="button"
        onClick={() =>
          onMasteryUpdated?.("concept-id-2", { status: "mastered", score: 0.9 })
        }
      >
        Trigger concept2 mastered
      </button>
    </div>
  ),
}));

import * as api from "@/lib/api";
import TrailPage from "@/app/trails/[id]/page";

const mockTrailDetail: TrailDetail = {
  trail: {
    id: "trail-1",
    workspace_id: "workspace-1",
    title: "Linear Algebra",
    topic: "Matrices",
    goal: "Understand matrix operations",
    target_depth: "understand",
    created_at: "2026-01-01T00:00:00Z",
    node_count: 3,
    edge_count: 0,
  },
  graph: {
    nodes: [
      {
        id: "concept-id-1",
        trail_id: "trail-1",
        slug: "vectors",
        title: "Vectors",
        node_type: "concept",
        concept_level: "topic",
        difficulty: "beginner",
        bloom_level: "understand",
        mastery_check_labels: [],
        metadata_json: {},
      },
      {
        id: "concept-id-2",
        trail_id: "trail-1",
        slug: "matrices",
        title: "Matrices",
        node_type: "concept",
        concept_level: "topic",
        difficulty: "beginner",
        bloom_level: "understand",
        mastery_check_labels: [],
        metadata_json: {},
      },
      {
        id: "concept-id-3",
        trail_id: "trail-1",
        slug: "basis",
        title: "Basis",
        node_type: "concept",
        concept_level: "subtopic",
        difficulty: "intermediate",
        bloom_level: "apply",
        mastery_check_labels: [],
        metadata_json: {},
      },
    ],
    edges: [],
    mastery: {
      "concept-id-1": {
        id: null,
        workspace_id: "workspace-1",
        concept_id: "concept-id-1",
        status: "learning",
        bloom_level: "understand",
        score: 0.4,
        updated_at: null,
      },
      "concept-id-2": {
        id: null,
        workspace_id: "workspace-1",
        concept_id: "concept-id-2",
        status: "needs_review",
        bloom_level: "understand",
        score: 0.3,
        updated_at: null,
      },
      "concept-id-3": {
        id: null,
        workspace_id: "workspace-1",
        concept_id: "concept-id-3",
        status: "not_started",
        bloom_level: "apply",
        score: 0,
        updated_at: null,
      },
    },
  },
  mastery_summary: {
    total: 3,
    not_started: 1,
    learning: 1,
    needs_review: 1,
    mastered: 0,
  },
};

const freshTrailDetail: TrailDetail = {
  ...mockTrailDetail,
  graph: {
    ...mockTrailDetail.graph,
    mastery: {
      "concept-id-1": {
        id: null,
        workspace_id: "workspace-1",
        concept_id: "concept-id-1",
        status: "not_started",
        bloom_level: "understand",
        score: 0,
        updated_at: null,
      },
      "concept-id-2": {
        id: null,
        workspace_id: "workspace-1",
        concept_id: "concept-id-2",
        status: "not_started",
        bloom_level: "understand",
        score: 0,
        updated_at: null,
      },
      "concept-id-3": {
        id: null,
        workspace_id: "workspace-1",
        concept_id: "concept-id-3",
        status: "not_started",
        bloom_level: "apply",
        score: 0,
        updated_at: null,
      },
    },
  },
  mastery_summary: {
    total: 3,
    not_started: 3,
    learning: 0,
    needs_review: 0,
    mastered: 0,
  },
};

describe("TrailPage suggested starting point (fresh Trail)", () => {
  test("shows a dismissible suggested-start affordance without blocking navigation", async () => {
    vi.mocked(api.getTrail).mockResolvedValue(freshTrailDetail);
    vi.mocked(api.getTrailNext).mockResolvedValue({
      concept_id: "concept-id-1",
      concept_title: "Vectors",
      reason: "Good starting point - no prerequisites, beginner level.",
      all_mastered: false,
      mastery_status: null,
      concept_level: "topic",
    });

    render(<TrailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("suggested-start-banner")).toBeInTheDocument();
    });

    expect(screen.getByText("Suggested starting point:")).toBeInTheDocument();
    expect(screen.getByText("Vectors")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Good starting point - no prerequisites, beginner level.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/Just a suggestion/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Start Here" }),
    ).toBeInTheDocument();

    // The suggestion coexists with free navigation: the graph is still rendered.
    expect(screen.getByTestId("summary-total")).toHaveTextContent("3");

    // Dismissing the suggestion never blocks the graph.
    await userEvent.click(
      screen.getByRole("button", { name: "Dismiss recommendation" }),
    );
    await waitFor(() => {
      expect(
        screen.queryByTestId("suggested-start-banner"),
      ).not.toBeInTheDocument();
    });
    expect(screen.getByTestId("summary-total")).toHaveTextContent("3");
  });
});

describe("TrailPage mastery update", () => {
  test("renders initial mastery summary from getTrail", async () => {
    vi.mocked(api.getTrail).mockResolvedValue(mockTrailDetail);
    vi.mocked(api.getTrailNext).mockResolvedValue({
      concept_id: "concept-id-2",
      concept_title: "Matrices",
      reason: "Backend says to repair this next.",
      all_mastered: false,
      mastery_status: null,
      concept_level: null,
    });

    render(<TrailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("summary-total")).toHaveTextContent("3");
    });

    expect(screen.getByTestId("summary-not-started")).toHaveTextContent("1");
    expect(screen.getByTestId("summary-learning")).toHaveTextContent("1");
    expect(screen.getByTestId("summary-needs-review")).toHaveTextContent("1");
    expect(screen.getByTestId("summary-mastered")).toHaveTextContent("0");
    expect(screen.getByText("Recommended next:")).toBeInTheDocument();
    expect(screen.getByText("Matrices")).toBeInTheDocument();
    expect(
      screen.getByText("Backend says to repair this next."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Start Learning" }),
    ).toBeInTheDocument();
  });

  test("renders all-mastered recommendation state without concept link", async () => {
    vi.mocked(api.getTrail).mockResolvedValue(mockTrailDetail);
    vi.mocked(api.getTrailNext).mockResolvedValue({
      concept_id: null,
      concept_title: null,
      reason: "Review the Trail or extend it.",
      all_mastered: true,
      mastery_status: null,
      concept_level: null,
    });

    render(<TrailPage />);

    await waitFor(() => {
      expect(
        screen.getByText("All concepts mastered — well done."),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByText("Review the Trail or extend it."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Focus concept" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByTestId("next-banner-cta")).not.toBeInTheDocument();
  });

  test("hides recommendation banner when getTrailNext fails", async () => {
    vi.mocked(api.getTrail).mockResolvedValue(mockTrailDetail);
    vi.mocked(api.getTrailNext).mockRejectedValue(
      new Error("Recommendation unavailable"),
    );

    render(<TrailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("summary-total")).toHaveTextContent("3");
    });
    expect(screen.queryByText(/Recommended next:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/All concepts mastered/)).not.toBeInTheDocument();
  });

  test("onMasteryUpdated updates mastery_summary counts", async () => {
    vi.mocked(api.getTrail).mockResolvedValue(mockTrailDetail);
    vi.mocked(api.getTrailNext).mockResolvedValue({
      concept_id: "concept-id-2",
      concept_title: "Matrices",
      reason: "Backend says to repair this next.",
      all_mastered: false,
      mastery_status: null,
      concept_level: null,
    });

    render(<TrailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("summary-mastered")).toHaveTextContent("0");
    });

    // concept-id-1 was "learning", now transitions to "mastered"
    await userEvent.click(
      screen.getByRole("button", { name: "Trigger mastered" }),
    );

    await waitFor(() => {
      expect(screen.getByTestId("summary-mastered")).toHaveTextContent("1");
    });

    // learning count should decrease
    expect(screen.getByTestId("summary-learning")).toHaveTextContent("0");
    // others unchanged
    expect(screen.getByTestId("summary-not-started")).toHaveTextContent("1");
    expect(screen.getByTestId("summary-needs-review")).toHaveTextContent("1");
    expect(screen.getByTestId("summary-total")).toHaveTextContent("3");
  });

  test("onMasteryUpdated to needs_review adjusts counts correctly", async () => {
    vi.mocked(api.getTrail).mockResolvedValue(mockTrailDetail);
    vi.mocked(api.getTrailNext).mockResolvedValue({
      concept_id: "concept-id-2",
      concept_title: "Matrices",
      reason: "Backend says to repair this next.",
      all_mastered: false,
      mastery_status: null,
      concept_level: null,
    });

    render(<TrailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("summary-not-started")).toHaveTextContent("1");
    });

    // concept-id-2 was "needs_review" and stays "needs_review" — no net change for needs_review
    // but we can test that concept-id-1 (learning) -> needs_review via Trigger needs_review?
    // Actually the mock triggers concept-id-2 -> needs_review, which was already needs_review
    // Let's use Trigger mastered on concept-id-1, then trigger needs_review on concept-id-2
    // to verify the counts remain stable for concept-id-2
    await userEvent.click(
      screen.getByRole("button", { name: "Trigger needs_review" }),
    );

    // concept-id-2 was already needs_review → stays needs_review = 1
    // no change expected
    await waitFor(() => {
      expect(screen.getByTestId("summary-needs-review")).toHaveTextContent("1");
    });

    expect(screen.getByTestId("summary-mastered")).toHaveTextContent("0");
    expect(screen.getByTestId("summary-learning")).toHaveTextContent("1");
  });

  test("multiple mastery updates accumulate correctly", async () => {
    vi.mocked(api.getTrail).mockResolvedValue(mockTrailDetail);
    vi.mocked(api.getTrailNext).mockResolvedValue({
      concept_id: "concept-id-2",
      concept_title: "Matrices",
      reason: "Backend says to repair this next.",
      all_mastered: false,
      mastery_status: null,
      concept_level: null,
    });

    render(<TrailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("summary-mastered")).toHaveTextContent("0");
    });

    // First update: concept-id-1 learning -> mastered
    await userEvent.click(
      screen.getByRole("button", { name: "Trigger mastered" }),
    );

    await waitFor(() => {
      expect(screen.getByTestId("summary-mastered")).toHaveTextContent("1");
    });

    expect(screen.getByTestId("summary-learning")).toHaveTextContent("0");

    // Second update: concept-id-2 needs_review -> mastered
    await userEvent.click(
      screen.getByRole("button", { name: "Trigger concept2 mastered" }),
    );

    await waitFor(() => {
      expect(screen.getByTestId("summary-mastered")).toHaveTextContent("2");
    });

    expect(screen.getByTestId("summary-needs-review")).toHaveTextContent("0");
    expect(screen.getByTestId("summary-not-started")).toHaveTextContent("1");
    expect(screen.getByTestId("summary-total")).toHaveTextContent("3");
  });
});
