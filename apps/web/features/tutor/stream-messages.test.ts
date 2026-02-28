import { describe, expect, it } from "vitest";

import type { TimelineMessage } from "./types";
import {
  appendStreamingAssistantDelta,
  removeStreamingAssistant,
} from "./stream-messages";

describe("stream-messages", () => {
  it("creates a new assistant message for the first delta", () => {
    const messages: TimelineMessage[] = [
      { id: "user-1", role: "user", text: "Explain tensors" },
    ];

    const next = appendStreamingAssistantDelta(messages, "assistant-1", "Tensors");

    expect(next).toEqual([
      { id: "user-1", role: "user", text: "Explain tensors" },
      { id: "assistant-1", role: "assistant", text: "Tensors" },
    ]);
  });

  it("appends subsequent deltas to the same assistant message", () => {
    const messages: TimelineMessage[] = [
      { id: "user-1", role: "user", text: "Explain tensors" },
      { id: "assistant-1", role: "assistant", text: "Ten" },
    ];

    const next = appendStreamingAssistantDelta(messages, "assistant-1", "sors");

    expect(next[1]).toEqual({
      id: "assistant-1",
      role: "assistant",
      text: "Tensors",
      response: undefined,
    });
  });

  it("removes the temporary assistant message", () => {
    const messages: TimelineMessage[] = [
      { id: "user-1", role: "user", text: "Explain tensors" },
      { id: "assistant-1", role: "assistant", text: "Partial" },
    ];

    expect(removeStreamingAssistant(messages, "assistant-1")).toEqual([
      { id: "user-1", role: "user", text: "Explain tensors" },
    ]);
  });

  // F3: edge case tests
  it("ignores empty delta strings", () => {
    const messages: TimelineMessage[] = [
      { id: "user-1", role: "user", text: "Hello" },
      { id: "assistant-1", role: "assistant", text: "Hi" },
    ];

    const next = appendStreamingAssistantDelta(messages, "assistant-1", "");
    expect(next).toBe(messages); // same reference, no mutation
  });

  it("handles multiple sequential deltas correctly", () => {
    let messages: TimelineMessage[] = [
      { id: "user-1", role: "user", text: "Explain" },
    ];

    messages = appendStreamingAssistantDelta(messages, "a-1", "Hello");
    messages = appendStreamingAssistantDelta(messages, "a-1", " ");
    messages = appendStreamingAssistantDelta(messages, "a-1", "world");
    messages = appendStreamingAssistantDelta(messages, "a-1", "!");

    expect(messages[1]).toEqual({
      id: "a-1",
      role: "assistant",
      text: "Hello world!",
      response: undefined,
    });
  });

  it("removeStreamingAssistant is a no-op when id does not exist", () => {
    const messages: TimelineMessage[] = [
      { id: "user-1", role: "user", text: "Hello" },
    ];

    const next = removeStreamingAssistant(messages, "nonexistent");
    expect(next).toHaveLength(1);
    expect(next[0].id).toBe("user-1");
  });

  it("does not affect other messages when removing streaming assistant", () => {
    const messages: TimelineMessage[] = [
      { id: "user-1", role: "user", text: "Hello" },
      { id: "tmp-a-1", role: "assistant", text: "Partial stream" },
      { id: "user-2", role: "user", text: "Another" },
    ];

    const next = removeStreamingAssistant(messages, "tmp-a-1");
    expect(next).toEqual([
      { id: "user-1", role: "user", text: "Hello" },
      { id: "user-2", role: "user", text: "Another" },
    ]);
  });
});
