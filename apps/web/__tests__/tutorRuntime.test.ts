import { describe, expect, test, vi } from "vitest";

import { createTutorModelAdapter, latestUserMessageText, toThreadMessages } from "@/lib/tutor-runtime";
import type { ConversationHistoryResponse, ConversationMessage } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  streamTutorChat: vi.fn(async ({ onMode, onThinking, onToken, onDone }) => {
    onMode("socratic");
    onThinking?.("First, inspect the relationship.\n");
    onToken("Think");
    onToken(" about it.");
    onDone("conversation-1", {
      id: "assistant-1",
      role: "assistant",
      content: "Think about it.",
      reasoning: "First, inspect the relationship.\n",
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
        signal: abortSignal,
      }),
    );
    expect(
      chunks.map((chunk) =>
        chunk.content?.map((part) => (part.type === "text" || part.type === "reasoning" ? `${part.type}:${part.text}` : part.type)),
      ),
    ).toEqual([
      ["reasoning:First, inspect the relationship.\n"],
      ["reasoning:First, inspect the relationship.\n", "text:Think"],
      ["reasoning:First, inspect the relationship.\n", "text:Think about it."],
      ["reasoning:First, inspect the relationship.\n", "text:Think about it."],
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
          mode: null,
          created_at: "2026-01-01T00:00:00Z",
        },
        {
          id: "assistant-1",
          role: "assistant",
          content: "Hi",
          reasoning: "Trace",
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
          { type: "reasoning", text: "Trace" },
          { type: "text", text: "Hi" },
        ],
        status: { type: "complete", reason: "stop" },
        metadata: { custom: { mode: "direct" } },
      }),
    ]);
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
