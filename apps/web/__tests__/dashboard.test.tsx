import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import type { Trail, TrailDetail } from "@/lib/types";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/workspace", () => ({
  ensureWorkspaceId: vi.fn().mockResolvedValue("workspace-1"),
}));

const listTrailsMock = vi.fn();
const getTrailMock = vi.fn();

vi.mock("@/lib/api", () => ({
  listTrails: (...args: unknown[]) => listTrailsMock(...args),
  getTrail: (...args: unknown[]) => getTrailMock(...args),
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

async function loadPage() {
  const mod = await import("@/app/page");
  return mod.default;
}

describe("Dashboard (home)", () => {
  test("renders empty state when there are no trails", async () => {
    listTrailsMock.mockResolvedValueOnce({ trails: [] });
    const Home = await loadPage();
    render(<Home />);

    await waitFor(() => {
      expect(screen.getByTestId("dashboard-empty")).toBeInTheDocument();
    });
    expect(screen.getAllByText(/Create your first Trail/i).length).toBeGreaterThan(0);
  });

  test("renders Continue Learning + Recent + per-trail CTA by mastery", async () => {
    const t1 = trail("t1", { title: "Linear Algebra", created_at: "2026-02-01T00:00:00Z" });
    const t2 = trail("t2", { title: "Calculus", created_at: "2026-01-01T00:00:00Z" });
    listTrailsMock.mockResolvedValueOnce({ trails: [t1, t2] });
    getTrailMock.mockImplementation(async (_ws: string, id: string) => {
      if (id === "t1") return detail(t1, "learning");
      return detail(t2, "mastered");
    });

    const Home = await loadPage();
    render(<Home />);

    // Continue Learning section picks t1 (it has activity + in-progress beats mastered fallback)
    await waitFor(() => {
      expect(screen.getByTestId("continue-learning")).toBeInTheDocument();
    });
    const continueSection = screen.getByTestId("continue-learning");
    expect(continueSection).toHaveTextContent("Linear Algebra");

    // Primary CTA in continue card reflects "learning" -> "Continue Tutor"
    await waitFor(() => {
      expect(continueSection.querySelector("a")?.textContent).toMatch(/Continue Tutor/);
    });

    // Recent Trails show both, with mastery-aware per-card CTAs
    expect(screen.getByText("Recent Trails")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Practice / Explore Further")).toBeInTheDocument();
    });
  });

  test("Continue Learning deep-links to ?concept=<recommended>", async () => {
    const t1 = trail("t1");
    listTrailsMock.mockResolvedValueOnce({ trails: [t1] });
    getTrailMock.mockResolvedValueOnce(detail(t1, "not_started"));

    const Home = await loadPage();
    render(<Home />);

    await waitFor(() => {
      const link = screen
        .getByTestId("continue-learning")
        .querySelector('a[href*="?concept="]') as HTMLAnchorElement | null;
      expect(link).not.toBeNull();
      expect(link!.getAttribute("href")).toBe("/trails/t1?concept=t1-c1");
      expect(link!.textContent).toMatch(/Start Learning/);
    });
  });
});
