import { afterEach, describe, expect, test, vi } from "vitest";

import { generateTrail, listTrails } from "@/lib/api";
import type { Trail } from "@/lib/types";

describe("api client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("listTrails calls the workspace-scoped endpoint", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ trails: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await listTrails("workspace-1");

    expect(result.trails).toEqual([]);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/workspaces/workspace-1/trails",
      expect.objectContaining({ method: "GET" }),
    );
  });

  test("generateTrail reports backend stream progress", async () => {
    const encoder = new TextEncoder();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        new ReadableStream({
          start(controller) {
            controller.enqueue(
              encoder.encode(
                'event: progress\ndata: {"message":"Generating graph for Math..."}\n\n',
              ),
            );
            controller.enqueue(
              encoder.encode(
                `event: done\ndata: ${JSON.stringify({
                  trail: fixtureTrail,
                  graph: { nodes: [], edges: [] },
                })}\n\n`,
              ),
            );
            controller.close();
          },
        }),
        {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        },
      ),
    );
    const progress: string[] = [];

    const result = await generateTrail(
      "workspace-1",
      {
        topic: "Math",
        goal: "Learn",
        target_depth: "apply",
        max_nodes: 40,
      },
      (message) => progress.push(message),
    );

    expect(progress).toContain("Generating graph for Math...");
    expect(result.trail.id).toBe("trail-1");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/workspaces/workspace-1/trails/generate/stream",
      expect.objectContaining({ method: "POST" }),
    );
  });
});

const fixtureTrail: Trail = {
  id: "trail-1",
  workspace_id: "workspace-1",
  title: "Math",
  topic: "Math",
  goal: "Learn",
  target_depth: "apply",
  created_at: "2026-01-01T00:00:00Z",
  node_count: 0,
  edge_count: 0,
};
