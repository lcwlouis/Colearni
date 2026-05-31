import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { sortTrailsForDashboard } from "@/app/(app)/dashboard/sortTrails";
import type { NextConceptResponse, Trail, TrailDetail } from "@/lib/types";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/workspace", () => ({
  ensureWorkspaceId: vi.fn().mockResolvedValue("workspace-1"),
}));

const listTrailsMock = vi.fn();
const getTrailMock = vi.fn();
const getTrailNextMock = vi.fn();

vi.mock("@/lib/api", () => ({
  listTrails: (...args: unknown[]) => listTrailsMock(...args),
  getTrail: (...args: unknown[]) => getTrailMock(...args),
  getTrailNext: (...args: unknown[]) => getTrailNextMock(...args),
  deleteTrail: vi.fn(),
}));

function trail(id: string, overrides: Partial<Trail> = {}): Trail {
  return {
    id,
    workspace_id: "workspace-1",
    title: overrides.title ?? `Trail ${id}`,
    topic: overrides.topic ?? "Topic",
    goal: overrides.goal ?? `Goal ${id}`,
    target_depth: "understand",
    created_at: overrides.created_at ?? "2026-01-01T00:00:00Z",
    node_count: overrides.node_count ?? 3,
    edge_count: overrides.edge_count ?? 1,
  };
}

function detail(t: Trail, status: "not_started" | "learning" | "needs_review" | "mastered"): TrailDetail {
  return {
    trail: t,
    graph: {
      nodes: [
        {
          id: `${t.id}-c1`,
          trail_id: t.id,
          slug: "c1",
          title: `${t.title} concept`,
          node_type: "concept",
          concept_level: "topic",
          difficulty: "beginner",
          bloom_level: "understand",
          mastery_check_labels: [],
          metadata_json: {},
        },
      ],
      edges: [],
      mastery: {
        [`${t.id}-c1`]: {
          id: null,
          workspace_id: "workspace-1",
          concept_id: `${t.id}-c1`,
          status,
          bloom_level: "understand",
          score: status === "mastered" ? 1 : status === "learning" ? 0.5 : 0,
          updated_at: status === "not_started" ? null : "2026-05-01T00:00:00Z",
        },
      },
    },
    mastery_summary: {
      total: 1,
      not_started: status === "not_started" ? 1 : 0,
      learning: status === "learning" ? 1 : 0,
      needs_review: status === "needs_review" ? 1 : 0,
      mastered: status === "mastered" ? 1 : 0,
    },
  };
}

function nextConcept(overrides: Partial<NextConceptResponse> = {}): NextConceptResponse {
  return {
    concept_id: overrides.concept_id ?? "backend-concept-1",
    concept_title: overrides.concept_title ?? "Backend recommendation",
    reason: overrides.reason ?? "Backend reason",
    all_mastered: overrides.all_mastered ?? false,
    mastery_status: overrides.mastery_status ?? null,
    concept_level: overrides.concept_level ?? null,
  };
}

async function loadPage() {
  const mod = await import("@/app/(app)/dashboard/page");
  return mod.default;
}

describe("Dashboard (home)", () => {
  test("sorts pinned trails first and supports dashboard sort modes", () => {
    const t1 = trail("t1", {
      created_at: "2026-03-01T00:00:00Z",
      title: "Algebra",
    });
    const t2 = trail("t2", {
      created_at: "2026-02-01T00:00:00Z",
      title: "Biology",
    });
    const t3 = trail("t3", {
      created_at: "2026-01-01T00:00:00Z",
      title: "Chemistry",
    });
    const progressByTrail = {
      t1: {
        detail: detail(t1, "learning"),
        total: 1,
        mastered: 0,
        learning: 1,
        needs_review: 0,
        not_started: 0,
        progress: 0.5,
        lastActivity: "2026-05-01T00:00:00Z",
      },
      t2: {
        detail: detail(t2, "mastered"),
        total: 1,
        mastered: 1,
        learning: 0,
        needs_review: 0,
        not_started: 0,
        progress: 1,
        lastActivity: "2026-04-01T00:00:00Z",
      },
      t3: {
        detail: detail(t3, "not_started"),
        total: 1,
        mastered: 0,
        learning: 0,
        needs_review: 0,
        not_started: 1,
        progress: 0,
        lastActivity: null,
      },
    };
    const pinnedIds = new Set(["t2", "t1"]);

    expect(
      sortTrailsForDashboard([t3, t2, t1], progressByTrail, pinnedIds, "recent").map(
        (trail) => trail.id,
      ),
    ).toEqual(["t1", "t2", "t3"]);
    expect(
      sortTrailsForDashboard(
        [t3, t2, t1],
        progressByTrail,
        pinnedIds,
        "created_asc",
      ).map((trail) => trail.id),
    ).toEqual(["t2", "t1", "t3"]);
    expect(
      sortTrailsForDashboard(
        [t3, t2, t1],
        progressByTrail,
        pinnedIds,
        "mastery_desc",
      ).map((trail) => trail.id),
    ).toEqual(["t2", "t1", "t3"]);
  });

  test("renders empty state when there are no trails", async () => {
    listTrailsMock.mockResolvedValueOnce({ trails: [] });
    const Home = await loadPage();
    render(<Home />);

    await waitFor(() => {
      expect(screen.getByTestId("dashboard-empty")).toBeInTheDocument();
    });
    expect(screen.getAllByText(/Create your first Trail/i).length).toBeGreaterThan(0);
  });

  test("renders the main dashboard cards and per-trail CTA by mastery", async () => {
    const t1 = trail("t1", { title: "Linear Algebra", created_at: "2026-02-01T00:00:00Z" });
    const t2 = trail("t2", { title: "Calculus", created_at: "2026-01-01T00:00:00Z" });
    listTrailsMock.mockResolvedValueOnce({ trails: [t1, t2] });
    getTrailMock.mockImplementation(async (_ws: string, id: string) => {
      if (id === "t1") return detail(t1, "learning");
      return detail(t2, "mastered");
    });
    getTrailNextMock.mockImplementation(async (_ws: string, id: string) => {
      if (id === "t1") {
        return nextConcept({
          concept_id: "backend-t1-c9",
          concept_title: "Backend Linear Algebra focus",
          reason: "Continue the server-picked concept.",
        });
      }
      return nextConcept({
        concept_id: null,
        concept_title: null,
        reason: "All concepts mastered — review or explore further.",
        all_mastered: true,
      });
    });

    const Home = await loadPage();
    render(<Home />);

    // Continue Learning section picks t1 (it has activity + in-progress beats mastered fallback)
    await waitFor(() =>
      expect(
        screen.getByRole("link", { name: "Continue Learning" }),
      ).toHaveAttribute("href", "/trails/t1?concept=backend-t1-c9"),
    );
    expect(screen.getByText("Backend Linear Algebra focus")).toBeInTheDocument();
    expect(
      screen.getByText("Continue the server-picked concept."),
    ).toBeInTheDocument();

    expect(screen.getByText("Your Trails")).toBeInTheDocument();
    expect(screen.getByLabelText("Sort Trails")).toBeInTheDocument();
    expect(screen.getByLabelText("Sort Trails")).toBeInTheDocument();
  });

  test("Continue Learning deep-links to the backend recommended concept", async () => {
    const t1 = trail("t1");
    listTrailsMock.mockResolvedValueOnce({ trails: [t1] });
    getTrailMock.mockResolvedValueOnce(detail(t1, "not_started"));
    getTrailNextMock.mockResolvedValueOnce(
      nextConcept({ concept_id: "backend-c42", concept_title: "Backend-picked concept" }),
    );

    const Home = await loadPage();
    render(<Home />);

    await waitFor(() => {
      const link = screen.getByRole("link", { name: "Continue Learning" });
      expect(link).toHaveAttribute("href", "/trails/t1?concept=backend-c42");
    });
  });

  test("all-mastered state shows the review path and browse fallback", async () => {
    const t1 = trail("t1");
    listTrailsMock.mockResolvedValueOnce({ trails: [t1] });
    getTrailMock.mockResolvedValueOnce(detail(t1, "mastered"));
    getTrailNextMock.mockResolvedValueOnce(
      nextConcept({
        concept_id: null,
        concept_title: null,
        reason: "All concepts mastered — well done.",
        all_mastered: true,
      }),
    );

    const Home = await loadPage();
    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText("All concepts mastered")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Review Trail" })).toHaveAttribute(
        "href",
        "/trails/t1",
      );
      expect(screen.getByText("You're all caught up")).toBeInTheDocument();
    });
  });
});
