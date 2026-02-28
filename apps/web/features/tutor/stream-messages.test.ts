import { describe, expect, it } from "vitest";

import type { TimelineMessage } from "./types";
import {
  appendStreamingAssistantDelta,
  removeStreamingAssistant,
  setStreamingReasoningSummary,
  setStreamingAnswerParts,
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

  // U5: reasoning summary tests
  it("setStreamingReasoningSummary attaches summary to existing message", () => {
    const messages: TimelineMessage[] = [
      { id: "a-1", role: "assistant", text: "Streaming..." },
    ];

    const next = setStreamingReasoningSummary(messages, "a-1", "Reasoned for 512 tokens");
    expect(next[0].reasoningSummary).toBe("Reasoned for 512 tokens");
    expect(next[0].text).toBe("Streaming...");
  });

  it("setStreamingReasoningSummary is no-op for missing id", () => {
    const messages: TimelineMessage[] = [
      { id: "a-1", role: "assistant", text: "Text" },
    ];

    const next = setStreamingReasoningSummary(messages, "nonexistent", "summary");
    expect(next).toBe(messages);
  });

  // U7: answer parts tests
  it("setStreamingAnswerParts updates message body and stores parts", () => {
    const messages: TimelineMessage[] = [
      { id: "a-1", role: "assistant", text: "Full raw text with hint" },
    ];

    const next = setStreamingAnswerParts(messages, "a-1", { body: "Just the body", hint: "The hint" });
    expect(next[0].text).toBe("Just the body");
    expect(next[0].answerParts).toEqual({ body: "Just the body", hint: "The hint" });
  });

  it("setStreamingAnswerParts is no-op for missing id", () => {
    const messages: TimelineMessage[] = [
      { id: "a-1", role: "assistant", text: "Text" },
    ];

    const next = setStreamingAnswerParts(messages, "nonexistent", { body: "Body", hint: null });
    expect(next).toBe(messages);
  });

  // U5: reasoning summary is only on streaming messages, not persisted
  it("removeStreamingAssistant drops reasoningSummary with the message", () => {
    const messages: TimelineMessage[] = [
      { id: "a-1", role: "assistant", text: "Streaming...", reasoningSummary: "Reasoned for 256 tokens" },
    ];

    const next = removeStreamingAssistant(messages, "a-1");
    expect(next).toEqual([]);
  });
});
