import type { AssistantResponseEnvelope, ChatMessageRecord } from "@/lib/api/types";
import { ApiError } from "@/lib/api/client";

export type TimelineMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  text: string;
  response?: AssistantResponseEnvelope;
};

/** Lifecycle phases for the chat request indicator (E2). */
export type ChatPhase = "idle" | "thinking" | "searching" | "responding";

export const PHASE_LABELS: Record<ChatPhase, string> = {
  idle: "",
  thinking: "Thinking…",
  searching: "Searching knowledge base…",
  responding: "Generating response…",
};

export function errorText(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return fallback;
}

export function mapMessage(record: ChatMessageRecord): TimelineMessage {
  const payload = record.payload;
  if (record.type === "assistant" && payload && typeof payload === "object") {
    const candidate = payload as Partial<AssistantResponseEnvelope>;
    if (candidate.kind && candidate.text) {
      return {
        id: String(record.message_id),
        role: "assistant",
        text: String(candidate.text),
        response: candidate as AssistantResponseEnvelope,
      };
    }
  }
  const text = typeof payload.text === "string" ? payload.text : JSON.stringify(payload);
  if (record.type === "assistant") return { id: String(record.message_id), role: "assistant", text };
  if (record.type === "user") return { id: String(record.message_id), role: "user", text };
  return { id: String(record.message_id), role: "system", text };
}

export function masteryLabel(status: string | null, score: number | null): string {
  if (!status) return "unseen";
  if (typeof score === "number") return `${status} (${Math.round(score * 100)}%)`;
  return status;
}
