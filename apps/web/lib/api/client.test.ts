import { ApiClient, ApiError, DEFAULT_API_BASE_URL } from "./client";
import { describe, expect, it, vi } from "vitest";

describe("ApiClient", () => {
  it("uses /api by default", async () => {
    const fetchImpl = vi.fn(async (_input: RequestInfo | URL) =>
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    );
    await new ApiClient({ fetchImpl }).healthz();
    expect(DEFAULT_API_BASE_URL).toBe("/api");
    expect(fetchImpl).toHaveBeenCalledWith("/api/healthz", expect.objectContaining({ method: "GET" }));
  });

  it("throws ApiError with detail", async () => {
    const fetchImpl = vi.fn(async (_input: RequestInfo | URL) =>
      new Response(JSON.stringify({ detail: "invalid payload" }), { status: 422 }),
    );
    await expect(new ApiClient({ fetchImpl }).respondChat({ workspace_id: 1, query: "x" })).rejects.toMatchObject({
      status: 422,
      detail: "invalid payload",
      message: "invalid payload",
    } satisfies Partial<ApiError>);
  });

  it("builds graph query strings", async () => {
    let calledUrl = "";
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      calledUrl = String(input);
      return new Response(
        JSON.stringify({ workspace_id: 1, root_concept_id: 2, max_hops: 1, nodes: [], edges: [] }),
        { status: 200 },
      );
    });
    await new ApiClient({ baseUrl: "/api/", fetchImpl }).getConceptSubgraph({ workspace_id: 1, concept_id: 2, max_hops: 1, max_nodes: 40, max_edges: 80 });
    expect(calledUrl).toBe("/api/graph/concepts/2/subgraph?workspace_id=1&max_hops=1&max_nodes=40&max_edges=80");
  });

  it("builds chat session query strings", async () => {
    let calledUrl = "";
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      calledUrl = String(input);
      return new Response(
        JSON.stringify({ workspace_id: 1, user_id: 2, sessions: [] }),
        { status: 200 },
      );
    });
    await new ApiClient({ baseUrl: "/api/", fetchImpl }).listChatSessions({
      workspace_id: 1,
      user_id: 2,
      limit: 20,
    });
    expect(calledUrl).toBe("/api/chat/sessions?workspace_id=1&user_id=2&limit=20");
  });

  it("builds chat delete query strings", async () => {
    let calledUrl = "";
    let calledMethod = "";
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      calledUrl = String(input);
      calledMethod = String(init?.method);
      return new Response(null, { status: 204 });
    });
    await new ApiClient({ baseUrl: "/api/", fetchImpl }).deleteChatSession({
      workspace_id: 1,
      user_id: 2,
      session_id: 7,
    });
    expect(calledUrl).toBe("/api/chat/sessions/7?workspace_id=1&user_id=2");
    expect(calledMethod).toBe("DELETE");
  });
});
