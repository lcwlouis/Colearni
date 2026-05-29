import { describe, expect, test, vi } from "vitest";

import { createTutorModelAdapter, latestUserMessageText, toThreadMessages } from "@/lib/tutor-runtime";
import type { ConversationHistoryResponse, ConversationMessage } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  streamTutorChat: vi.fn(async ({ onMode, onStatus, onThinking, onToolCall, onToolResult, onToken, onDone }) => {
    onMode("socratic");
    onStatus?.("thinking");
    onThinking?.("First, inspect the relationship.\n");
    onToolCall?.({ name: "get_tutor_instructions", mode: "direct" });
    onToolResult?.({ name: "get_tutor_instructions", mode: "direct", result: "Use direct mode." });
    onThinking?.("Now answer visibly.\n");
    onToken("Think");
    onToken(" about it.");
    onDone("conversation-1", {
      id: "assistant-1",
      role: "assistant",
      content: "Think about it.",
      reasoning: "First, inspect the relationship.\n",
      reasoning_parts: [],
      mode: "socratic",
      created_at: "2026-01-01T00:00:00Z",
    } satisfies ConversationMessage);
  }),
}));

describe("tutor runtime adapter", () => {
  test("sends only the latest learner message and streams accumulated tokens", async () => {
    const { streamTutorChat } = await import("@/lib/api");
    const onConversationId = vi.fn();
    const onMode = vi.fn();
    const adapter = createTutorModelAdapter({
      workspaceId: "workspace-1",
      trailId: "trail-1",
      conceptId: "concept-1",
      conversationId: "conversation-0",
      onConversationId,
      onMode,
    });
    const abortSignal = new AbortController().signal;
    const chunks = [];

    const stream = adapter.run({
      messages: [
        userMessage("First message"),
        assistantMessage("Earlier answer"),
        userMessage("Latest message"),
      ],
      runConfig: {},
      abortSignal,
      context: {},
      unstable_getMessage: () => assistantMessage(""),
    });

    if (!(Symbol.asyncIterator in stream)) {
      throw new Error("Expected streaming adapter result");
    }
    for await (const chunk of stream) {
      chunks.push(chunk);
    }

    expect(streamTutorChat).toHaveBeenCalledWith(
      expect.objectContaining({
        workspaceId: "workspace-1",
        trailId: "trail-1",
        conceptId: "concept-1",
        message: "Latest message",
        conversationId: "conversation-0",
        regenerate: false,
        signal: abortSignal,
      }),
    );
    expect(
      chunks.map((chunk) =>
        chunk.content?.map((part) => {
          if (part.type === "text" || part.type === "reasoning") {
            return `${part.type}:${part.text}`;
          }
          if (part.type === "data") {
            if (part.name === "tutor-status") {
              return `${part.type}:${(part.data as { status: string }).status}`;
            }
            if (part.name === "tutor-thinking") {
              return `${part.type}:thinking:${(part.data as { text: string }).text}`;
            }
            if (part.name === "tutor-tool-call") {
              return `${part.type}:tool_call:${(part.data as { name: string }).name}`;
            }
            if (part.name === "tutor-tool-result") {
              return `${part.type}:tool_result:${(part.data as { result: string }).result}`;
            }
          }
          return part.type;
        }),
      ),
    ).toEqual([
      ["data:thinking"],
      ["data:thinking", "data:thinking:First, inspect the relationship.\n"],
      [
        "data:thinking",
        "data:thinking:First, inspect the relationship.\n",
        "data:tool_call:get_tutor_instructions",
      ],
      [
        "data:thinking",
        "data:thinking:First, inspect the relationship.\n",
        "data:tool_call:get_tutor_instructions",
        "data:tool_result:Use direct mode.",
      ],
      [
        "data:thinking",
        "data:thinking:First, inspect the relationship.\n",
        "data:tool_call:get_tutor_instructions",
        "data:tool_result:Use direct mode.",
        "data:thinking:Now answer visibly.\n",
      ],
      [
        "data:thinking",
        "data:thinking:First, inspect the relationship.\n",
        "data:tool_call:get_tutor_instructions",
        "data:tool_result:Use direct mode.",
        "data:thinking:Now answer visibly.\n",
        "text:Think",
      ],
      [
        "data:thinking",
        "data:thinking:First, inspect the relationship.\n",
        "data:tool_call:get_tutor_instructions",
        "data:tool_result:Use direct mode.",
        "data:thinking:Now answer visibly.\n",
        "text:Think about it.",
      ],
      [
        "data:thinking",
        "data:thinking:First, inspect the relationship.\n",
        "data:tool_call:get_tutor_instructions",
        "data:tool_result:Use direct mode.",
        "data:thinking:Now answer visibly.\n",
        "text:Think about it.",
      ],
    ]);
    expect(onMode).toHaveBeenCalledWith("socratic");
    expect(onConversationId).toHaveBeenCalledWith("conversation-1");
  });

  test("latestUserMessageText extracts text from the newest user turn", () => {
    expect(
      latestUserMessageText([
        userMessage("Older"),
        assistantMessage("Answer"),
        userMessage("Newest"),
      ]),
    ).toBe("Newest");
  });

  test("toThreadMessages maps conversation history for assistant-ui hydration", () => {
    const history: ConversationHistoryResponse = {
      conversation_id: "conversation-1",
      messages: [
        {
          id: "user-1",
          role: "user",
          content: "Hello",
          reasoning: null,
          reasoning_parts: [],
          mode: null,
          created_at: "2026-01-01T00:00:00Z",
        },
        {
          id: "assistant-1",
          role: "assistant",
          content: "Hi",
          reasoning: "Trace",
          reasoning_parts: [
            { kind: "thinking", text: "Trace before tool." },
            { kind: "tool_call", name: "get_tutor_instructions", mode: "direct" },
            {
              kind: "tool_result",
              name: "get_tutor_instructions",
              mode: "direct",
              result: "Use direct mode.",
            },
            { kind: "thinking", text: "Trace after tool." },
          ],
          mode: "direct",
          created_at: "2026-01-01T00:00:01Z",
        },
      ],
    };

    expect(toThreadMessages(history)).toEqual([
      expect.objectContaining({ id: "user-1", role: "user", content: "Hello" }),
      expect.objectContaining({
        id: "assistant-1",
        role: "assistant",
        content: [
          { type: "data", name: "tutor-thinking", data: { text: "Trace before tool." } },
          {
            type: "data",
            name: "tutor-tool-call",
            data: { name: "get_tutor_instructions", mode: "direct", query: undefined, result: undefined },
          },
          {
            type: "data",
            name: "tutor-tool-result",
            data: { name: "get_tutor_instructions", mode: "direct", query: undefined, result: "Use direct mode." },
          },
          { type: "data", name: "tutor-thinking", data: { text: "Trace after tool." } },
          { type: "text", text: "Hi" },
        ],
        status: { type: "complete", reason: "stop" },
        metadata: { custom: { mode: "direct" } },
      }),
    ]);
  });

  test("marks explicit reload runs as backend regenerate requests", async () => {
    const { streamTutorChat } = await import("@/lib/api");
    vi.mocked(streamTutorChat).mockClear();
    const adapter = createTutorModelAdapter({
      workspaceId: "workspace-1",
      trailId: "trail-1",
      conceptId: "concept-1",
      conversationId: "conversation-0",
      onConversationId: vi.fn(),
      onMode: vi.fn(),
    });
    const stream = adapter.run({
      messages: [userMessage("Latest message")],
      runConfig: { custom: { regenerate: true } },
      abortSignal: new AbortController().signal,
      context: {},
      unstable_getMessage: () => assistantMessage(""),
    });

    if (!(Symbol.asyncIterator in stream)) {
      throw new Error("Expected streaming adapter result");
    }
    for await (const _chunk of stream) {
      // drain stream
    }

    expect(streamTutorChat).toHaveBeenCalledWith(
      expect.objectContaining({ regenerate: true }),
    );
  });

  test("marks latest user edit runs as backend latest-user replacement requests", async () => {
    const { streamTutorChat } = await import("@/lib/api");
    vi.mocked(streamTutorChat).mockClear();
    const adapter = createTutorModelAdapter({
      workspaceId: "workspace-1",
      trailId: "trail-1",
      conceptId: "concept-1",
      conversationId: "conversation-0",
      onConversationId: vi.fn(),
      onMode: vi.fn(),
    });
    const stream = adapter.run({
      messages: [userMessage("Edited latest message")],
      runConfig: { custom: { replaceLatestUser: true } },
      abortSignal: new AbortController().signal,
      context: {},
      unstable_getMessage: () => assistantMessage(""),
    });

    if (!(Symbol.asyncIterator in stream)) {
      throw new Error("Expected streaming adapter result");
    }
    for await (const _chunk of stream) {
      // drain stream
    }

    expect(streamTutorChat).toHaveBeenCalledWith(
      expect.objectContaining({ replaceLatestUser: true }),
    );
  });

  test("handled stream errors do not reject the adapter loop", async () => {
    const { streamTutorChat } = await import("@/lib/api");
    vi.mocked(streamTutorChat).mockImplementationOnce(async () => {
      throw new Error("Generation ended before a visible tutor response was produced");
    });

    const onError = vi.fn();
    const adapter = createTutorModelAdapter({
      workspaceId: "workspace-1",
      trailId: "trail-1",
      conceptId: "concept-1",
      conversationId: null,
      onConversationId: vi.fn(),
      onMode: vi.fn(),
      onError,
    });

    const stream = adapter.run({
      messages: [userMessage("Latest message")],
      runConfig: {},
      abortSignal: new AbortController().signal,
      context: {},
      unstable_getMessage: () => assistantMessage(""),
    });

    if (!(Symbol.asyncIterator in stream)) {
      throw new Error("Expected streaming adapter result");
    }

    const chunks = [];
    for await (const chunk of stream) {
      chunks.push(chunk);
    }

    expect(chunks).toEqual([]);
    expect(onError).toHaveBeenCalledWith("Generation ended before a visible tutor response was produced");
  });
});

function userMessage(text: string) {
  return {
    id: `user-${text}`,
    role: "user" as const,
    content: [{ type: "text" as const, text }],
    attachments: [],
    createdAt: new Date("2026-01-01T00:00:00Z"),
    metadata: { custom: {} },
  };
}

function assistantMessage(text: string) {
  return {
    id: `assistant-${text}`,
    role: "assistant" as const,
    content: [{ type: "text" as const, text }],
    status: { type: "complete" as const, reason: "stop" as const },
    createdAt: new Date("2026-01-01T00:00:00Z"),
    metadata: {
      unstable_state: null,
      unstable_annotations: [],
      unstable_data: [],
      steps: [],
      custom: {},
    },
  };
}
