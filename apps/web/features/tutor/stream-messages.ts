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

export function removeStreamingAssistant(
  messages: TimelineMessage[],
  assistantId: string,
): TimelineMessage[] {
  return messages.filter((message) => message.id !== assistantId);
}
