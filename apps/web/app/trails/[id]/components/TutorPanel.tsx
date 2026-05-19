"use client";

import {
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useThread,
  type MessageState,
} from "@assistant-ui/react";

import { MarkdownText } from "@/components/assistant-ui/markdown-text";
import {
  ReasoningContent,
  ReasoningRoot,
  ReasoningText,
  ReasoningTrigger,
} from "@/components/assistant-ui/reasoning";
import { SourceChip } from "@/components/assistant-ui/sources";
import { getConversation } from "@/lib/api";
import { useTutorRuntime } from "@/lib/tutor-runtime";
import type {
  ConceptNode,
  ConversationHistoryResponse,
  SourceRecord,
  TutorMode,
} from "@/lib/types";

interface TutorPanelProps {
  workspaceId: string;
  trailId: string;
  concept: ConceptNode;
  sources?: SourceRecord[];
  onBack?: () => void;
}

export function TutorPanel({
  workspaceId,
  trailId,
  concept,
  sources = [],
  onBack,
}: TutorPanelProps) {
  const [history, setHistory] = useState<ConversationHistoryResponse | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [mode, setMode] = useState<TutorMode | null>(null);
  const [loading, setLoading] = useState(true);
  const [historyError, setHistoryError] = useState("");
  const [chatError, setChatError] = useState("");
  const [loadKey, setLoadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setHistoryError("");
    setChatError("");
    setHistory(null);
    setConversationId(null);
    setMode(null);

    async function loadHistory() {
      try {
        const nextHistory = await getConversation(workspaceId, trailId, concept.id);
        if (cancelled) {
          return;
        }
        setHistory(nextHistory);
        setConversationId(nextHistory.conversation_id);
        setMode(lastAssistantMode(nextHistory));
      } catch (exc) {
        if (!cancelled) {
          setHistoryError(exc instanceof Error ? exc.message : "Could not load conversation");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadHistory();
    return () => {
      cancelled = true;
    };
  }, [workspaceId, trailId, concept.id, loadKey]);

  if (loading) {
    return (
      <TutorShell concept={concept} sources={sources ?? []} mode={mode} onBack={onBack}>
        <div className="p-4 text-sm text-slate-500">Loading conversation...</div>
      </TutorShell>
    );
  }

  if (historyError || !history) {
    return (
      <TutorShell concept={concept} sources={sources ?? []} mode={mode} onBack={onBack}>
        <div className="m-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {historyError || "Conversation unavailable"}
        </div>
        <div className="px-4">
          <button
            type="button"
            onClick={() => setLoadKey((current) => current + 1)}
            className="rounded-md border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Retry
          </button>
        </div>
      </TutorShell>
    );
  }

  return (
    <TutorRuntimePanel
      key={concept.id}
      workspaceId={workspaceId}
      trailId={trailId}
      concept={concept}
      sources={sources}
      history={history}
      conversationId={conversationId}
      mode={mode}
      chatError={chatError}
      onBack={onBack}
      onConversationId={setConversationId}
      onMode={(nextMode) => {
        setMode(nextMode);
        setChatError("");
      }}
      onError={setChatError}
    />
  );
}

function TutorRuntimePanel({
  workspaceId,
  trailId,
  concept,
  sources,
  history,
  conversationId,
  mode,
  chatError,
  onBack,
  onConversationId,
  onMode,
  onError,
}: TutorPanelProps & {
  history: ConversationHistoryResponse;
  conversationId: string | null;
  mode: TutorMode | null;
  chatError: string;
  onConversationId: (conversationId: string) => void;
  onMode: (mode: TutorMode) => void;
  onError: (message: string) => void;
}) {
  const runtime = useTutorRuntime({
    workspaceId,
    trailId,
    conceptId: concept.id,
    conversationId,
    history,
    onConversationId,
    onMode,
    onError,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <TutorShell concept={concept} sources={sources ?? []} mode={mode} onBack={onBack}>
        {chatError ? (
          <div className="mx-4 mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {chatError}
          </div>
        ) : null}
        {mode === "quiz_prompt" ? (
          <div className="mx-4 mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
            Ready to level up? Quiz cards arrive in Phase 5.
          </div>
        ) : null}
        <TutorThread />
      </TutorShell>
    </AssistantRuntimeProvider>
  );
}

function TutorShell({
  concept,
  sources,
  mode,
  onBack,
  children,
}: {
  concept: ConceptNode;
  sources: SourceRecord[];
  mode: TutorMode | null;
  onBack?: () => void;
  children: ReactNode;
}) {
  return (
    <section className="flex min-h-[420px] flex-1 flex-col overflow-hidden rounded-md border border-slate-200 bg-white">
      <div className="border-b border-slate-200 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Tutor for this concept
            </p>
            <h3 className="mt-1 text-base font-semibold text-slate-950">{concept.title}</h3>
          </div>
          <ModeBadge mode={mode} />
        </div>
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          <ContextBadge>Level: {concept.concept_level}</ContextBadge>
          <ContextBadge>Bloom: {concept.bloom_level}</ContextBadge>
          <ContextBadge>Difficulty: {concept.difficulty}</ContextBadge>
        </div>
        {sources.length > 0 ? <SourceChips sources={sources} /> : null}
        {onBack ? (
          <button
            type="button"
            onClick={onBack}
            className="mt-3 text-xs font-medium text-slate-500 hover:text-slate-900"
          >
            Back to concept details
          </button>
        ) : null}
      </div>
      {children}
    </section>
  );
}

function TutorThread() {
  const messageCount = useThread((state) => state.messages.length);
  const isRunning = useThread((state) => state.isRunning);

  return (
    <ThreadPrimitive.Root className="flex min-h-0 flex-1 flex-col">
      <ThreadPrimitive.Viewport autoScroll className="min-h-0 flex-1 overflow-y-auto p-4">
        {messageCount === 0 ? (
          <div className="rounded-md border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-500">
            Ask the tutor to help you reason through this concept.
          </div>
        ) : null}
        <div className="grid gap-3">
          <ThreadPrimitive.Messages>
            {({ message }) => <ChatMessage message={message} />}
          </ThreadPrimitive.Messages>
        </div>
      </ThreadPrimitive.Viewport>
      <ComposerPrimitive.Root className="flex shrink-0 gap-2 border-t border-slate-200 p-3">
        <ComposerPrimitive.Input
          aria-label="Message tutor"
          placeholder="Ask the tutor to help you reason..."
          submitMode="enter"
          className="max-h-32 min-h-10 flex-1 resize-none rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 disabled:bg-slate-50"
        />
        <ComposerPrimitive.Send className="h-10 rounded-md bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300">
          {isRunning ? "Sending" : "Send"}
        </ComposerPrimitive.Send>
      </ComposerPrimitive.Root>
    </ThreadPrimitive.Root>
  );
}

function ChatMessage({ message }: { message: MessageState }) {
  const assistant = message.role === "assistant";

  return (
    <MessagePrimitive.Root
      className={`rounded-lg border px-3 py-2 text-sm ${
        assistant
          ? "border-blue-100 bg-blue-50 text-blue-950"
          : "border-slate-200 bg-white text-slate-800"
      }`}
    >
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
        {assistant ? "Tutor" : "You"}
      </div>
      {assistant ? <AssistantMessageBody message={message} /> : <UserMessageBody message={message} />}
    </MessagePrimitive.Root>
  );
}

function AssistantMessageBody({ message }: { message: MessageState }) {
  return (
    <MessagePrimitive.GroupedParts
      groupBy={(part) => {
        if (part.type === "reasoning") {
          return ["group-reasoning"];
        }
        return null;
      }}
    >
      {({ part, children }) => {
        if (part.type === "group-reasoning") {
          const running = part.status.type === "running";
          return (
            <ReasoningRoot defaultOpen={running}>
              <ReasoningTrigger active={running} />
              <ReasoningContent busy={running}>
                <ReasoningText>{children}</ReasoningText>
              </ReasoningContent>
            </ReasoningRoot>
          );
        }
        if (part.type === "text") {
          return <MarkdownText />;
        }
        if (part.type === "reasoning") {
          return <MarkdownText />;
        }
        return null;
      }}
    </MessagePrimitive.GroupedParts>
  );
}

function UserMessageBody({ message }: { message: MessageState }) {
  if (!messageText(message).trim()) {
    return null;
  }

  return <UserMarkdownText text={messageText(message)} />;
}

function ModeBadge({ mode }: { mode: TutorMode | null }) {
  return (
    <span className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-800">
      Mode: {mode ?? "waiting"}
    </span>
  );
}

function ContextBadge({ children }: { children: ReactNode }) {
  return (
    <span className="rounded border border-slate-200 bg-slate-50 px-2 py-1 font-medium text-slate-700">
      {children}
    </span>
  );
}

function SourceChips({ sources }: { sources: SourceRecord[] }) {
  return (
    <div className="mt-3">
      <div className="text-xs font-semibold text-slate-700">Sources available</div>
      <div className="mt-2 flex flex-wrap gap-2">
        {sources.map((source) =>
          source.url ? (
            <SourceChip
              key={source.id}
              href={source.url}
              title={source.title}
            />
          ) : (
            <span
              key={source.id}
              className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700"
            >
              {source.title}
            </span>
          ),
        )}
      </div>
    </div>
  );
}

function lastAssistantMode(history: ConversationHistoryResponse): TutorMode | null {
  return (
    [...history.messages].reverse().find((message) => message.role === "assistant" && message.mode)
      ?.mode ?? null
  );
}

function messageText(message: MessageState): string {
  return message.content
    .map((part) => {
      if (part.type === "text") {
        return part.text;
      }
      return "";
    })
    .join("");
}

function UserMarkdownText({ text }: { text: string }) {
  return <div className="whitespace-pre-wrap leading-6 text-slate-800">{text}</div>;
}
