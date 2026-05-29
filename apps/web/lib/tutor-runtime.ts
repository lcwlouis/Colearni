import { useCallback, useMemo, useRef } from "react";
import {
  useLocalRuntime,
  type ChatModelAdapter,
  type ChatModelRunResult,
  type ThreadAssistantMessagePart,
  type ThreadMessageLike,
} from "@assistant-ui/react";

import { streamTutorChat } from "@/lib/api";
import type {
  ConversationHistoryResponse,
  ConversationReasoningPart,
  MasteryStatus,
  TutorToolEvent,
  TutorMode,
  TutorStreamStatus,
} from "@/lib/types";

type TutorRuntimePart =
  | { kind: "status"; status: TutorStreamStatus }
  | { kind: "thinking"; text: string }
  | { kind: "tool_call"; tool: TutorToolEvent }
  | { kind: "tool_result"; tool: TutorToolEvent };

interface TutorRuntimeOptions {
  workspaceId: string;
  trailId: string;
  conceptId: string;
  conversationId: string | null;
  history?: ConversationHistoryResponse | null;
  onConversationId: (conversationId: string) => void;
  onMode: (mode: TutorMode) => void;
  onStatus?: (status: TutorStreamStatus) => void;
  onError?: (message: string) => void;
  onMasteryUpdated?: (conceptId: string, update: { status: MasteryStatus; score: number }) => void;
}

interface CreateTutorModelAdapterOptions
  extends Omit<TutorRuntimeOptions, "history"> {
  getConversationId?: () => string | null;
}

export function useTutorRuntime({
  workspaceId,
  trailId,
  conceptId,
  conversationId,
  history,
  onConversationId,
  onMode,
  onStatus,
  onError,
  onMasteryUpdated,
}: TutorRuntimeOptions) {
  const conversationIdRef = useRef(conversationId);
  conversationIdRef.current = conversationId;

  const getConversationId = useCallback(() => conversationIdRef.current, []);

  const adapter = useMemo(
    () =>
      createTutorModelAdapter({
        workspaceId,
        trailId,
        conceptId,
        conversationId,
        getConversationId,
        onConversationId,
        onMode,
        onStatus,
        onError,
        onMasteryUpdated,
      }),
    [
      workspaceId,
      trailId,
      conceptId,
      conversationId,
      getConversationId,
      onConversationId,
      onMode,
      onStatus,
      onError,
      onMasteryUpdated,
    ],
  );

  return useLocalRuntime(adapter, {
    // assistant-ui LocalRuntime owns live chat state. We hydrate persisted turns here.
    initialMessages: history ? toThreadMessages(history) : [],
  });
}

export function createTutorModelAdapter({
  workspaceId,
  trailId,
  conceptId,
  conversationId,
  getConversationId,
  onConversationId,
  onMode,
  onStatus,
  onError,
  onMasteryUpdated,
}: CreateTutorModelAdapterOptions): ChatModelAdapter {
  return {
    async *run({ messages, abortSignal, runConfig }) {
      const latest = latestUserMessageText(messages);
      if (!latest) {
        return;
      }
      const regenerate = runConfig.custom?.regenerate === true;
      const replaceLatestUser = runConfig.custom?.replaceLatestUser === true;

      let text = "";
      const parts: TutorRuntimePart[] = [];
      const queue = createRunQueue();

      // LocalRuntime expects yielded message snapshots, while our backend streams callback-style SSE.
      void streamTutorChat({
        workspaceId,
        trailId,
        conceptId,
        message: latest,
        conversationId: getConversationId?.() ?? conversationId,
        regenerate,
        replaceLatestUser,
        signal: abortSignal,
        onMode,
        onStatus(nextStatus) {
          onStatus?.(nextStatus);
          parts.push({ kind: "status", status: nextStatus });
          queue.push(assistantRunUpdate(text, parts));
        },
        onMasteryUpdated,
        onThinking(content) {
          const last = parts[parts.length - 1];
          if (last?.kind === "thinking") {
            last.text += content;
          } else {
            parts.push({ kind: "thinking", text: content });
          }
          queue.push(assistantRunUpdate(text, parts));
        },
        onToolCall(tool) {
          parts.push({ kind: "tool_call", tool });
          queue.push(assistantRunUpdate(text, parts));
        },
        onToolResult(tool) {
          parts.push({ kind: "tool_result", tool });
          queue.push(assistantRunUpdate(text, parts));
        },
        onToken(content) {
          text += content;
          queue.push(assistantRunUpdate(text, parts));
        },
        onDone(nextConversationId) {
          onConversationId(nextConversationId);
          queue.push(assistantRunResult(text, parts));
          queue.close();
        },
      })
        .then(() => queue.close())
        .catch((exc) => {
          const message = exc instanceof Error ? exc.message : "Tutor chat failed";
          onError?.(message);
          queue.close();
        });

      while (true) {
        const next = await queue.next();
        if (next.done) {
          break;
        }
        yield next.value;
      }
    },
  };
}

export function latestUserMessageText(messages: ChatModelAdapterRunMessages): string {
  const latest = [...messages].reverse().find((message) => message.role === "user");
  return latest ? messageText(latest.content).trim() : "";
}

export function toThreadMessages(history: ConversationHistoryResponse): ThreadMessageLike[] {
  return history.messages.map((message) => ({
    id: message.id,
    role: message.role,
    content: toThreadMessageContent(message),
    createdAt: new Date(message.created_at),
    status:
      message.role === "assistant"
        ? {
            type: "complete",
            reason: "stop",
          }
        : undefined,
    metadata: {
      custom: message.mode ? { mode: message.mode } : {},
    },
  }));
}

function toThreadMessageContent(message: ConversationHistoryResponse["messages"][number]) {
  if (message.role !== "assistant") {
    return message.content;
  }

  return assistantMessageContent(message.content, reasoningParts(message));
}

function assistantRunUpdate(
  text: string,
  parts: TutorRuntimePart[],
): ChatModelRunResult {
  return {
    content: assistantMessageContent(text, parts),
  };
}

function assistantRunResult(
  text: string,
  parts: TutorRuntimePart[],
): ChatModelRunResult {
  return {
    content: assistantMessageContent(text, parts),
    status: { type: "complete", reason: "stop" },
  };
}

function assistantMessageContent(
  text: string,
  parts: TutorRuntimePart[],
): ThreadAssistantMessagePart[] {
  const content: ThreadAssistantMessagePart[] = [];
  for (const part of parts) {
    if (part.kind === "status") {
      if (part.status !== "responding") {
        content.push({
          type: "data",
          name: "tutor-status",
          data: { status: part.status },
        });
      }
      continue;
    }
    if (part.kind === "thinking") {
      content.push({
        type: "data",
        name: "tutor-thinking",
        data: { text: part.text },
      });
      continue;
    }
    content.push({
      type: "data",
      name: `tutor-${part.kind.replace("_", "-")}`,
      data: part.tool,
    });
  }
  if (text || content.length === 0) {
    content.push({ type: "text", text });
  }
  return content;
}

function reasoningParts(message: ConversationHistoryResponse["messages"][number]): TutorRuntimePart[] {
  if (message.reasoning_parts?.length) {
    return message.reasoning_parts.flatMap(reasoningPartToRuntimePart);
  }
  return message.reasoning ? [{ kind: "thinking", text: message.reasoning }] : [];
}

function reasoningPartToRuntimePart(part: ConversationReasoningPart): TutorRuntimePart[] {
  if (part.kind === "status") {
    return part.status ? [{ kind: "status", status: part.status }] : [];
  }
  if (part.kind === "thinking") {
    return part.text ? [{ kind: "thinking", text: part.text }] : [];
  }
  const tool = {
    name: part.name ?? "tool",
    mode: part.mode ?? null,
    query: part.query ?? undefined,
    result: part.result ?? undefined,
  };
  return [{ kind: part.kind, tool }];
}

function createRunQueue() {
  const items: ChatModelRunResult[] = [];
  let closed = false;
  let failure: unknown;
  let pending:
    | {
        resolve: (value: IteratorResult<ChatModelRunResult>) => void;
        reject: (reason?: unknown) => void;
      }
    | null = null;

  return {
    push(item: ChatModelRunResult) {
      if (closed) {
        return;
      }
      if (pending) {
        const { resolve } = pending;
        pending = null;
        resolve({ value: item, done: false });
        return;
      }
      items.push(item);
    },
    close() {
      if (closed) {
        return;
      }
      closed = true;
      if (pending) {
        const { resolve } = pending;
        pending = null;
        resolve({ value: undefined, done: true });
      }
    },
    fail(reason: unknown) {
      if (closed) {
        return;
      }
      failure = reason;
      closed = true;
      if (pending) {
        const { reject } = pending;
        pending = null;
        reject(reason);
      }
    },
    async next(): Promise<IteratorResult<ChatModelRunResult>> {
      if (items.length > 0) {
        return { value: items.shift()!, done: false };
      }
      if (failure) {
        throw failure;
      }
      if (closed) {
        return { value: undefined, done: true };
      }
      return new Promise((resolve, reject) => {
        pending = { resolve, reject };
      });
    },
  };
}

type ChatModelAdapterRunMessages = Parameters<ChatModelAdapter["run"]>[0]["messages"];

function messageText(content: ChatModelAdapterRunMessages[number]["content"]): string {
  if (typeof content === "string") {
    return content;
  }
  return content
    .map((part) => {
      if (part.type === "text") {
        return part.text;
      }
      return "";
    })
    .join("");
}
