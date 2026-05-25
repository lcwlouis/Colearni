import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

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
    await waitFor(() => {
      expect(screen.getByTestId("continue-learning")).toBeInTheDocument();
    });
    const continueSection = screen.getByTestId("continue-learning");
    expect(continueSection).toHaveTextContent("Linear Algebra");

    expect(continueSection).toHaveTextContent("Backend Linear Algebra focus");
    expect(continueSection).toHaveTextContent("Continue the server-picked concept.");

    // Primary CTA uses the backend recommendation deep link.
    await waitFor(() => {
      expect(continueSection.querySelector("a")?.textContent).toMatch(/Start Learning/);
    });

    // Recent Trails show both, including the all-mastered backend state.
    expect(screen.getByText("Recent Trails")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("All mastered")).toBeInTheDocument();
    });
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
      const link = screen
        .getByTestId("continue-learning")
        .querySelector('a[href*="?concept="]') as HTMLAnchorElement | null;
      expect(link).not.toBeNull();
      expect(link!.getAttribute("href")).toBe("/trails/t1?concept=backend-c42");
      expect(link!.textContent).toMatch(/Start Learning/);
    });
  });

  test("Continue Learning all-mastered state shows achievement card with Create New Trail CTA", async () => {
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
      const section = screen.getByTestId("continue-learning");
      // Achievement state: correct heading and body copy
      expect(section).toHaveTextContent("All trails mastered");
      expect(section).toHaveTextContent("You have mastered every concept. Ready to go deeper?");
      // No deep-link to a concept
      expect(section.querySelector('a[href*="?concept="]')).toBeNull();
      // Primary CTA is "Create New Trail"
      expect(section.querySelector('a[href="/trails/new"]')).not.toBeNull();
      // View graph still links to the trail
      expect(section.querySelector('a[href="/trails/t1"]')).not.toBeNull();
    });
  });
});
