import { ApiClient, ApiError, DEFAULT_API_BASE_URL, consumeSseFrames, parseSseFrame } from "./client";
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
    await expect(new ApiClient({ fetchImpl }).respondChat("ws-uuid", { query: "x" })).rejects.toMatchObject({
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
    await new ApiClient({ baseUrl: "/api/", fetchImpl }).getConceptSubgraph("ws-uuid", 2, { max_hops: 1, max_nodes: 40, max_edges: 80 });
    expect(calledUrl).toBe("/api/workspaces/ws-uuid/graph/concepts/2/subgraph?max_hops=1&max_nodes=40&max_edges=80");
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
    await new ApiClient({ baseUrl: "/api/", fetchImpl }).listChatSessions("ws-uuid", {
      limit: 20,
    });
    expect(calledUrl).toBe("/api/workspaces/ws-uuid/chat/sessions?limit=20");
  });

  it("builds chat delete query strings", async () => {
    let calledUrl = "";
    let calledMethod = "";
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      calledUrl = String(input);
      calledMethod = String(init?.method);
      return new Response(null, { status: 204 });
    });
    await new ApiClient({ baseUrl: "/api/", fetchImpl }).deleteChatSession("ws-uuid", "abc-def-123");
    expect(calledUrl).toBe("/api/workspaces/ws-uuid/chat/sessions/abc-def-123");
    expect(calledMethod).toBe("DELETE");
  });

  it("consumes complete SSE frames while keeping partial remainder", () => {
    const consumed = consumeSseFrames(
      'event: status\ndata: {"event":"status","phase":"thinking"}\n\n' +
      'event: delta\ndata: {"event":"delta","text":"Hel',
    );

    expect(consumed.frames).toEqual([
      'event: status\ndata: {"event":"status","phase":"thinking"}',
    ]);
    expect(consumed.remainder).toBe(
      'event: delta\ndata: {"event":"delta","text":"Hel',
    );
  });

  it("parses SSE data payloads into chat events", () => {
    const parsed = parseSseFrame<{ event: string; text: string }>(
      'event: delta\ndata: {"event":"delta","text":"Hello"}',
    );

    expect(parsed).toEqual({ event: "delta", text: "Hello" });
  });

  it("streams chat events across chunk boundaries", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('event: status\ndata: {"event":"status","phase":"searching"}\n'));
        controller.enqueue(encoder.encode("\n"));
        controller.enqueue(encoder.encode('event: delta\ndata: {"event":"delta","text":"Hello"}\n\n'));
        controller.close();
      },
    });

    const fetchImpl = vi.fn(async () =>
      new Response(stream, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      }),
    );
    const events: Array<{ event: string; phase?: string | null; text?: string }> = [];

    new ApiClient({ baseUrl: "/api", fetchImpl }).respondChatStream(
      "ws-uuid",
      { query: "hello" },
      (event) => {
        events.push(event);
      },
    );

    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(events).toEqual([
      { event: "status", phase: "searching" },
      { event: "delta", text: "Hello" },
    ]);
  });
});
