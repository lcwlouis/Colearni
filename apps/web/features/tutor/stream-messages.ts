import type { AnswerParts } from "@/lib/api/types";
import type { TimelineMessage } from "./types";

export function appendStreamingAssistantDelta(
  messages: TimelineMessage[],
  assistantId: string,
  delta: string,
): TimelineMessage[] {
  if (!delta) return messages;

  const index = messages.findIndex((message) => message.id === assistantId);
  if (index === -1) {
    return [
      ...messages,
      {
        id: assistantId,
        role: "assistant",
        text: delta,
      },
    ];
  }

  const next = [...messages];
  const existing = next[index];
  next[index] = {
    ...existing,
    role: "assistant",
    text: `${existing.text}${delta}`,
    response: undefined,
  };
  return next;
}

/** Attach an ephemeral reasoning summary to the streaming assistant message. */
export function setStreamingReasoningSummary(
  messages: TimelineMessage[],
  assistantId: string,
  summary: string,
): TimelineMessage[] {
  const index = messages.findIndex((message) => message.id === assistantId);
  if (index === -1) return messages;

  const next = [...messages];
  next[index] = { ...next[index], reasoningSummary: summary };
  return next;
}

/** Update structured answer parts on the streaming assistant message. */
export function setStreamingAnswerParts(
  messages: TimelineMessage[],
  assistantId: string,
  parts: AnswerParts,
): TimelineMessage[] {
  const index = messages.findIndex((message) => message.id === assistantId);
  if (index === -1) return messages;

  // Store body as text and full parts as answerParts so the streaming
  // UI can render the hint area identically to the final ChatResponse (U7).
  const next = [...messages];
  next[index] = { ...next[index], text: parts.body, answerParts: parts };
  return next;
}

export function removeStreamingAssistant(
  messages: TimelineMessage[],
  assistantId: string,
): TimelineMessage[] {
  return messages.filter((message) => message.id !== assistantId);
}
