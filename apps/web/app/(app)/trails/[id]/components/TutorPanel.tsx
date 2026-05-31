"use client";

import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
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
  ArrowLeft,
  ArrowUpIcon,
  Bookmark,
  CopyIcon,
  GaugeIcon,
  LayersIcon,
  LinkIcon,
  MoreHorizontalIcon,
  PencilIcon,
  PlusIcon,
  RotateCcwIcon,
  TargetIcon,
  X,
  type LucideIcon,
} from "lucide-react";

import { MarkdownText } from "@/components/assistant-ui/markdown-text";
import {
  ReasoningContent,
  ReasoningRoot,
  ReasoningText,
  ReasoningTrigger,
} from "@/components/assistant-ui/reasoning";
import { SourceChip } from "@/components/assistant-ui/sources";
import {
  createConversationThread,
  createNote,
  deleteConversationThread,
  deleteNote,
  getConversation,
  listConversationThreads,
  listNotes,
  updateConversationThread,
  updateNote,
} from "@/lib/api";
import { formatBloomLevel, titleCase } from "@/lib/display";
import { useTutorRuntime } from "@/lib/tutor-runtime";
import type {
  ConceptNode,
  ConversationHistoryResponse,
  ConversationThreadSummary,
  MasteryStatus,
  Note,
  SourceRecord,
  TutorMode,
  TutorStreamStatus,
  TutorToolEvent,
} from "@/lib/types";
import type { ArtifactKind } from "@/lib/artifacts";

type ReasoningView = "summary" | "full";
type TutorPanelTab = "tutor" | "notes";

type TutorHistoryState = {
  key: string;
  status: "loading" | "ready" | "error";
  history: ConversationHistoryResponse | null;
  conversationId: string | null;
  mode: TutorMode | null;
  historyError: string;
  chatError: string;
};

function tutorHistoryKey(
  workspaceId: string,
  trailId: string,
  conceptId: string,
  loadKey: number,
  selectedThreadId: string | null,
) {
  return `${workspaceId}:${trailId}:${conceptId}:${selectedThreadId ?? "latest"}:${loadKey}`;
}

function loadingTutorHistoryState(key: string): TutorHistoryState {
  return {
    key,
    status: "loading",
    history: null,
    conversationId: null,
    mode: null,
    historyError: "",
    chatError: "",
  };
}

interface TutorPanelProps {
  workspaceId: string;
  trailId: string;
  concept: ConceptNode;
  sources?: SourceRecord[];
  sampleQuestions?: string[];
  embeddedInConceptPanel?: boolean;
  bookmarked?: boolean;
  onToggleBookmark?: () => void;
  onPanelClose?: () => void;
  onBack?: () => void;
  onSuggestQuiz?: (quizType: "level_up" | "practice") => void;
  onSuggestFlashcards?: () => void;
  onSuggestArtifact?: (kind: ArtifactKind) => void;
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
  sampleQuestions,
  embeddedInConceptPanel = false,
  bookmarked = false,
  onToggleBookmark,
  onPanelClose,
  onBack,
  onSuggestQuiz,
  onSuggestFlashcards,
  onSuggestArtifact,
  onMasteryUpdated,
}: TutorPanelProps) {
  const [loadKey, setLoadKey] = useState(0);
  const [threads, setThreads] = useState<ConversationThreadSummary[]>([]);
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const historyKey = tutorHistoryKey(
    workspaceId,
    trailId,
    concept.id,
    loadKey,
    selectedThreadId,
  );
  const [historyState, setHistoryState] = useState<TutorHistoryState>(() =>
    loadingTutorHistoryState(historyKey),
  );
  const currentHistoryState =
    historyState.key === historyKey
      ? historyState
      : loadingTutorHistoryState(historyKey);
  const { history, conversationId, mode, historyError, chatError } =
    currentHistoryState;
  const loading = currentHistoryState.status === "loading";

  useEffect(() => {
    let cancelled = false;

    async function loadHistory() {
      try {
        const threadList = await listConversationThreads(
          workspaceId,
          trailId,
          concept.id,
        );
        const threadId =
          selectedThreadId ?? threadList.conversations[0]?.id ?? null;
        const nextHistory = await getConversation(
          workspaceId,
          trailId,
          concept.id,
          {
            conversationId: threadId,
          },
        );
        if (cancelled) {
          return;
        }
        setThreads(threadList.conversations);
        if (!selectedThreadId && nextHistory.conversation_id) {
          setSelectedThreadId(nextHistory.conversation_id);
        }
        setHistoryState({
          key: historyKey,
          status: "ready",
          history: nextHistory,
          conversationId: nextHistory.conversation_id,
          mode: lastAssistantMode(nextHistory),
          historyError: "",
          chatError: "",
        });
      } catch (exc) {
        if (!cancelled) {
          setHistoryState({
            ...loadingTutorHistoryState(historyKey),
            status: "error",
            historyError:
              exc instanceof Error
                ? exc.message
                : "Could not load conversation",
          });
        }
      }
    }

    void loadHistory();
    return () => {
      cancelled = true;
    };
  }, [workspaceId, trailId, concept.id, historyKey, selectedThreadId]);

  if (loading) {
    return (
      <TutorShell
        concept={concept}
        sources={sources ?? []}
        mode={mode}
        embeddedInConceptPanel={embeddedInConceptPanel}
        bookmarked={bookmarked}
        onToggleBookmark={onToggleBookmark}
        onPanelClose={onPanelClose}
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
        embeddedInConceptPanel={embeddedInConceptPanel}
        bookmarked={bookmarked}
        onToggleBookmark={onToggleBookmark}
        onPanelClose={onPanelClose}
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
      key={`${concept.id}:${conversationId ?? "new"}`}
      workspaceId={workspaceId}
      trailId={trailId}
      concept={concept}
      sources={sources}
      sampleQuestions={sampleQuestions}
      embeddedInConceptPanel={embeddedInConceptPanel}
      bookmarked={bookmarked}
      onToggleBookmark={onToggleBookmark}
      onPanelClose={onPanelClose}
      history={history}
      conversationId={conversationId}
      mode={mode}
      chatError={chatError}
      onBack={onBack}
      onSuggestQuiz={onSuggestQuiz}
      onSuggestFlashcards={onSuggestFlashcards}
      onSuggestArtifact={onSuggestArtifact}
      threads={threads}
      selectedThreadId={selectedThreadId}
      onSelectThread={(threadId) => setSelectedThreadId(threadId)}
      onCreateThread={async () => {
        const thread = await createConversationThread(
          workspaceId,
          trailId,
          concept.id,
        );
        setThreads((current) => [thread, ...current]);
        setSelectedThreadId(thread.id);
        setHistoryState({
          ...loadingTutorHistoryState(historyKey),
          key: historyKey,
        });
      }}
      onRenameThread={async (threadId, title) => {
        const updated = await updateConversationThread(
          workspaceId,
          trailId,
          concept.id,
          threadId,
          title,
        );
        setThreads((current) =>
          current.map((thread) => (thread.id === threadId ? updated : thread)),
        );
      }}
      onDeleteThread={async (threadId) => {
        await deleteConversationThread(
          workspaceId,
          trailId,
          concept.id,
          threadId,
        );
        setThreads((current) => {
          const remaining = current.filter((thread) => thread.id !== threadId);
          if (selectedThreadId === threadId) {
            setSelectedThreadId(remaining[0]?.id ?? null);
          }
          return remaining;
        });
      }}
      onConversationId={(nextConversationId) => {
        setSelectedThreadId(nextConversationId);
        setHistoryState((current) =>
          current.key === historyKey
            ? { ...current, conversationId: nextConversationId }
            : current,
        );
      }}
      onMode={(nextMode) => {
        setHistoryState((current) =>
          current.key === historyKey
            ? { ...current, mode: nextMode, chatError: "" }
            : current,
        );
      }}
      onError={(message) => {
        setHistoryState((current) =>
          current.key === historyKey
            ? { ...current, chatError: message }
            : current,
        );
      }}
      onMasteryUpdated={onMasteryUpdated}
    />
  );
}

function TutorRuntimePanel({
  workspaceId,
  trailId,
  concept,
  sources,
  sampleQuestions,
  embeddedInConceptPanel = false,
  bookmarked = false,
  onToggleBookmark,
  onPanelClose,
  history,
  conversationId,
  mode,
  chatError,
  onBack,
  onSuggestQuiz,
  onSuggestFlashcards,
  onSuggestArtifact,
  threads,
  selectedThreadId,
  onSelectThread,
  onCreateThread,
  onRenameThread,
  onDeleteThread,
  onConversationId,
  onMode,
  onError,
  onMasteryUpdated,
}: TutorPanelProps & {
  history: ConversationHistoryResponse;
  conversationId: string | null;
  mode: TutorMode | null;
  chatError: string;
  threads: ConversationThreadSummary[];
  selectedThreadId: string | null;
  onSelectThread: (threadId: string) => void;
  onCreateThread: () => Promise<void>;
  onRenameThread: (threadId: string, title: string) => Promise<void>;
  onDeleteThread: (threadId: string) => Promise<void>;
  onConversationId: (conversationId: string) => void;
  onMode: (mode: TutorMode) => void;
  onError: (message: string) => void;
}) {
  const [activeTab, setActiveTab] = useState<TutorPanelTab>("tutor");
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
    onError,
    onMasteryUpdated,
  });

  useEffect(() => {
    window.localStorage.setItem("colearni.reasoningView", reasoningView);
  }, [reasoningView]);

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <SuggestQuizContext.Provider value={onSuggestQuiz ?? null}>
        <SuggestFlashcardsContext.Provider value={onSuggestFlashcards ?? null}>
          <SuggestArtifactContext.Provider value={onSuggestArtifact ?? null}>
            <TutorShell
              concept={concept}
              sources={sources ?? []}
              mode={mode}
              embeddedInConceptPanel={embeddedInConceptPanel}
              bookmarked={bookmarked}
              onToggleBookmark={onToggleBookmark}
              onPanelClose={onPanelClose}
              onBack={onBack}
              activeTab={activeTab}
              onActiveTabChange={setActiveTab}
              reasoningView={reasoningView}
              onReasoningViewChange={setReasoningView}
              threads={threads}
              selectedThreadId={selectedThreadId}
              onSelectThread={onSelectThread}
              onCreateThread={onCreateThread}
              onRenameThread={onRenameThread}
              onDeleteThread={onDeleteThread}
            >
              {activeTab === "tutor" ? (
                <>
                  {chatError ? (
                    <div className="mx-4 mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                      {chatError}
                    </div>
                  ) : null}
                  {mode === "quiz_prompt" ? (
                    <div className="mx-4 mt-3 flex flex-col gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 sm:flex-row sm:items-center sm:justify-between">
                      <span>
                        Ready to level up? Take the quiz to check your
                        understanding.
                      </span>
                      {onSuggestQuiz ? (
                        <button
                          type="button"
                          onClick={() => onSuggestQuiz("level_up")}
                          className="shrink-0 self-start rounded-full bg-emerald-600 px-4 py-1.5 text-xs font-semibold text-white transition hover:bg-emerald-500 sm:self-auto"
                        >
                          Start level-up quiz
                        </button>
                      ) : null}
                    </div>
                  ) : null}
                  <TutorThread
                    reasoningView={reasoningView}
                    sampleQuestions={sampleQuestions}
                  />
                </>
              ) : (
                <NotesPanel
                  workspaceId={workspaceId}
                  trailId={trailId}
                  concept={concept}
                />
              )}
            </TutorShell>
          </SuggestArtifactContext.Provider>
        </SuggestFlashcardsContext.Provider>
      </SuggestQuizContext.Provider>
    </AssistantRuntimeProvider>
  );
}

function TutorShell({
  concept,
  sources,
  mode,
  embeddedInConceptPanel = false,
  bookmarked = false,
  onToggleBookmark,
  onPanelClose,
  onBack,
  activeTab = "tutor",
  onActiveTabChange,
  reasoningView,
  onReasoningViewChange,
  threads = [],
  selectedThreadId = null,
  onSelectThread,
  onCreateThread,
  onRenameThread,
  onDeleteThread,
  children,
}: {
  concept: ConceptNode;
  sources: SourceRecord[];
  mode: TutorMode | null;
  embeddedInConceptPanel?: boolean;
  bookmarked?: boolean;
  onToggleBookmark?: () => void;
  onPanelClose?: () => void;
  onBack?: () => void;
  activeTab?: TutorPanelTab;
  onActiveTabChange?: (tab: TutorPanelTab) => void;
  reasoningView?: ReasoningView;
  onReasoningViewChange?: (view: ReasoningView) => void;
  threads?: ConversationThreadSummary[];
  selectedThreadId?: string | null;
  onSelectThread?: (threadId: string) => void;
  onCreateThread?: () => Promise<void>;
  onRenameThread?: (threadId: string, title: string) => Promise<void>;
  onDeleteThread?: (threadId: string) => Promise<void>;
  children: ReactNode;
}) {
  const [creatingThread, setCreatingThread] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuContainerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!menuOpen) return;

    function handlePointerDown(event: PointerEvent) {
      if (
        menuContainerRef.current &&
        !menuContainerRef.current.contains(event.target as Node)
      ) {
        setMenuOpen(false);
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMenuOpen(false);
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    window.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      window.removeEventListener("keydown", handleEscape);
    };
  }, [menuOpen]);

  return (
    <section className="flex h-full min-h-0 flex-1 flex-col rounded-md border border-slate-200 bg-white">
      <div className="relative z-30 shrink-0 border-b border-slate-200 bg-white/95 px-3 py-2 backdrop-blur">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 flex-1 items-start gap-2">
            {onBack ? (
              <button
                type="button"
                aria-label="Back to concept details"
                onClick={onBack}
                className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full border border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-950"
              >
                <ArrowLeft className="size-3.5" aria-hidden="true" />
              </button>
            ) : null}
            <div className="min-w-0 flex-1">
              {embeddedInConceptPanel ? (
                <>
                  <div className="flex min-w-0 items-center gap-2">
                    <h2 className="truncate text-base font-semibold text-slate-950">
                      {concept.title}
                    </h2>
                    <ModeBadge mode={mode} />
                  </div>
                  <div className="mt-0.5 flex min-w-0 items-center gap-2 text-xs text-slate-500">
                    <span className="truncate">
                      {titleCase(concept.concept_level)} ·{" "}
                      {titleCase(concept.node_type)}
                    </span>
                    <span className="shrink-0 text-[11px] font-semibold uppercase tracking-wide text-blue-700">
                      Tutor workspace
                    </span>
                  </div>
                </>
              ) : (
                <div className="flex min-w-0 items-center gap-2">
                  <h2 className="text-[11px] font-semibold uppercase tracking-wide text-blue-700 truncate">
                    Tutor workspace
                  </h2>
                  <ModeBadge mode={mode} />
                </div>
              )}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            {embeddedInConceptPanel && onToggleBookmark ? (
              <button
                type="button"
                aria-label={bookmarked ? "Remove bookmark" : "Bookmark concept"}
                aria-pressed={bookmarked}
                onClick={onToggleBookmark}
                className={`grid size-7 place-items-center rounded-md border text-slate-600 hover:bg-slate-50 ${
                  bookmarked
                    ? "border-blue-200 bg-blue-50 text-blue-700"
                    : "border-slate-200"
                }`}
              >
                <Bookmark
                  className="size-3.5"
                  aria-hidden
                  fill={bookmarked ? "currentColor" : "none"}
                />
              </button>
            ) : null}
            {embeddedInConceptPanel && onPanelClose ? (
              <button
                type="button"
                aria-label="Close"
                onClick={onPanelClose}
                className="grid size-7 place-items-center rounded-md border border-slate-200 text-slate-600 hover:bg-slate-50"
              >
                <X className="size-3.5" aria-hidden="true" />
              </button>
            ) : null}
          </div>
        </div>
        <div className="mt-2 flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center">
          {onActiveTabChange ? (
            <TutorPanelTabs
              activeTab={activeTab}
              onChange={onActiveTabChange}
            />
          ) : null}
          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2 sm:flex-nowrap">
            <span className="shrink-0 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
              Threads
            </span>
            {threads.length > 0 ? (
              <ThreadSwitcher
                threads={threads}
                selectedThreadId={selectedThreadId}
                onSelectThread={onSelectThread}
                onRenameThread={onRenameThread}
                onDeleteThread={onDeleteThread}
              />
            ) : (
              <p className="min-w-0 flex-1 truncate text-xs text-slate-500">
                Start a conversation for this concept.
              </p>
            )}
            <div className="flex shrink-0 items-center gap-1 sm:ml-auto">
              {onCreateThread ? (
                <button
                  type="button"
                  aria-label="New thread"
                  title="New thread"
                  onClick={() => {
                    if (!onCreateThread || creatingThread) return;
                    setCreatingThread(true);
                    void onCreateThread().finally(() => {
                      setCreatingThread(false);
                    });
                  }}
                  disabled={creatingThread}
                  className="grid size-7 place-items-center rounded-full border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 hover:text-slate-950 disabled:opacity-50"
                >
                  <PlusIcon className="size-3.5" aria-hidden="true" />
                </button>
              ) : null}
              <div ref={menuContainerRef} className="relative">
                <button
                  type="button"
                  aria-label="Conversation settings"
                  aria-expanded={menuOpen}
                  onClick={() => setMenuOpen((open) => !open)}
                  className="grid size-7 place-items-center rounded-full border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 hover:text-slate-950"
                >
                  <MoreHorizontalIcon className="size-3.5" />
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
                        <ContextBadge icon={LayersIcon}>
                          Level: {titleCase(concept.concept_level)}
                        </ContextBadge>
                        <ContextBadge icon={TargetIcon}>
                          Bloom: {formatBloomLevel(concept.bloom_level)}
                        </ContextBadge>
                        <ContextBadge icon={GaugeIcon}>
                          Difficulty: {titleCase(concept.difficulty)}
                        </ContextBadge>
                      </div>
                      <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                        <LinkIcon className="size-3 shrink-0" />
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
      </div>
      {children}
    </section>
  );
}

function TutorPanelTabs({
  activeTab,
  onChange,
}: {
  activeTab: TutorPanelTab;
  onChange: (tab: TutorPanelTab) => void;
}) {
  const tabs: Array<{ value: TutorPanelTab; label: string }> = [
    { value: "tutor", label: "Tutor" },
    { value: "notes", label: "Notes" },
  ];

  return (
    <div
      role="tablist"
      aria-label="Tutor panel sections"
      className="flex w-full shrink-0 rounded-full border border-slate-200 bg-slate-50 p-1 sm:inline-flex sm:w-auto"
    >
      {tabs.map((tab) => (
        <button
          key={tab.value}
          type="button"
          role="tab"
          aria-selected={activeTab === tab.value}
          onClick={() => onChange(tab.value)}
          className={`h-8 flex-1 rounded-full px-3 text-xs font-semibold transition sm:flex-none ${
            activeTab === tab.value
              ? "bg-blue-600 text-white shadow-sm shadow-blue-200"
              : "text-slate-600 hover:bg-white hover:text-slate-950"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

function NotesPanel({
  workspaceId,
  trailId,
  concept,
}: {
  workspaceId: string;
  trailId: string;
  concept: ConceptNode;
}) {
  const [loadKey, setLoadKey] = useState(0);
  const [notes, setNotes] = useState<Note[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">(
    "loading",
  );
  const [loadError, setLoadError] = useState("");
  const [draftTitle, setDraftTitle] = useState("");
  const [draftBody, setDraftBody] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadNotes() {
      setStatus("loading");
      setLoadError("");
      try {
        const nextNotes = await listNotes(workspaceId, trailId, concept.id);
        if (!cancelled) {
          setNotes(sortNotesNewestFirst(nextNotes));
          setStatus("ready");
        }
      } catch (exc) {
        if (!cancelled) {
          setStatus("error");
          setLoadError(
            exc instanceof Error ? exc.message : "Could not load notes",
          );
        }
      }
    }

    void loadNotes();
    return () => {
      cancelled = true;
    };
  }, [workspaceId, trailId, concept.id, loadKey]);

  const createNewNote = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const body = draftBody.trim();
    const title = draftTitle.trim();
    if (!body || saving) {
      return;
    }

    setSaving(true);
    setSaveError("");
    try {
      const note = await createNote(workspaceId, trailId, {
        title: title || null,
        body,
        concept_id: concept.id,
      });
      setNotes((current) => sortNotesNewestFirst([note, ...current]));
      setDraftTitle("");
      setDraftBody("");
    } catch (exc) {
      setSaveError(exc instanceof Error ? exc.message : "Could not save note");
    } finally {
      setSaving(false);
    }
  };

  const updateExistingNote = async (
    noteId: string,
    next: { title: string | null; body: string },
  ) => {
    const note = await updateNote(workspaceId, trailId, noteId, next);
    setNotes((current) =>
      sortNotesNewestFirst(
        current.map((candidate) =>
          candidate.id === note.id ? note : candidate,
        ),
      ),
    );
  };

  const deleteExistingNote = async (noteId: string) => {
    await deleteNote(workspaceId, trailId, noteId);
    setNotes((current) => current.filter((note) => note.id !== noteId));
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-linear-to-b from-white to-slate-50/80">
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
          <section className="rounded-3xl border border-blue-100 bg-blue-50/60 p-3 shadow-sm shadow-blue-100/50">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-950">
                  Notes for {concept.title}
                </h3>
                <p className="mt-0.5 text-xs text-slate-600">
                  Capture takeaways while the tutor conversation stays open.
                </p>
              </div>
              <span className="rounded-full border border-blue-200 bg-white px-2 py-0.5 text-[11px] font-semibold text-blue-700">
                {notes.length} note{notes.length === 1 ? "" : "s"}
              </span>
            </div>
            <form onSubmit={createNewNote} className="mt-3 grid gap-2">
              <input
                type="text"
                aria-label="Note title"
                value={draftTitle}
                onChange={(event) => setDraftTitle(event.target.value)}
                placeholder="Optional title"
                className="h-9 rounded-2xl border border-blue-100 bg-white px-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
              />
              <textarea
                aria-label="Note body"
                value={draftBody}
                onChange={(event) => setDraftBody(event.target.value)}
                placeholder="Write a note, summary, question, or next step..."
                className="min-h-28 resize-y rounded-2xl border border-blue-100 bg-white px-3 py-2 text-sm leading-6 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
              />
              {saveError ? (
                <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                  {saveError}
                </div>
              ) : null}
              <div className="flex items-center justify-between gap-3">
                <span className="text-xs text-slate-500">
                  Saved to this Trail and concept.
                </span>
                <button
                  type="submit"
                  disabled={!draftBody.trim() || saving}
                  className="rounded-full bg-blue-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-slate-300"
                >
                  {saving ? "Saving..." : "Save note"}
                </button>
              </div>
            </form>
          </section>

          {status === "loading" ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-500">
              Loading notes...
            </div>
          ) : null}

          {status === "error" ? (
            <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              <div>{loadError || "Notes unavailable"}</div>
              <button
                type="button"
                onClick={() => setLoadKey((current) => current + 1)}
                className="mt-3 rounded-full border border-red-200 bg-white px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-50"
              >
                Retry notes
              </button>
            </div>
          ) : null}

          {status === "ready" && notes.length === 0 ? (
            <div className="rounded-3xl border border-dashed border-slate-300 bg-white/80 p-5 text-center shadow-sm">
              <div className="text-sm font-semibold text-slate-900">
                No notes yet
              </div>
              <p className="mt-1 text-sm text-slate-500">
                Save one key insight, misconception, or follow-up question from
                this tutor session.
              </p>
            </div>
          ) : null}

          {status === "ready" && notes.length > 0 ? (
            <div className="grid gap-3">
              {notes.map((note) => (
                <NoteCard
                  key={note.id}
                  note={note}
                  onUpdate={updateExistingNote}
                  onDelete={deleteExistingNote}
                />
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function NoteCard({
  note,
  onUpdate,
  onDelete,
}: {
  note: Note;
  onUpdate: (
    noteId: string,
    next: { title: string | null; body: string },
  ) => Promise<void>;
  onDelete: (noteId: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(note.title ?? "");
  const [body, setBody] = useState(note.body);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submitUpdate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextBody = body.trim();
    if (!nextBody || busy) {
      return;
    }

    setBusy(true);
    setError("");
    try {
      await onUpdate(note.id, {
        title: title.trim() || null,
        body: nextBody,
      });
      setEditing(false);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Could not update note");
    } finally {
      setBusy(false);
    }
  };

  const deleteNoteCard = async () => {
    if (busy) {
      return;
    }
    setBusy(true);
    setError("");
    try {
      await onDelete(note.id);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Could not delete note");
      setBusy(false);
    }
  };

  if (editing) {
    return (
      <form
        onSubmit={submitUpdate}
        className="rounded-3xl border border-blue-100 bg-white p-3 shadow-sm"
      >
        <input
          type="text"
          aria-label="Edit note title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Optional title"
          className="h-9 w-full rounded-2xl border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
        />
        <textarea
          aria-label="Edit note body"
          value={body}
          onChange={(event) => setBody(event.target.value)}
          className="mt-2 min-h-32 w-full resize-y rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm leading-6 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
        />
        {error ? (
          <div className="mt-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {error}
          </div>
        ) : null}
        <div className="mt-3 flex items-center justify-between gap-2">
          <span className="text-xs text-slate-500">
            Updated {formatNoteTimestamp(note.updated_at)}
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setTitle(note.title ?? "");
                setBody(note.body);
                setError("");
                setEditing(false);
              }}
              disabled={busy}
              className="rounded-full border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!body.trim() || busy}
              className="rounded-full bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {busy ? "Saving..." : "Save"}
            </button>
          </div>
        </div>
      </form>
    );
  }

  return (
    <article className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-slate-950">
            {noteDisplayTitle(note)}
          </h3>
          <p className="mt-0.5 text-xs text-slate-500">
            Updated {formatNoteTimestamp(note.updated_at)}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            onClick={() => {
              setTitle(note.title ?? "");
              setBody(note.body);
              setError("");
              setEditing(true);
            }}
            className="rounded-full border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50"
          >
            Edit
          </button>
          <button
            type="button"
            onClick={deleteNoteCard}
            disabled={busy}
            className="rounded-full border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50"
          >
            {busy ? "Deleting..." : "Delete"}
          </button>
        </div>
      </div>
      <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-700">
        {note.body}
      </p>
      {error ? (
        <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </div>
      ) : null}
    </article>
  );
}

function sortNotesNewestFirst(notes: Note[]): Note[] {
  return [...notes].sort(
    (left, right) => noteTimestamp(right) - noteTimestamp(left),
  );
}

function noteTimestamp(note: Note): number {
  const timestamp = Date.parse(note.updated_at || note.created_at);
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function noteDisplayTitle(note: Note): string {
  const explicit = note.title?.trim();
  if (explicit) {
    return explicit;
  }
  const firstLine = note.body
    .split("\n")
    .map((line) => line.trim())
    .find(Boolean);
  return firstLine || `Note from ${formatNoteTimestamp(note.created_at)}`;
}

function formatNoteTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "recently";
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function TutorThread({
  reasoningView,
  sampleQuestions,
}: {
  reasoningView: ReasoningView;
  sampleQuestions?: string[];
}) {
  const messageCount = useThread((state) => state.messages.length);
  const isRunning = useThread((state) => state.isRunning);
  const latestUserMessageId = useThread(
    (state) =>
      [...state.messages].reverse().find((message) => message.role === "user")
        ?.id ?? null,
  );

  return (
    <ThreadPrimitive.Root className="flex min-h-0 flex-1 flex-col bg-linear-to-b from-white to-slate-50/80">
      <ThreadPrimitive.Viewport
        autoScroll
        scrollToBottomOnRunStart
        scrollToBottomOnInitialize
        data-testid="tutor-thread-viewport"
        className="relative flex min-h-0 flex-1 touch-pan-y flex-col overflow-y-auto overscroll-y-contain px-4 pb-4 pt-5 [-webkit-overflow-scrolling:touch]"
      >
        {messageCount === 0 ? (
          <WelcomeSuggestions sampleQuestions={sampleQuestions} />
        ) : null}
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
        <ThreadPrimitive.ScrollToBottom className="sticky bottom-4 z-10 ml-auto mt-3 grid size-9 place-items-center rounded-full border border-slate-200 bg-white text-slate-500 shadow-sm transition hover:bg-slate-50 disabled:hidden">
          <ArrowDownIcon className="size-4" />
        </ThreadPrimitive.ScrollToBottom>
      </ThreadPrimitive.Viewport>
      {/* Chatbox is outside the scroll container so messages can never bleed below it */}
      <div className="shrink-0 border-t border-slate-200 bg-white px-4 pb-[calc(env(safe-area-inset-bottom)+0.75rem)] pt-3 md:pb-3">
        <ComposerPrimitive.Root className="flex items-end gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 shadow-sm">
          <ComposerPrimitive.Input
            aria-label="Message tutor"
            placeholder="Ask for a hint, test an idea, or explain your thinking..."
            submitMode="enter"
            className="max-h-36 min-h-[2.75rem] flex-1 resize-none bg-transparent text-sm leading-6 text-slate-900 outline-none placeholder:text-slate-400 disabled:text-slate-400"
          />
          {isRunning ? (
            <ComposerPrimitive.Cancel className="mb-0.5 h-9 shrink-0 rounded-full border border-slate-200 px-3 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40">
              Stop
            </ComposerPrimitive.Cancel>
          ) : (
            <ComposerPrimitive.Send
              aria-label="Send"
              className="mb-0.5 grid size-9 shrink-0 place-items-center rounded-full bg-slate-950 text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              <ArrowUpIcon className="size-4" />
            </ComposerPrimitive.Send>
          )}
        </ComposerPrimitive.Root>
      </div>
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

// Whether the surrounding chain-of-thought group is still streaming. Used by
// full-view reasoning lines so only live steps pulse and completed steps stay
// static (Bug 1). Defaults to false so any standalone render settles quietly.
const ReasoningRunningContext = createContext(false);

// Click handler that opens the suggested quiz. Null when the host panel does
// not wire quiz opening (e.g. standalone previews). The CTA card stays click-
// only and never auto-opens.
const SuggestQuizContext = createContext<
  ((quizType: "level_up" | "practice") => void) | null
>(null);

const SuggestFlashcardsContext = createContext<(() => void) | null>(null);

// Click handler that opens the artifacts panel and starts the suggested build.
// Null when the host panel does not wire artifact opening (e.g. standalone
// previews). The CTA card stays click-only and never auto-opens.
const SuggestArtifactContext = createContext<
  ((kind: ArtifactKind) => void) | null
>(null);

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
          // The reasoning indicator should only pulse while the tutor is still
          // reasoning. Once a visible answer has started (or the run settles to
          // a non-running status) the chain-of-thought is done, so stop the
          // "streaming" dot instead of letting it flash forever (Bug 1).
          const running =
            part.status.type === "running" && !hasVisibleAnswer(message);
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
                  // Tell the per-line status dots whether the chain-of-thought is
                  // still streaming so completed steps render a static dot
                  // instead of pulsing forever (Bug 1).
                  <ReasoningRunningContext.Provider value={running}>
                    <div className="grid gap-3">{children}</div>
                  </ReasoningRunningContext.Provider>
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
        if (part.type === "data" && part.name === "tutor-suggest-quiz") {
          const data = part.data as {
            quizType?: "level_up" | "practice";
            reason?: string;
          };
          if (data.quizType !== "level_up" && data.quizType !== "practice") {
            return null;
          }
          return (
            <SuggestQuizCard
              messageId={message.id}
              quizType={data.quizType}
              reason={data.reason ?? ""}
              isLatestInMessage={
                latestSuggestQuizPart(message, data.quizType) === part
              }
            />
          );
        }
        if (part.type === "data" && part.name === "tutor-suggest-flashcards") {
          const data = part.data as { reason?: string };
          return (
            <SuggestFlashcardsCard
              messageId={message.id}
              reason={data.reason ?? ""}
              isLatestInMessage={latestSuggestFlashcardsPart(message) === part}
            />
          );
        }
        if (part.type === "data" && part.name === "tutor-suggest-artifact") {
          const data = part.data as {
            artifactKind?: ArtifactKind;
            reason?: string;
          };
          if (!isArtifactKind(data.artifactKind)) {
            return null;
          }
          return (
            <SuggestArtifactCard
              messageId={message.id}
              artifactKind={data.artifactKind}
              reason={data.reason ?? ""}
              isLatestInMessage={
                latestSuggestArtifactPart(message, data.artifactKind) === part
              }
            />
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

function SuggestQuizCard({
  messageId,
  quizType,
  reason,
  isLatestInMessage,
}: {
  messageId: string;
  quizType: "level_up" | "practice";
  reason: string;
  isLatestInMessage: boolean;
}) {
  const onSuggestQuiz = useContext(SuggestQuizContext);
  // Collapse to a single active CTA per quiz_type across the whole thread: only
  // the most recent suggestion of this type stays clickable, so re-suggesting
  // never leaves a stale competing button behind.
  const latestMessageId = useThread((state) => {
    let latest: string | null = null;
    for (const candidate of state.messages) {
      const matches = candidate.content.some(
        (entry) =>
          entry.type === "data" &&
          entry.name === "tutor-suggest-quiz" &&
          (entry.data as { quizType?: string }).quizType === quizType,
      );
      if (matches) {
        latest = candidate.id;
      }
    }
    return latest;
  });

  if (!onSuggestQuiz || !isLatestInMessage) {
    return null;
  }
  if (latestMessageId && latestMessageId !== messageId) {
    return null;
  }

  const label =
    quizType === "level_up" ? "Take level-up quiz" : "Practice this";

  return (
    <div className="mt-3 grid gap-2 rounded-2xl border border-emerald-200 bg-emerald-50/70 p-3 dark:border-emerald-900/60 dark:bg-emerald-950/30">
      {reason ? (
        <p className="min-w-0 wrap-break-word text-sm text-emerald-900 dark:text-emerald-100">
          {reason}
        </p>
      ) : null}
      <button
        type="button"
        onClick={() => onSuggestQuiz(quizType)}
        className="justify-self-start rounded-full bg-emerald-600 px-4 py-1.5 text-xs font-semibold text-white transition hover:bg-emerald-500"
      >
        {label}
      </button>
    </div>
  );
}

function latestSuggestQuizPart(
  message: MessageState,
  quizType: "level_up" | "practice",
): MessageState["content"][number] | null {
  let latest: MessageState["content"][number] | null = null;
  for (const part of message.content) {
    if (
      part.type === "data" &&
      part.name === "tutor-suggest-quiz" &&
      (part.data as { quizType?: string }).quizType === quizType
    ) {
      latest = part;
    }
  }
  return latest;
}

function SuggestFlashcardsCard({
  messageId,
  reason,
  isLatestInMessage,
}: {
  messageId: string;
  reason: string;
  isLatestInMessage: boolean;
}) {
  const onSuggestFlashcards = useContext(SuggestFlashcardsContext);
  const latestMessageId = useThread((state) => {
    let latest: string | null = null;
    for (const candidate of state.messages) {
      const matches = candidate.content.some(
        (entry) =>
          entry.type === "data" && entry.name === "tutor-suggest-flashcards",
      );
      if (matches) {
        latest = candidate.id;
      }
    }
    return latest;
  });

  if (!onSuggestFlashcards || !isLatestInMessage) {
    return null;
  }
  if (latestMessageId && latestMessageId !== messageId) {
    return null;
  }

  return (
    <div className="mt-3 grid gap-2 rounded-2xl border border-violet-200 bg-violet-50/70 p-3 dark:border-violet-900/60 dark:bg-violet-950/30">
      {reason ? (
        <p className="min-w-0 wrap-break-word text-sm text-violet-900 dark:text-violet-100">
          {reason}
        </p>
      ) : null}
      <button
        type="button"
        onClick={onSuggestFlashcards}
        className="justify-self-start rounded-full bg-violet-600 px-4 py-1.5 text-xs font-semibold text-white transition hover:bg-violet-500"
      >
        Generate flashcards
      </button>
    </div>
  );
}

function latestSuggestFlashcardsPart(
  message: MessageState,
): MessageState["content"][number] | null {
  let latest: MessageState["content"][number] | null = null;
  for (const part of message.content) {
    if (part.type === "data" && part.name === "tutor-suggest-flashcards") {
      latest = part;
    }
  }
  return latest;
}

const ARTIFACT_KIND_LABELS: Record<ArtifactKind, string> = {
  worked_example: "Build worked example",
  comparison_card: "Build comparison",
  timeline: "Build timeline",
  mini_graph: "Build mini graph",
  simulation_slider: "Build simulation",
};

function isArtifactKind(value: unknown): value is ArtifactKind {
  return (
    typeof value === "string" &&
    Object.prototype.hasOwnProperty.call(ARTIFACT_KIND_LABELS, value)
  );
}

function SuggestArtifactCard({
  messageId,
  artifactKind,
  reason,
  isLatestInMessage,
}: {
  messageId: string;
  artifactKind: ArtifactKind;
  reason: string;
  isLatestInMessage: boolean;
}) {
  const onSuggestArtifact = useContext(SuggestArtifactContext);
  // Collapse to a single active CTA per artifact kind across the whole thread:
  // only the most recent suggestion of this kind stays clickable, so
  // re-suggesting never leaves a stale competing button behind.
  const latestMessageId = useThread((state) => {
    let latest: string | null = null;
    for (const candidate of state.messages) {
      const matches = candidate.content.some(
        (entry) =>
          entry.type === "data" &&
          entry.name === "tutor-suggest-artifact" &&
          (entry.data as { artifactKind?: string }).artifactKind ===
            artifactKind,
      );
      if (matches) {
        latest = candidate.id;
      }
    }
    return latest;
  });

  if (!onSuggestArtifact || !isLatestInMessage) {
    return null;
  }
  if (latestMessageId && latestMessageId !== messageId) {
    return null;
  }

  const label = ARTIFACT_KIND_LABELS[artifactKind];

  return (
    <div className="mt-3 grid gap-2 rounded-2xl border border-sky-200 bg-sky-50/70 p-3 dark:border-sky-900/60 dark:bg-sky-950/30">
      {reason ? (
        <p className="min-w-0 wrap-break-word text-sm text-sky-900 dark:text-sky-100">
          {reason}
        </p>
      ) : null}
      <button
        type="button"
        onClick={() => onSuggestArtifact(artifactKind)}
        className="justify-self-start rounded-full bg-sky-600 px-4 py-1.5 text-xs font-semibold text-white transition hover:bg-sky-500"
      >
        {label}
      </button>
    </div>
  );
}

function latestSuggestArtifactPart(
  message: MessageState,
  artifactKind: ArtifactKind,
): MessageState["content"][number] | null {
  let latest: MessageState["content"][number] | null = null;
  for (const part of message.content) {
    if (
      part.type === "data" &&
      part.name === "tutor-suggest-artifact" &&
      (part.data as { artifactKind?: string }).artifactKind === artifactKind
    ) {
      latest = part;
    }
  }
  return latest;
}

function UserMessageBody({ message }: { message: MessageState }) {
  if (!messageText(message).trim()) {
    return null;
  }

  return <UserMarkdownText text={messageText(message)} />;
}

function WelcomeSuggestions({
  sampleQuestions,
}: {
  sampleQuestions?: string[];
}) {
  const fallback = [
    "Give me one hint to get started.",
    "Ask me a Socratic question about this concept.",
    "Check whether my current understanding is right.",
  ];
  const suggestions =
    sampleQuestions && sampleQuestions.length > 0 ? sampleQuestions : fallback;

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

function ThreadSwitcher({
  threads,
  selectedThreadId,
  onSelectThread,
  onRenameThread,
  onDeleteThread,
}: {
  threads: ConversationThreadSummary[];
  selectedThreadId: string | null;
  onSelectThread?: (threadId: string) => void;
  onRenameThread?: (threadId: string, title: string) => Promise<void>;
  onDeleteThread?: (threadId: string) => Promise<void>;
}) {
  const [menuThreadId, setMenuThreadId] = useState<string | null>(null);
  const [menuPosition, setMenuPosition] = useState<{
    top: number;
    left: number;
  } | null>(null);
  const [actionError, setActionError] = useState("");
  const [busyThreadId, setBusyThreadId] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!menuThreadId) return;

    function handlePointerDown(event: PointerEvent) {
      const target = event.target as Node;
      const button =
        target instanceof Element
          ? target.closest(`[data-thread-menu-button="${menuThreadId}"]`)
          : null;
      if (menuRef.current?.contains(target) || button) {
        return;
      }
      setMenuThreadId(null);
      setMenuPosition(null);
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMenuThreadId(null);
        setMenuPosition(null);
      }
    }

    function handleViewportChange() {
      setMenuThreadId(null);
      setMenuPosition(null);
    }

    document.addEventListener("pointerdown", handlePointerDown);
    window.addEventListener("keydown", handleEscape);
    window.addEventListener("resize", handleViewportChange);
    window.addEventListener("scroll", handleViewportChange, true);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      window.removeEventListener("keydown", handleEscape);
      window.removeEventListener("resize", handleViewportChange);
      window.removeEventListener("scroll", handleViewportChange, true);
    };
  }, [menuThreadId]);

  async function handleRename(thread: ConversationThreadSummary) {
    if (!onRenameThread || busyThreadId) return;
    const nextTitle = window.prompt("Rename thread", thread.title);
    setMenuThreadId(null);
    setMenuPosition(null);
    if (nextTitle === null) return;
    const title = nextTitle.trim();
    if (!title) {
      setActionError("Thread title cannot be blank.");
      return;
    }
    setBusyThreadId(thread.id);
    setActionError("");
    try {
      await onRenameThread(thread.id, title);
    } catch (exc) {
      setActionError(
        exc instanceof Error ? exc.message : "Could not rename thread",
      );
    } finally {
      setBusyThreadId(null);
    }
  }

  async function handleDelete(thread: ConversationThreadSummary) {
    if (!onDeleteThread || busyThreadId) return;
    const confirmed = window.confirm(`Delete thread \"${thread.title}\"?`);
    setMenuThreadId(null);
    setMenuPosition(null);
    if (!confirmed) return;
    setBusyThreadId(thread.id);
    setActionError("");
    try {
      await onDeleteThread(thread.id);
    } catch (exc) {
      setActionError(
        exc instanceof Error ? exc.message : "Could not delete thread",
      );
    } finally {
      setBusyThreadId(null);
    }
  }

  const activeThread =
    threads.find((thread) => thread.id === menuThreadId) ?? null;

  return (
    <div className="min-w-0 flex-1">
      <div
        role="group"
        aria-label="Conversation threads"
        className="no-scrollbar flex min-w-0 gap-1 overflow-x-auto"
      >
        {threads.map((thread) => {
          const selected = selectedThreadId === thread.id;
          const menuOpen = menuThreadId === thread.id;
          return (
            <div
              key={thread.id}
              className={`relative inline-flex h-8 max-w-56 shrink-0 items-center rounded-lg border text-xs font-medium transition ${
                selected
                  ? "border-blue-200 bg-blue-50 text-blue-800 shadow-sm"
                  : "border-slate-200 bg-slate-50 text-slate-700 hover:bg-white"
              }`}
            >
              <button
                type="button"
                title={thread.preview ?? thread.title}
                aria-pressed={selected}
                onClick={() => onSelectThread?.(thread.id)}
                className="min-w-0 flex-1 truncate px-3 text-left"
              >
                <span className="truncate">{thread.title}</span>
              </button>
              {onRenameThread || onDeleteThread ? (
                <button
                  type="button"
                  data-thread-menu-button={thread.id}
                  aria-label={`Thread actions for ${thread.title}`}
                  aria-expanded={menuOpen}
                  disabled={busyThreadId === thread.id}
                  onClick={(event) => {
                    if (menuOpen) {
                      setMenuThreadId(null);
                      setMenuPosition(null);
                      return;
                    }
                    const rect = event.currentTarget.getBoundingClientRect();
                    setMenuThreadId(thread.id);
                    setMenuPosition({
                      top: rect.bottom + 4,
                      left: Math.max(
                        8,
                        Math.min(rect.left, window.innerWidth - 144),
                      ),
                    });
                  }}
                  className="mr-1 grid size-6 shrink-0 place-items-center rounded-md text-slate-500 hover:bg-white hover:text-slate-900 disabled:opacity-50"
                >
                  <MoreHorizontalIcon className="size-3" aria-hidden="true" />
                </button>
              ) : null}
            </div>
          );
        })}
      </div>
      {activeThread && menuPosition
        ? createPortal(
            <div
              ref={menuRef}
              className="fixed z-[9999] grid min-w-32 gap-1 rounded-xl border border-slate-200 bg-white p-1.5 text-xs text-slate-700 shadow-xl ring-1 ring-slate-950/5"
              style={{ top: menuPosition.top, left: menuPosition.left }}
            >
              {onRenameThread ? (
                <button
                  type="button"
                  onClick={() => void handleRename(activeThread)}
                  className="rounded-lg px-2 py-1.5 text-left hover:bg-slate-50"
                >
                  Rename
                </button>
              ) : null}
              {onDeleteThread ? (
                <button
                  type="button"
                  onClick={() => void handleDelete(activeThread)}
                  className="rounded-lg px-2 py-1.5 text-left text-red-600 hover:bg-red-50"
                >
                  Delete
                </button>
              ) : null}
            </div>,
            document.body,
          )
        : null}
      {actionError ? (
        <p className="mt-1 text-xs text-red-600">{actionError}</p>
      ) : null}
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
      className="inline-flex h-8 w-full items-center justify-center rounded-full border border-slate-200 bg-slate-50 px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
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

  if (steps.length === 0) {
    // Before any concrete thinking/tool step exists, surface the latest live
    // status (e.g. "Thinking", "Calling tool") so the summary view shows real
    // progress while the tutor reasons instead of a frozen placeholder (Bug 2).
    const status = latestReasoningStatus(message);
    const label = running
      ? status
        ? formatStreamStatus(status)
        : "Choosing a focused question..."
      : "Reasoning trace available.";
    return (
      <div className="flex items-center gap-1.5 text-sm text-slate-500 dark:text-slate-400">
        {running ? (
          <span className="size-1.5 animate-pulse rounded-full bg-blue-500" />
        ) : null}
        <span>{label}</span>
      </div>
    );
  }

  return (
    <ol className="grid gap-3">
      {steps.map((step, index) => {
        const isActive = running && index === steps.length - 1;
        return (
          <li key={`${step.label}-${index}`} className="grid gap-0.5">
            <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              {isActive ? (
                <span className="size-1.5 animate-pulse rounded-full bg-blue-500" />
              ) : null}
              <span>{step.label}</span>
            </div>
            {step.detail ? (
              <div className="text-sm text-slate-600 dark:text-slate-300">
                {step.detail}
              </div>
            ) : null}
          </li>
        );
      })}
    </ol>
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
    <span className="rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-[11px] font-semibold text-blue-800 sm:text-xs">
      {mode ? titleCase(mode) : "waiting"}
    </span>
  );
}

function ContextBadge({
  icon: Icon,
  children,
}: {
  icon?: LucideIcon;
  children: ReactNode;
}) {
  return (
    <span className="inline-flex items-center gap-1 rounded border border-slate-200 bg-slate-50 px-2 py-1 font-medium text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200">
      {Icon ? (
        <Icon className="size-3 shrink-0 text-slate-400 dark:text-slate-500" />
      ) : null}
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

function hasVisibleAnswer(message: MessageState): boolean {
  return message.content.some(
    (part) => part.type === "text" && part.text.trim().length > 0,
  );
}

function latestReasoningStatus(
  message: MessageState,
): TutorStreamStatus | null {
  let status: TutorStreamStatus | null = null;
  for (const part of message.content) {
    if (isTutorDataPart(part, "tutor-status")) {
      const next = (part.data as { status?: TutorStreamStatus }).status;
      if (next) {
        status = next;
      }
    }
  }
  return status;
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
  if (tool.name === "get_concept_primer") {
    return "Checking primer";
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
  const running = useContext(ReasoningRunningContext);
  if (!status) {
    return null;
  }

  return (
    <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
      <span
        className={`size-1.5 rounded-full bg-blue-500${
          running ? " animate-pulse" : ""
        }`}
      />
      {formatStreamStatus(status)}
    </div>
  );
}

function TutorThinkingLine({ text }: { text: string }) {
  if (!text.trim()) {
    return null;
  }

  return (
    <div className="grid gap-0.5">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        Thinking
      </div>
      <ReasoningText>
        <div className="italic text-slate-600 dark:text-slate-300">{text}</div>
      </ReasoningText>
    </div>
  );
}

function TutorToolCallLine({ tool }: { tool: TutorToolEvent }) {
  return (
    <div className="grid gap-0.5">
      <div className="flex items-center justify-between gap-3">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          {toolSummaryLabel(tool)}
        </span>
        {tool.mode ? (
          <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-600 dark:bg-slate-800 dark:text-slate-300">
            {tool.mode}
          </span>
        ) : null}
      </div>
      {tool.query ? (
        <div className="text-sm text-slate-600 dark:text-slate-300">
          {tool.query}
        </div>
      ) : null}
    </div>
  );
}

function TutorToolResultLine({ tool }: { tool: TutorToolEvent }) {
  return (
    <div className="grid gap-0.5">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {formatToolName(tool.name)} result
      </div>
      {tool.result ? (
        <pre className="max-h-44 overflow-y-auto whitespace-pre-wrap border-l border-slate-200 pl-3 text-xs leading-5 text-slate-500 dark:border-slate-700 dark:text-slate-400">
          {tool.result}
        </pre>
      ) : null}
    </div>
  );
}

function formatStreamStatus(status: TutorStreamStatus): string {
  switch (status) {
    case "selecting_mode":
      return "Choosing answering mode";
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
