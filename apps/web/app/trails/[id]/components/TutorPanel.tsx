"use client";

import {
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  ActionBarPrimitive,
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useThread,
  type MessageState,
} from "@assistant-ui/react";
import { ArrowDownIcon, ArrowUpIcon } from "lucide-react";

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
  MasteryStatus,
  SourceRecord,
  TutorMode,
  TutorStreamStatus,
  TutorToolEvent,
} from "@/lib/types";

type ReasoningView = "summary" | "full";

interface TutorPanelProps {
  workspaceId: string;
  trailId: string;
  concept: ConceptNode;
  sources?: SourceRecord[];
  onBack?: () => void;
  onMasteryUpdated?: (conceptId: string, update: { status: MasteryStatus; score: number }) => void;
}

export function TutorPanel({
  workspaceId,
  trailId,
  concept,
  sources = [],
  onBack,
  onMasteryUpdated,
}: TutorPanelProps) {
  const [history, setHistory] = useState<ConversationHistoryResponse | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [mode, setMode] = useState<TutorMode | null>(null);
  const [streamStatus, setStreamStatus] = useState<TutorStreamStatus | null>(null);
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
    setStreamStatus(null);

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
      <TutorShell
        concept={concept}
        sources={sources ?? []}
        mode={mode}
        streamStatus={streamStatus}
        onBack={onBack}
      >
        <div className="p-4 text-sm text-slate-500">Loading conversation...</div>
      </TutorShell>
    );
  }

  if (historyError || !history) {
    return (
      <TutorShell
        concept={concept}
        sources={sources ?? []}
        mode={mode}
        streamStatus={streamStatus}
        onBack={onBack}
      >
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
      streamStatus={streamStatus}
      chatError={chatError}
      onBack={onBack}
      onConversationId={setConversationId}
      onMode={(nextMode) => {
        setMode(nextMode);
        setChatError("");
      }}
      onStatus={setStreamStatus}
      onError={setChatError}
      onMasteryUpdated={onMasteryUpdated}
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
  streamStatus,
  chatError,
  onBack,
  onConversationId,
  onMode,
  onStatus,
  onError,
  onMasteryUpdated,
}: TutorPanelProps & {
  history: ConversationHistoryResponse;
  conversationId: string | null;
  mode: TutorMode | null;
  streamStatus: TutorStreamStatus | null;
  chatError: string;
  onConversationId: (conversationId: string) => void;
  onMode: (mode: TutorMode) => void;
  onStatus: (status: TutorStreamStatus | null) => void;
  onError: (message: string) => void;
}) {
  const [reasoningView, setReasoningView] = useState<ReasoningView>(() => {
    if (typeof window === "undefined") {
      return "summary";
    }
    return window.localStorage.getItem("colearni.reasoningView") === "full" ? "full" : "summary";
  });
  const runtime = useTutorRuntime({
    workspaceId,
    trailId,
    conceptId: concept.id,
    conversationId,
    history,
    onConversationId,
    onMode,
    onStatus,
    onError,
    onMasteryUpdated,
  });

  useEffect(() => {
    window.localStorage.setItem("colearni.reasoningView", reasoningView);
  }, [reasoningView]);

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <TutorShell
        concept={concept}
        sources={sources ?? []}
        mode={mode}
        streamStatus={streamStatus}
        onBack={onBack}
        reasoningView={reasoningView}
        onReasoningViewChange={setReasoningView}
      >
        {chatError ? (
          <div className="mx-4 mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {chatError}
          </div>
        ) : null}
        {mode === "quiz_prompt" ? (
          <div className="mx-4 mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
            Ready to level up? Go back to the concept details and use the Level Up button.
          </div>
        ) : null}
        <TutorThread reasoningView={reasoningView} />
      </TutorShell>
    </AssistantRuntimeProvider>
  );
}

function TutorShell({
  concept,
  sources,
  mode,
  streamStatus,
  onBack,
  reasoningView,
  onReasoningViewChange,
  children,
}: {
  concept: ConceptNode;
  sources: SourceRecord[];
  mode: TutorMode | null;
  streamStatus: TutorStreamStatus | null;
  onBack?: () => void;
  reasoningView?: ReasoningView;
  onReasoningViewChange?: (view: ReasoningView) => void;
  children: ReactNode;
}) {
  return (
    <section className="flex h-full min-h-[520px] flex-1 flex-col overflow-hidden rounded-md border border-slate-200 bg-white md:min-h-0">
      <div className="shrink-0 border-b border-slate-200 bg-white/95 p-3 backdrop-blur">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="mb-2 flex items-center gap-2">
              {onBack ? (
                <button
                  type="button"
                  aria-label="Back to concept details"
                  onClick={onBack}
                  className="inline-flex h-8 items-center gap-1.5 rounded-full border border-slate-200 px-2.5 text-xs font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-950"
                >
                  <span aria-hidden="true">←</span>
                  <span>Concept</span>
                </button>
              ) : null}
              {reasoningView && onReasoningViewChange ? (
                <ReasoningViewToggle value={reasoningView} onChange={onReasoningViewChange} />
              ) : null}
            </div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Learning thread
            </p>
            <h3 className="mt-1 truncate text-base font-semibold text-slate-950">{concept.title}</h3>
            {streamStatus ? (
              <p className="mt-1 text-xs text-slate-500">Status: {formatStreamStatus(streamStatus)}</p>
            ) : null}
          </div>
          <ModeBadge mode={mode} />
        </div>
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          <ContextBadge>Level: {concept.concept_level}</ContextBadge>
          <ContextBadge>Bloom: {concept.bloom_level}</ContextBadge>
          <ContextBadge>Difficulty: {concept.difficulty}</ContextBadge>
        </div>
        {sources.length > 0 ? <SourceChips sources={sources} /> : null}
      </div>
      {children}
    </section>
  );
}

function TutorThread({ reasoningView }: { reasoningView: ReasoningView }) {
  const messageCount = useThread((state) => state.messages.length);
  const isRunning = useThread((state) => state.isRunning);

  return (
    <ThreadPrimitive.Root className="flex min-h-0 flex-1 flex-col bg-gradient-to-b from-white to-slate-50/80">
      <ThreadPrimitive.Viewport
        autoScroll
        scrollToBottomOnRunStart
        scrollToBottomOnInitialize
        className="relative flex min-h-0 flex-1 flex-col overflow-y-auto px-4 py-5"
      >
        {messageCount === 0 ? (
          <WelcomeSuggestions />
        ) : null}
        <div className="grid gap-5">
          <ThreadPrimitive.Messages>
            {({ message }) => <ChatMessage message={message} reasoningView={reasoningView} />}
          </ThreadPrimitive.Messages>
        </div>
        <ThreadPrimitive.ScrollToBottom className="sticky bottom-24 ml-auto mt-3 grid size-9 place-items-center rounded-full border border-slate-200 bg-white text-slate-500 shadow-sm transition hover:bg-slate-50 disabled:hidden">
          <ArrowDownIcon className="size-4" />
        </ThreadPrimitive.ScrollToBottom>
        <ThreadPrimitive.ViewportFooter className="sticky bottom-0 mt-auto pt-4">
          <div className="bg-gradient-to-t from-slate-50 via-slate-50 to-transparent pb-3 pt-6">
            <ComposerPrimitive.Root className="rounded-3xl border border-slate-200 bg-white p-2 shadow-lg shadow-slate-200/70">
              <ComposerPrimitive.Input
                aria-label="Message tutor"
                placeholder="Ask for a hint, test an idea, or explain your thinking..."
                submitMode="enter"
                className="max-h-36 min-h-11 w-full resize-none bg-transparent px-3 pb-2 pt-2 text-sm leading-6 text-slate-900 outline-none placeholder:text-slate-400 disabled:text-slate-400"
              />
              <div className="flex items-center justify-between gap-2 px-1 pb-1">
                <span className="hidden pl-2 text-[11px] text-slate-400 sm:inline">Enter to send, Shift+Enter for a new line</span>
                {isRunning ? (
                  <ComposerPrimitive.Cancel className="h-9 rounded-full border border-slate-200 px-3 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40">
                    Stop
                  </ComposerPrimitive.Cancel>
                ) : (
                  <ComposerPrimitive.Send
                    aria-label="Send"
                    className="grid size-9 place-items-center rounded-full bg-slate-950 text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
                  >
                    <ArrowUpIcon className="size-4" />
                  </ComposerPrimitive.Send>
                )}
              </div>
            </ComposerPrimitive.Root>
          </div>
        </ThreadPrimitive.ViewportFooter>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  );
}

function ChatMessage({ message, reasoningView }: { message: MessageState; reasoningView: ReasoningView }) {
  const assistant = message.role === "assistant";

  return (
    <MessagePrimitive.Root
      className={`group flex w-full flex-col gap-1 text-sm ${assistant ? "items-start" : "items-end"}`}
    >
      {assistant ? (
        <div className="flex w-full max-w-3xl gap-3">
          <div className="mt-1 grid size-7 shrink-0 place-items-center rounded-full bg-slate-950 text-[11px] font-semibold text-white">
            CL
          </div>
          <div className="min-w-0 flex-1 text-slate-900">
            <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
              Tutor
            </div>
            <AssistantMessageBody message={message} reasoningView={reasoningView} />
            <AssistantActionBar />
          </div>
        </div>
      ) : (
        <div className="max-w-[88%] rounded-3xl bg-slate-950 px-4 py-2.5 text-white shadow-sm">
          <UserMessageBody message={message} />
          <UserActionBar />
        </div>
      )}
    </MessagePrimitive.Root>
  );
}

function AssistantMessageBody({
  message,
  reasoningView,
}: {
  message: MessageState;
  reasoningView: ReasoningView;
}) {
  return (
    <MessagePrimitive.GroupedParts
      groupBy={(part) => {
        if (
          part.type === "data" &&
          (part.name === "tutor-status" ||
            part.name === "tutor-thinking" ||
            part.name === "tutor-tool-call" ||
            part.name === "tutor-tool-result")
        ) {
          return ["group-chain-of-thought"];
        }
        if (part.type === "reasoning") {
          return ["group-chain-of-thought"];
        }
        return null;
      }}
    >
      {({ part, children }) => {
        if (part.type === "group-chain-of-thought") {
          const running = part.status.type === "running";
          const full = reasoningView === "full";
          return (
            <ReasoningRoot defaultOpen={running}>
              <ReasoningTrigger
                active={running}
                label={
                  full
                    ? undefined
                    : { open: "Hide reasoning summary", closed: "Show reasoning summary" }
                }
              />
              <ReasoningContent busy={running}>
                {full ? (
                  <div className="grid gap-3">{children}</div>
                ) : (
                  <CompactReasoningTrace message={message} running={running} />
                )}
              </ReasoningContent>
            </ReasoningRoot>
          );
        }
        if (part.type === "data" && part.name === "tutor-status") {
          return <TutorStatusLine status={(part.data as { status?: TutorStreamStatus }).status ?? null} />;
        }
        if (part.type === "data" && part.name === "tutor-thinking") {
          return <TutorThinkingLine text={(part.data as { text?: string }).text ?? ""} />;
        }
        if (part.type === "data" && part.name === "tutor-tool-call") {
          return <TutorToolCallLine tool={part.data as TutorToolEvent} />;
        }
        if (part.type === "data" && part.name === "tutor-tool-result") {
          return <TutorToolResultLine tool={part.data as TutorToolEvent} />;
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

function WelcomeSuggestions() {
  const suggestions = [
    "Give me one hint to get started.",
    "Ask me a Socratic question about this concept.",
    "Check whether my current understanding is right.",
  ];

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col items-center rounded-3xl border border-dashed border-slate-300 bg-white/80 p-5 text-center shadow-sm">
      <div className="text-sm font-semibold text-slate-900">Start with a learning move</div>
      <p className="mt-1 text-sm text-slate-500">Pick a prompt or write your own. The tutor will keep you reasoning one step at a time.</p>
      <div className="mt-4 grid w-full gap-2 sm:grid-cols-3">
        {suggestions.map((suggestion) => (
          <ThreadPrimitive.Suggestion
            key={suggestion}
            prompt={suggestion}
            send
            className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3 text-left text-xs font-medium text-slate-700 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-800"
          >
            {suggestion}
          </ThreadPrimitive.Suggestion>
        ))}
      </div>
    </div>
  );
}

function ReasoningViewToggle({
  value,
  onChange,
}: {
  value: ReasoningView;
  onChange: (view: ReasoningView) => void;
}) {
  const full = value === "full";
  return (
    <button
      type="button"
      aria-pressed={full}
      aria-label={full ? "Use learner-safe reasoning summary" : "Show full reasoning trace"}
      onClick={() => onChange(full ? "summary" : "full")}
      className="inline-flex h-8 items-center rounded-full border border-amber-200 bg-amber-50 px-2.5 text-xs font-medium text-amber-800 hover:bg-amber-100"
    >
      Reasoning: {full ? "Full trace" : "Summary"}
    </button>
  );
}

function CompactReasoningTrace({ message, running }: { message: MessageState; running: boolean }) {
  const firstThinking = firstReasoningText(message);
  const toolSeen = message.content.some(
    (part) => part.type === "data" && (part.name === "tutor-tool-call" || part.name === "tutor-tool-result"),
  );
  const snippet = learnerSafeSnippet(firstThinking);

  return (
    <div className="rounded-md border border-amber-200 bg-white/70 px-3 py-2 text-sm text-amber-950">
      <div className="flex items-center gap-2 font-semibold">
        <span>Thinking through the next step</span>
        {running ? <span className="h-2 w-16 animate-pulse rounded-full bg-amber-200" /> : null}
      </div>
      <p className="mt-1 text-amber-950/75">
        {snippet || (running ? "Choosing a focused question..." : "Reasoning trace available.")}
      </p>
      {toolSeen ? (
        <p className="mt-1 text-xs font-medium text-amber-800/80">
          Checked tutor guidance without exposing internal instructions.
        </p>
      ) : null}
    </div>
  );
}

function AssistantActionBar() {
  return (
    <ActionBarPrimitive.Root
      hideWhenRunning
      autohide="not-last"
      autohideFloat="always"
      className="mt-1 flex gap-1 text-xs text-slate-400 data-[floating]:opacity-0 data-[floating]:transition-opacity group-hover:data-[floating]:opacity-100"
    >
      <ActionBarPrimitive.Copy className="rounded-md px-2 py-1 hover:bg-slate-100 hover:text-slate-700">
        Copy
      </ActionBarPrimitive.Copy>
      <ActionBarPrimitive.Reload className="rounded-md px-2 py-1 hover:bg-slate-100 hover:text-slate-700">
        Regenerate
      </ActionBarPrimitive.Reload>
    </ActionBarPrimitive.Root>
  );
}

function UserActionBar() {
  return (
    <ActionBarPrimitive.Root
      hideWhenRunning
      autohide="always"
      autohideFloat="always"
      className="mt-1 flex justify-end text-xs text-slate-300 data-[floating]:opacity-0 data-[floating]:transition-opacity group-hover:data-[floating]:opacity-100"
    >
      <ActionBarPrimitive.Edit className="rounded-md px-2 py-1 hover:bg-white/10 hover:text-white">
        Edit
      </ActionBarPrimitive.Edit>
    </ActionBarPrimitive.Root>
  );
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
  return <div className="whitespace-pre-wrap leading-6 text-white">{text}</div>;
}

function firstReasoningText(message: MessageState): string {
  for (const part of message.content) {
    if (part.type === "reasoning") {
      return part.text;
    }
    if (isTutorDataPart(part, "tutor-thinking")) {
      return (part.data as { text?: string }).text ?? "";
    }
  }
  return "";
}

function isTutorDataPart(
  part: MessageState["content"][number],
  name: string,
): part is MessageState["content"][number] & { type: "data"; name: string } {
  return part.type === "data" && part.name === name;
}

function learnerSafeSnippet(text: string): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (!normalized) {
    return "";
  }
  const firstSentence = normalized.match(/^(.{20,180}?[.!?])\s/)?.[1];
  if (firstSentence) {
    return firstSentence;
  }
  const words = normalized.split(" ").slice(0, 18).join(" ");
  return words.length < normalized.length ? `${words}...` : words;
}

function TutorStatusLine({ status }: { status: TutorStreamStatus | null }) {
  if (!status) {
    return null;
  }

  return (
    <div className="mb-2 rounded border border-amber-200 bg-amber-100/60 px-2 py-1 text-xs font-medium text-amber-900">
      {formatStreamStatus(status)}
    </div>
  );
}

function TutorThinkingLine({ text }: { text: string }) {
  if (!text.trim()) {
    return null;
  }

  return (
    <ReasoningText>
      <div className="italic text-amber-950/75">{text}</div>
    </ReasoningText>
  );
}

function TutorToolCallLine({ tool }: { tool: TutorToolEvent }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800">
      <div className="flex items-center justify-between gap-3">
        <span className="font-semibold">{tool.name}</span>
        {tool.mode ? (
          <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-700">
            {tool.mode}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function TutorToolResultLine({ tool }: { tool: TutorToolEvent }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white text-sm text-slate-800">
      <div className="border-b border-slate-200 px-3 py-2 font-semibold">{tool.name} result</div>
      {tool.result ? (
        <pre className="max-h-44 overflow-y-auto whitespace-pre-wrap px-3 py-2 text-xs leading-5 text-slate-600">
          {tool.result}
        </pre>
      ) : null}
    </div>
  );
}

function formatStreamStatus(status: TutorStreamStatus): string {
  switch (status) {
    case "thinking":
      return "Thinking";
    case "calling_tool":
      return "Calling tool";
    case "tool_called":
      return "Tool requested";
    case "tool_complete":
      return "Tool result ready";
    case "responding":
      return "Responding";
    case "retrying_without_thinking":
      return "Retrying without thinking";
  }
}
