import { useCallback, useMemo, useRef } from "react";
import {
  useLocalRuntime,
  type ChatModelAdapter,
  type ChatModelRunResult,
  type ThreadAssistantMessagePart,
  type ThreadMessageLike,
} from "@assistant-ui/react";

import { streamTutorChat } from "@/lib/api";
import type { ConversationHistoryResponse, TutorMode } from "@/lib/types";

interface TutorRuntimeOptions {
  workspaceId: string;
  trailId: string;
  conceptId: string;
  conversationId: string | null;
  history?: ConversationHistoryResponse | null;
  onConversationId: (conversationId: string) => void;
  onMode: (mode: TutorMode) => void;
  onError?: (message: string) => void;
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
  onError,
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
        onError,
      }),
    [
      workspaceId,
      trailId,
      conceptId,
      conversationId,
      getConversationId,
      onConversationId,
      onMode,
      onError,
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
  onError,
}: CreateTutorModelAdapterOptions): ChatModelAdapter {
  return {
    async *run({ messages, abortSignal }) {
      const latest = latestUserMessageText(messages);
      if (!latest) {
        return;
      }

      let text = "";
      let reasoning = "";
      const queue = createRunQueue();

      // LocalRuntime expects yielded message snapshots, while our backend streams callback-style SSE.
      void streamTutorChat({
        workspaceId,
        trailId,
        conceptId,
        message: latest,
        conversationId: getConversationId?.() ?? conversationId,
        signal: abortSignal,
        onMode,
        onThinking(content) {
          reasoning += content;
          queue.push(assistantRunUpdate(text, reasoning));
        },
        onToken(content) {
          text += content;
          queue.push(assistantRunUpdate(text, reasoning));
        },
        onDone(nextConversationId) {
          onConversationId(nextConversationId);
          queue.push(assistantRunResult(text, reasoning));
          queue.close();
        },
      })
        .then(() => queue.close())
        .catch((exc) => {
          const message = exc instanceof Error ? exc.message : "Tutor chat failed";
          onError?.(message);
          queue.fail(exc);
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

  return assistantMessageContent(message.content, message.reasoning ?? "");
}

function assistantRunUpdate(text: string, reasoning: string): ChatModelRunResult {
  return {
    content: assistantMessageContent(text, reasoning),
  };
}

function assistantRunResult(text: string, reasoning: string): ChatModelRunResult {
  return {
    content: assistantMessageContent(text, reasoning),
    status: { type: "complete", reason: "stop" },
  };
}

function assistantMessageContent(text: string, reasoning: string): ThreadAssistantMessagePart[] {
  const content: ThreadAssistantMessagePart[] = [];
  if (reasoning) {
    content.push({ type: "reasoning", text: reasoning });
  }
  if (text || content.length === 0) {
    content.push({ type: "text", text });
  }
  return content;
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
