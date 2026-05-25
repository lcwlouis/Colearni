import { afterEach, describe, expect, test, vi } from "vitest";

import { generateTrail, linkSourceToConcept, listTrails, streamTutorChat, uploadSource } from "@/lib/api";
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
                  graph: { nodes: [], edges: [], mastery: {} },
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

  test("streamTutorChat forwards tool call and result events", async () => {
    const encoder = new TextEncoder();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        new ReadableStream({
          start(controller) {
            controller.enqueue(
              encoder.encode(
                'data: {"type":"tool_call","name":"get_tutor_instructions","mode":"direct"}\n\n',
              ),
            );
            controller.enqueue(
              encoder.encode(
                'data: {"type":"tool_result","name":"get_tutor_instructions","mode":"direct","result":"Use direct mode."}\n\n',
              ),
            );
            controller.enqueue(
              encoder.encode(
                'data: {"type":"done","conversation_id":"conversation-1","message":{"id":"message-1","role":"assistant","content":"Hi","reasoning":null,"mode":"direct","created_at":"2026-01-01T00:00:00Z"}}\n\n',
              ),
            );
            controller.close();
          },
        }),
        { status: 200 },
      ),
    );
    const calls: unknown[] = [];
    const results: unknown[] = [];

    await streamTutorChat({
      workspaceId: "workspace-1",
      trailId: "trail-1",
      conceptId: "concept-1",
      message: "Explain directly.",
      conversationId: null,
      onMode: vi.fn(),
      onToolCall: (tool) => calls.push(tool),
      onToolResult: (tool) => results.push(tool),
      onToken: vi.fn(),
      onDone: vi.fn(),
    });

    expect(calls).toEqual([{ name: "get_tutor_instructions", mode: "direct" }]);
    expect(results).toEqual([
      { name: "get_tutor_instructions", mode: "direct", result: "Use direct mode." },
    ]);
  });

  test("streamTutorChat forwards status events", async () => {
    const encoder = new TextEncoder();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        new ReadableStream({
          start(controller) {
            controller.enqueue(encoder.encode('data: {"type":"status","status":"thinking"}\n\n'));
            controller.enqueue(encoder.encode('data: {"type":"status","status":"calling_tool"}\n\n'));
            controller.enqueue(
              encoder.encode(
                'data: {"type":"done","conversation_id":"conversation-1","message":{"id":"message-1","role":"assistant","content":"Hi","reasoning":null,"mode":"socratic","created_at":"2026-01-01T00:00:00Z"}}\n\n',
              ),
            );
            controller.close();
          },
        }),
        { status: 200 },
      ),
    );
    const statuses: string[] = [];

    await streamTutorChat({
      workspaceId: "workspace-1",
      trailId: "trail-1",
      conceptId: "concept-1",
      message: "Explain directly.",
      conversationId: null,
      onMode: vi.fn(),
      onStatus: (status) => statuses.push(status),
      onToken: vi.fn(),
      onDone: vi.fn(),
    });

    expect(statuses).toEqual(["thinking", "calling_tool"]);
  });

  test("streamTutorChat calls onMasteryUpdated when done event includes mastery_update", async () => {
    const encoder = new TextEncoder();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        new ReadableStream({
          start(controller) {
            controller.enqueue(
              encoder.encode(
                'data: {"type":"done","conversation_id":"conversation-1","message":{"id":"message-1","role":"assistant","content":"Hi","reasoning":null,"mode":"socratic","created_at":"2026-01-01T00:00:00Z"},"mastery_update":{"concept_id":"concept-1","status":"learning","score":0.0}}\n\n',
              ),
            );
            controller.close();
          },
        }),
        { status: 200 },
      ),
    );

    const onMasteryUpdated = vi.fn();

    await streamTutorChat({
      workspaceId: "workspace-1",
      trailId: "trail-1",
      conceptId: "concept-1",
      message: "Help me.",
      conversationId: null,
      onMode: vi.fn(),
      onToken: vi.fn(),
      onDone: vi.fn(),
      onMasteryUpdated,
    });

    expect(onMasteryUpdated).toHaveBeenCalledWith("concept-1", { status: "learning", score: 0.0 });
  });

  test("streamTutorChat does not call onMasteryUpdated when done event lacks mastery_update", async () => {
    const encoder = new TextEncoder();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        new ReadableStream({
          start(controller) {
            controller.enqueue(
              encoder.encode(
                'data: {"type":"done","conversation_id":"conversation-1","message":{"id":"message-1","role":"assistant","content":"Hi","reasoning":null,"mode":"socratic","created_at":"2026-01-01T00:00:00Z"}}\n\n',
              ),
            );
            controller.close();
          },
        }),
        { status: 200 },
      ),
    );

    const onMasteryUpdated = vi.fn();

    await streamTutorChat({
      workspaceId: "workspace-1",
      trailId: "trail-1",
      conceptId: "concept-1",
      message: "Help me.",
      conversationId: null,
      onMode: vi.fn(),
      onToken: vi.fn(),
      onDone: vi.fn(),
      onMasteryUpdated,
    });

    expect(onMasteryUpdated).not.toHaveBeenCalled();
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

  test("uploadSource posts multipart form data without JSON content type", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "source-1",
          workspace_id: "workspace-1",
          title: "Notes",
          url: null,
          origin: "user_upload",
          access: "private",
          license: null,
          include_on_public_export: false,
          metadata_json: {},
          revision: {
            id: "revision-1",
            workspace_id: "workspace-1",
            source_id: "source-1",
            revision_number: 1,
            content_type: "text/plain",
            file_size_bytes: 5,
            parser_name: "none",
            parser_version: "upload-only-v1",
            status: "pending_parse",
            error_message: null,
            metadata_json: {},
            created_at: "2026-01-01T00:00:00Z",
          },
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );
    const file = new File(["notes"], "notes.txt", { type: "text/plain" });

    const response = await uploadSource("workspace-1", file, "Notes");

    expect(response.id).toBe("source-1");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/workspaces/workspace-1/sources/upload",
      expect.objectContaining({ method: "POST", body: expect.any(FormData) }),
    );
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.headers).toBeInstanceOf(Headers);
    expect((init.headers as Headers).has("Content-Type")).toBe(false);
  });

  test("linkSourceToConcept posts concept link payload", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "link-1",
          source_id: "source-1",
          concept_id: "concept-1",
          relation: "primary",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );

    await linkSourceToConcept("workspace-1", "source-1", "concept-1", "primary");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/workspaces/workspace-1/sources/source-1/links",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ concept_id: "concept-1", relation: "primary" }),
      }),
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
