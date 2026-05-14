import { afterEach, describe, expect, test, vi } from "vitest";

import { listTrails } from "@/lib/api";

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
});
