"use client";

import { useEffect, useState, type ReactNode } from "react";
import {
  ActionBarPrimitive,
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useMessageRuntime,
  useThread,
  type MessageState,
} from "@assistant-ui/react";
import {
  ArrowDownIcon,
  ArrowUpIcon,
  CopyIcon,
  MoreHorizontalIcon,
  PencilIcon,
  RotateCcwIcon,
} from "lucide-react";

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
  onMasteryUpdated?: (
    conceptId: string,
    update: { status: MasteryStatus; score: number },
  ) => void;
}

export function TutorPanel({
  workspaceId,
  trailId,
  concept,
  sources = [],
  onBack,
  onMasteryUpdated,
}: TutorPanelProps) {
  const [history, setHistory] = useState<ConversationHistoryResponse | null>(
    null,
  );
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [mode, setMode] = useState<TutorMode | null>(null);
  const [streamStatus, setStreamStatus] = useState<TutorStreamStatus | null>(
    null,
  );
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
        const nextHistory = await getConversation(
          workspaceId,
          trailId,
          concept.id,
        );
        if (cancelled) {
          return;
        }
        setHistory(nextHistory);
        setConversationId(nextHistory.conversation_id);
        setMode(lastAssistantMode(nextHistory));
      } catch (exc) {
        if (!cancelled) {
          setHistoryError(
            exc instanceof Error ? exc.message : "Could not load conversation",
          );
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
        <div className="p-4 text-sm text-slate-500">
          Loading conversation...
        </div>
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
    return window.localStorage.getItem("colearni.reasoningView") === "full"
      ? "full"
      : "summary";
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
            Ready to level up? Go back to the concept details and use the Level
            Up button.
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
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <section className="flex h-full min-h-[520px] flex-1 flex-col rounded-md border border-slate-200 bg-white md:min-h-0">
      <div className="relative z-30 shrink-0 border-b border-slate-200 bg-white/95 px-3 py-2 backdrop-blur">
        <div className="flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            {onBack ? (
              <button
                type="button"
                aria-label="Back to concept details"
                onClick={onBack}
                className="grid size-8 shrink-0 place-items-center rounded-full border border-slate-200 text-base text-slate-600 hover:bg-slate-50 hover:text-slate-950"
              >
                <span aria-hidden="true">←</span>
              </button>
            ) : null}
            <div className="min-w-0">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                Learning thread
              </p>
              <h3 className="truncate text-sm font-semibold text-slate-950 sm:text-base">
                {concept.title}
              </h3>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            {streamStatus ? <StatusBadge status={streamStatus} /> : null}
            <ModeBadge mode={mode} />
            <div className="relative">
              <button
                type="button"
                aria-label="Thread options"
                aria-expanded={menuOpen}
                onClick={() => setMenuOpen((open) => !open)}
                className="grid size-8 place-items-center rounded-full border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 hover:text-slate-950"
              >
                <MoreHorizontalIcon className="size-4" />
              </button>
              {menuOpen ? (
                <div className="absolute right-0 z-50 mt-2 w-64 rounded-2xl border border-slate-200 bg-white p-3 text-xs shadow-2xl shadow-slate-300/70 ring-1 ring-slate-950/5">
                  <div className="grid gap-2">
                    {reasoningView && onReasoningViewChange ? (
                      <ReasoningViewToggle
                        value={reasoningView}
                        onChange={onReasoningViewChange}
                      />
                    ) : null}
                    <div className="flex flex-wrap gap-1.5">
                      <ContextBadge>
                        Level: {concept.concept_level}
                      </ContextBadge>
                      <ContextBadge>Bloom: {concept.bloom_level}</ContextBadge>
                      <ContextBadge>
                        Difficulty: {concept.difficulty}
                      </ContextBadge>
                    </div>
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                      {sources.length} source{sources.length === 1 ? "" : "s"}{" "}
                      linked
                    </div>
                    {sources.length > 0 ? (
                      <SourceChips sources={sources} compact />
                    ) : null}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </div>
      {children}
    </section>
  );
}

function TutorThread({ reasoningView }: { reasoningView: ReasoningView }) {
  const messageCount = useThread((state) => state.messages.length);
  const isRunning = useThread((state) => state.isRunning);
  const latestUserMessageId = useThread(
    (state) =>
      [...state.messages].reverse().find((message) => message.role === "user")
        ?.id ?? null,
  );

  return (
    <ThreadPrimitive.Root className="flex min-h-0 flex-1 flex-col bg-gradient-to-b from-white to-slate-50/80">
      <ThreadPrimitive.Viewport
        autoScroll
        scrollToBottomOnRunStart
        scrollToBottomOnInitialize
        className="relative flex min-h-0 flex-1 flex-col overflow-y-auto px-4 py-5"
      >
        {messageCount === 0 ? <WelcomeSuggestions /> : null}
        <div className="grid gap-5">
          <ThreadPrimitive.Messages>
            {({ message }) => (
              <ChatMessage
                message={message}
                reasoningView={reasoningView}
                isLatestUserMessage={message.id === latestUserMessageId}
              />
            )}
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
                <span className="hidden pl-2 text-[11px] text-slate-400 sm:inline">
                  Enter to send, Shift+Enter for a new line
                </span>
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

function ChatMessage({
  message,
  reasoningView,
  isLatestUserMessage,
}: {
  message: MessageState;
  reasoningView: ReasoningView;
  isLatestUserMessage: boolean;
}) {
  const assistant = message.role === "assistant";
  const messageRuntime = useMessageRuntime({ optional: true });
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(() => messageText(message));

  const startEditing = () => {
    setDraft(messageText(message));
    setEditing(true);
  };

  const submitEdit = () => {
    const nextText = draft.trim();
    if (!nextText || !messageRuntime) {
      return;
    }
    // Drive the edit through the message's native edit composer so assistant-ui
    // branches from the original turn (instead of appending a duplicate). The
    // replaceLatestUser runConfig tells the backend to replace the latest user
    // turn and regenerate, matching the branch the client now shows.
    const composer = messageRuntime.composer;
    composer.beginEdit();
    composer.setText(nextText);
    composer.setRunConfig({ custom: { replaceLatestUser: true } });
    composer.send();
    setEditing(false);
  };

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
            <AssistantMessageBody
              message={message}
              reasoningView={reasoningView}
            />
            <AssistantActionBar canRegenerate={message.isLast} />
          </div>
        </div>
      ) : (
        <div className="max-w-[88%]">
          {editing ? (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                submitEdit();
              }}
              className="rounded-3xl bg-slate-950 p-2 text-white shadow-sm"
            >
              <textarea
                aria-label="Edit message text"
                value={draft}
                autoFocus
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    submitEdit();
                  }
                  if (event.key === "Escape") {
                    event.preventDefault();
                    setEditing(false);
                  }
                }}
                className="min-h-20 w-full resize-none rounded-2xl bg-white/10 px-3 py-2 text-sm leading-6 text-white outline-none placeholder:text-white/40 focus:ring-2 focus:ring-white/30"
              />
              <div className="mt-2 flex items-center justify-between gap-2">
                <span className="hidden pl-1 text-[11px] text-white/50 sm:inline">
                  Enter to save, Shift+Enter for a new line
                </span>
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setEditing(false)}
                    className="rounded-full px-3 py-1.5 text-xs font-medium text-white/70 hover:bg-white/10 hover:text-white"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={!draft.trim()}
                    className="rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-slate-950 hover:bg-slate-100 disabled:cursor-not-allowed disabled:bg-white/40 disabled:text-slate-500"
                  >
                    Save
                  </button>
                </div>
              </div>
            </form>
          ) : (
            <>
              <div className="rounded-3xl bg-slate-950 px-4 py-2.5 text-white shadow-sm">
                <UserMessageBody message={message} />
              </div>
              {isLatestUserMessage ? (
                <UserActionBar onEdit={startEditing} />
              ) : null}
            </>
          )}
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
                    : {
                        open: "Hide reasoning summary",
                        closed: "Show reasoning summary",
                      }
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
          return (
            <TutorStatusLine
              status={
                (part.data as { status?: TutorStreamStatus }).status ?? null
              }
            />
          );
        }
        if (part.type === "data" && part.name === "tutor-thinking") {
          return (
            <TutorThinkingLine
              text={(part.data as { text?: string }).text ?? ""}
            />
          );
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
      <div className="text-sm font-semibold text-slate-900">
        Start with a learning move
      </div>
      <p className="mt-1 text-sm text-slate-500">
        Pick a prompt or write your own. The tutor will keep you reasoning one
        step at a time.
      </p>
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
      aria-label={
        full
          ? "Use learner-safe reasoning summary"
          : "Show full reasoning trace"
      }
      onClick={() => onChange(full ? "summary" : "full")}
      className="inline-flex h-8 w-full items-center justify-center rounded-full border border-amber-200 bg-amber-50 px-2.5 text-xs font-medium text-amber-800 hover:bg-amber-100"
    >
      Reasoning: {full ? "Full trace" : "Summary"}
    </button>
  );
}

function CompactReasoningTrace({
  message,
  running,
}: {
  message: MessageState;
  running: boolean;
}) {
  const steps = compactReasoningSteps(message);

  return (
    <div className="rounded-md border border-amber-200 bg-white/70 px-3 py-2 text-sm text-amber-950">
      <div className="flex items-center gap-2 font-semibold">
        <span>Reasoning summary</span>
      </div>
      {steps.length > 0 ? (
        <div className="mt-2 grid gap-1.5">
          {steps.map((step, index) => (
            <div
              key={`${step.label}-${index}`}
              className={`rounded border border-amber-200/80 bg-amber-50/70 px-2 py-1.5 ${
                running && index === steps.length - 1
                  ? "shadow-[inset_3px_0_0_rgb(251_191_36)]"
                  : ""
              }`}
            >
              <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-amber-800">
                {step.label}
                {running && index === steps.length - 1 ? (
                  <span className="size-1.5 animate-pulse rounded-full bg-amber-500" />
                ) : null}
              </div>
              {step.detail ? (
                <div className="mt-0.5 text-amber-950/75">{step.detail}</div>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
      {steps.length === 0 ? (
        <p className="mt-1 text-amber-950/75">
          {running
            ? "Choosing a focused question..."
            : "Reasoning trace available."}
        </p>
      ) : null}
    </div>
  );
}

function AssistantActionBar({ canRegenerate }: { canRegenerate: boolean }) {
  const messageRuntime = useMessageRuntime({ optional: true });
  return (
    <ActionBarPrimitive.Root
      hideWhenRunning
      autohide="never"
      autohideFloat="never"
      className="mt-1 flex w-fit items-center gap-1 text-slate-500"
    >
      <ActionBarPrimitive.Copy
        aria-label="Copy message"
        title="Copy"
        className="grid size-7 place-items-center rounded-md text-slate-500 transition hover:bg-slate-100 hover:text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
      >
        <CopyIcon className="size-4" />
      </ActionBarPrimitive.Copy>
      {canRegenerate && messageRuntime ? (
        <button
          type="button"
          aria-label="Regenerate response"
          title="Regenerate"
          onClick={() =>
            messageRuntime.reload({
              runConfig: { custom: { regenerate: true } },
            })
          }
          className="grid size-7 place-items-center rounded-md text-slate-500 transition hover:bg-slate-100 hover:text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
        >
          <RotateCcwIcon className="size-4" />
        </button>
      ) : null}
    </ActionBarPrimitive.Root>
  );
}

function UserActionBar({ onEdit }: { onEdit: () => void }) {
  return (
    <ActionBarPrimitive.Root
      hideWhenRunning
      autohide="never"
      autohideFloat="never"
      className="mt-1 flex justify-end text-slate-500"
    >
      <button
        type="button"
        aria-label="Edit message"
        title="Edit"
        onClick={onEdit}
        className="grid size-7 place-items-center rounded-md transition hover:bg-slate-100 hover:text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
      >
        <PencilIcon className="size-4" />
      </button>
    </ActionBarPrimitive.Root>
  );
}

function ModeBadge({ mode }: { mode: TutorMode | null }) {
  return (
    <span className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-[11px] font-semibold text-blue-800 sm:text-xs">
      {mode ?? "waiting"}
    </span>
  );
}

function StatusBadge({ status }: { status: TutorStreamStatus }) {
  return (
    <span className="hidden rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[11px] font-semibold text-amber-800 sm:inline-flex sm:text-xs">
      {formatStreamStatus(status)}
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

function SourceChips({
  sources,
  compact = false,
}: {
  sources: SourceRecord[];
  compact?: boolean;
}) {
  return (
    <div className={compact ? "" : "mt-3"}>
      <div className="text-xs font-semibold text-slate-700">
        Sources available
      </div>
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

function lastAssistantMode(
  history: ConversationHistoryResponse,
): TutorMode | null {
  return (
    [...history.messages]
      .reverse()
      .find((message) => message.role === "assistant" && message.mode)?.mode ??
    null
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

function compactReasoningSteps(
  message: MessageState,
): Array<{ label: string; detail: string }> {
  const steps: Array<{ label: string; detail: string }> = [];
  for (const part of message.content) {
    if (part.type === "reasoning") {
      const detail = learnerSafeSnippet(part.text);
      if (detail) {
        steps.push({ label: "Thinking", detail });
      }
    } else if (isTutorDataPart(part, "tutor-thinking")) {
      const detail = learnerSafeSnippet(
        (part.data as { text?: string }).text ?? "",
      );
      if (detail) {
        steps.push({ label: "Thinking", detail });
      }
    } else if (isTutorDataPart(part, "tutor-tool-call")) {
      const tool = part.data as TutorToolEvent;
      steps.push({
        label: toolSummaryLabel(tool),
        detail: toolSummaryDetail(tool),
      });
    }
    if (steps.length >= 6) {
      break;
    }
  }
  return steps;
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

function formatToolName(name: string): string {
  return name.replaceAll("_", " ");
}

function toolSummaryLabel(tool: TutorToolEvent): string {
  if (tool.name === "search_sources") {
    return "Searching sources";
  }
  if (tool.name === "read_document_section") {
    return "Reading source";
  }
  if (tool.name === "get_concept_sources") {
    return "Checking sources";
  }
  if (tool.name === "get_graph_neighbourhood") {
    return "Checking graph";
  }
  if (tool.name === "get_tutor_instructions") {
    return "Choosing response style";
  }
  return "Using tool";
}

function toolSummaryDetail(tool: TutorToolEvent): string {
  if (tool.name === "search_sources" && tool.query) {
    return `"${tool.query}"`;
  }
  if (tool.mode) {
    return tool.mode;
  }
  return formatToolName(tool.name);
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
        <span className="font-semibold">{toolSummaryLabel(tool)}</span>
        {tool.mode ? (
          <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-700">
            {tool.mode}
          </span>
        ) : null}
      </div>
      {tool.query ? (
        <div className="mt-1 text-slate-600">{tool.query}</div>
      ) : null}
    </div>
  );
}

function TutorToolResultLine({ tool }: { tool: TutorToolEvent }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white text-sm text-slate-800">
      <div className="border-b border-slate-200 px-3 py-2 font-semibold">
        {tool.name} result
      </div>
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
