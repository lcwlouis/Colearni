import type { AnswerParts, AssistantResponseEnvelope, ChatMessageRecord, TutorActivity } from "@/lib/api/types";
import { ApiError } from "@/lib/api/client";

export type TimelineMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  text: string;
  response?: AssistantResponseEnvelope;
  /** Ephemeral reasoning summary — only populated during live streaming turns. */
  reasoningSummary?: string;
  /** Structured answer parts — populated during live streaming turns (U7). */
  answerParts?: AnswerParts;
};

/** Lifecycle phases for the chat request indicator (E2). */
export type ChatPhase = "idle" | "thinking" | "searching" | "responding" | "finalizing";

/** A completed or in-progress activity step shown in the agent rail (AR3.3). */
export type ActivityStep = {
  activity: TutorActivity;
  label: string;
  done: boolean;
};

/**
 * User-facing labels for each TutorActivity (AR3.3).
 */
export const ACTIVITY_LABELS: Record<TutorActivity, string> = {
  planning_turn: "Analyzing question",
  retrieving_chunks: "Searching knowledge base",
  expanding_graph: "Finding related concepts",
  checking_mastery: "Checking mastery level",
  preparing_quiz: "Preparing quiz",
  grading_quiz: "Grading quiz",
  verifying_citations: "Verifying citations",
  generating_reply: "Generating response",
};

/**
 * User-facing phase labels (U1 visible phase policy).
 *
 * Only two distinct visible states:
 * - Pre-output work (thinking/searching/finalizing) → "Thinking…"
 * - Visible text arriving (responding) → "Generating response…"
 *
 * `searching` and `finalizing` remain valid internal/backend phases but are
 * collapsed under "Thinking…" at the UI boundary.
 */
export const PHASE_LABELS: Record<ChatPhase, string> = {
  idle: "",
  thinking: "Thinking…",
  searching: "Thinking…",
  responding: "Generating response…",
  finalizing: "Thinking…",
};

/**
 * Pure helper for visible phase label derivation (U1).
 * Extracted for direct unit testing of the visible phase policy.
 */
export function visiblePhaseLabel(phase: ChatPhase): string {
  return PHASE_LABELS[phase];
}

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
