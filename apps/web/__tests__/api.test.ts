import { afterEach, describe, expect, test, vi } from "vitest";

import { generateTrail, listTrails, streamTutorChat } from "@/lib/api";
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

  test("streamTutorChat posts to concept chat endpoint with body and signal", async () => {
    const encoder = new TextEncoder();
    const signal = new AbortController().signal;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        new ReadableStream({
          start(controller) {
            controller.enqueue(
              encoder.encode(
                'data: {"type":"mode","mode":"socratic"}\n\ndata: {"type":"done","conversation_id":"conversation-1","message":{"id":"message-1","role":"assistant","content":"Hi","reasoning":null,"mode":"socratic","created_at":"2026-01-01T00:00:00Z"}}\n\n',
              ),
            );
            controller.close();
          },
        }),
        { status: 200, headers: { "Content-Type": "text/event-stream" } },
      ),
    );

    await streamTutorChat({
      workspaceId: "workspace-1",
      trailId: "trail-1",
      conceptId: "concept-1",
      message: "Help me understand this.",
      conversationId: "conversation-0",
      signal,
      onMode: vi.fn(),
      onToken: vi.fn(),
      onDone: vi.fn(),
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/workspaces/workspace-1/trails/trail-1/concepts/concept-1/chat",
      expect.objectContaining({
        method: "POST",
        signal,
        body: JSON.stringify({
          message: "Help me understand this.",
          conversation_id: "conversation-0",
        }),
      }),
    );
  });

  test("streamTutorChat handles mode, thinking, token chunks, and done events", async () => {
    const encoder = new TextEncoder();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        new ReadableStream({
          start(controller) {
            controller.enqueue(encoder.encode('data: {"type":"mode","mode":"direct"}\n\n'));
            controller.enqueue(encoder.encode('data: {"type":"thinking","content":"Let me think."}\n\n'));
            controller.enqueue(encoder.encode('data: {"type":"token","content":"Hello"}\n\n'));
            controller.enqueue(encoder.encode('data: {"type":"token","content":" there"}\n\n'));
            controller.enqueue(
              encoder.encode(
                'data: {"type":"done","conversation_id":"conversation-1","message":{"id":"message-1","role":"assistant","content":"Hello there","reasoning":"Let me think.","mode":"direct","created_at":"2026-01-01T00:00:00Z"}}\n\n',
              ),
            );
            controller.close();
          },
        }),
        { status: 200 },
      ),
    );
    const modes: string[] = [];
    const thinking: string[] = [];
    const tokens: string[] = [];
    const done = vi.fn();

    await streamTutorChat({
      workspaceId: "workspace-1",
      trailId: "trail-1",
      conceptId: "concept-1",
      message: "Explain directly.",
      conversationId: null,
      onMode: (mode) => modes.push(mode),
      onThinking: (chunk) => thinking.push(chunk),
      onToken: (token) => tokens.push(token),
      onDone: done,
    });

    expect(modes).toEqual(["direct"]);
    expect(thinking).toEqual(["Let me think."]);
    expect(tokens).toEqual(["Hello", " there"]);
    expect(done).toHaveBeenCalledWith(
      "conversation-1",
      expect.objectContaining({ content: "Hello there", reasoning: "Let me think.", mode: "direct" }),
    );
  });

  test("streamTutorChat throws readable errors for error events", async () => {
    const encoder = new TextEncoder();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        new ReadableStream({
          start(controller) {
            controller.enqueue(
              encoder.encode('data: {"type":"error","code":"llm_error","message":"Generation failed"}\n\n'),
            );
            controller.close();
          },
        }),
        { status: 200 },
      ),
    );

    await expect(
      streamTutorChat({
        workspaceId: "workspace-1",
        trailId: "trail-1",
        conceptId: "concept-1",
        message: "Hello",
        conversationId: null,
        onMode: vi.fn(),
        onToken: vi.fn(),
        onDone: vi.fn(),
      }),
    ).rejects.toThrow("Generation failed");
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
