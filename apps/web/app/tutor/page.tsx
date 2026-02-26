"use client";

import { FormEvent, useEffect, useMemo, useReducer, useState } from "react";

import { ChatResponse } from "@/components/chat-response";
import { ConceptGraph } from "@/components/concept-graph";
import { LevelUpCard } from "@/components/level-up-card";
import { MarkdownContent } from "@/components/markdown-content";
import { ApiError, apiClient } from "@/lib/api/client";
import type {
  AssistantResponseEnvelope,
  ChatMessageRecord,
  ChatSessionSummary,
  ConceptSwitchSuggestion,
  GraphConceptSummary,
  GraphSubgraphResponse,
  GroundingMode,
} from "@/lib/api/types";
import {
  initialLevelUpState,
  levelUpReducer,
  toSubmitAnswers,
} from "@/lib/tutor/level-up-state";

type TimelineMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  text: string;
  response?: AssistantResponseEnvelope;
};

const asPositiveInt = (value: string) => {
  const num = Number(value);
  return Number.isInteger(num) && num > 0 ? num : undefined;
};

function toTitleCase(str: string): string {
  return str.replace(/\w\S*/g, (txt) => txt.charAt(0).toUpperCase() + txt.substring(1).toLowerCase());
}

function errorText(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}

function mapMessage(record: ChatMessageRecord): TimelineMessage {
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
  if (record.type === "assistant") {
    return { id: String(record.message_id), role: "assistant", text };
  }
  if (record.type === "user") {
    return { id: String(record.message_id), role: "user", text };
  }
  return { id: String(record.message_id), role: "system", text };
}

function masteryLabel(status: string | null, score: number | null): string {
  if (!status) {
    return "unseen";
  }
  if (typeof score === "number") {
    return `${status} (${Math.round(score * 100)}%)`;
  }
  return status;
}

export default function TutorPage() {
  const [workspace_id, setWorkspace] = useState("1");
  const [user_id, setUser] = useState("1");
  const [grounding_mode, setGroundingMode] = useState<GroundingMode>("hybrid");
  const [query, setQuery] = useState("");

  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [sessionsError, setSessionsError] = useState<string | null>(null);

  const [messages, setMessages] = useState<TimelineMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);

  const [showGraph, setShowGraph] = useState(false);
  const [showQuiz, setShowQuiz] = useState(false);
  const [concepts, setConcepts] = useState<GraphConceptSummary[]>([]);
  const [conceptsLoading, setConceptsLoading] = useState(false);
  const [conceptsError, setConceptsError] = useState<string | null>(null);
  const [currentConcept, setCurrentConcept] = useState<GraphConceptSummary | null>(null);
  const [subgraph, setSubgraph] = useState<GraphSubgraphResponse | null>(null);

  const [suggestedConceptId, setSuggestedConceptId] = useState<number | null>(null);
  const [switchSuggestion, setSwitchSuggestion] = useState<ConceptSwitchSuggestion | null>(null);
  const [switchDecision, setSwitchDecision] = useState<"accept" | "reject" | null>(null);

  const [levelUpState, dispatchLevelUp] = useReducer(levelUpReducer, initialLevelUpState);

  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Restore sidebar state from localStorage after hydration
  useEffect(() => {
    const stored = localStorage.getItem("colearni-sidebar");
    if (stored !== "closed") setSidebarOpen(true);
  }, []);
  const [contextMenuId, setContextMenuId] = useState<number | null>(null);
  const [contextMenuPos, setContextMenuPos] = useState<{ x: number; y: number; top?: boolean } | null>(null);
  const [renamingId, setRenamingId] = useState<number | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);

  const workspaceId = asPositiveInt(workspace_id);
  const userId = asPositiveInt(user_id);

  useEffect(() => {
    if (!workspaceId || !userId || !activeSessionId) return;
    const key = `colearni_levelup_${workspaceId}_${userId}_${activeSessionId}`;
    try {
      const saved = localStorage.getItem(key);
      if (saved) {
        dispatchLevelUp({ type: "restore", state: JSON.parse(saved) });
      } else {
        dispatchLevelUp({ type: "reset" });
      }
    } catch {
      dispatchLevelUp({ type: "reset" });
    }
  }, [workspaceId, userId, activeSessionId]);

  useEffect(() => {
    if (!workspaceId || !userId || !activeSessionId) return;
    const key = `colearni_levelup_${workspaceId}_${userId}_${activeSessionId}`;
    if (levelUpState.phase === "idle") {
      localStorage.removeItem(key);
    } else {
      localStorage.setItem(key, JSON.stringify(levelUpState));
    }
  }, [workspaceId, userId, activeSessionId, levelUpState]);

  async function ensureSession(): Promise<number | null> {
    if (!workspaceId || !userId) {
      return null;
    }
    if (activeSessionId) {
      return activeSessionId;
    }
    const created = await apiClient.createChatSession({ workspace_id: workspaceId, user_id: userId });
    setSessions((prev) => [created, ...prev]);
    setActiveSessionId(created.session_id);
    return created.session_id;
  }

  async function refreshSessions() {
    if (!workspaceId || !userId) {
      setSessions([]);
      setActiveSessionId(null);
      return;
    }
    setSessionsLoading(true);
    setSessionsError(null);
    try {
      const payload = await apiClient.listChatSessions({ workspace_id: workspaceId, user_id: userId, limit: 50 });
      let nextSessions = payload.sessions;
      if (!nextSessions.length) {
        const created = await apiClient.createChatSession({ workspace_id: workspaceId, user_id: userId });
        nextSessions = [created];
      }
      setSessions(nextSessions);
      setActiveSessionId((prev) => {
        if (prev && nextSessions.some((item) => item.session_id === prev)) {
          return prev;
        }
        return nextSessions[0]?.session_id ?? null;
      });
    } catch (error: unknown) {
      setSessionsError(errorText(error, "Failed to load chat sessions"));
      setSessions([]);
      setActiveSessionId(null);
    } finally {
      setSessionsLoading(false);
    }
  }

  async function loadMessages(sessionId: number) {
    if (!workspaceId || !userId) {
      return;
    }
    setChatLoading(true);
    setChatError(null);
    try {
      const payload = await apiClient.getChatMessages({
        workspace_id: workspaceId,
        user_id: userId,
        session_id: sessionId,
        limit: 500,
      });
      setMessages(payload.messages.map(mapMessage));

      // Restore active concept from the latest assistant message
      for (let i = payload.messages.length - 1; i >= 0; i--) {
        const record = payload.messages[i];
        if (record.type === "assistant" && typeof record.payload === "object") {
          const candidate = record.payload as Partial<AssistantResponseEnvelope>;
          const resolvedConceptId = candidate.conversation_meta?.resolved_concept_id;
          if (resolvedConceptId) {
            setConcepts((currentConcepts) => {
              const matched = currentConcepts.find((c) => c.concept_id === resolvedConceptId);
              if (matched) {
                setCurrentConcept(matched);
              }
              return currentConcepts;
            });
            break;
          }
        }
      }
    } catch (error: unknown) {
      setMessages([]);
      setChatError(errorText(error, "Failed to load messages"));
    } finally {
      setChatLoading(false);
    }
  }

  async function loadConcepts() {
    if (!workspaceId || !userId) {
      return;
    }
    setConceptsLoading(true);
    setConceptsError(null);
    try {
      const payload = await apiClient.listConcepts({
        workspace_id: workspaceId,
        user_id: userId,
        limit: 120,
      });
      setConcepts(payload.concepts);
      setCurrentConcept((prev) => {
        if (prev) {
          const matched = payload.concepts.find((item) => item.concept_id === prev.concept_id);
          if (matched) {
            return matched;
          }
        }
        return payload.concepts[0] ?? null;
      });
    } catch (error: unknown) {
      setConceptsError(errorText(error, "Failed to load concepts"));
      setConcepts([]);
      setCurrentConcept(null);
    } finally {
      setConceptsLoading(false);
    }
  }

  async function loadSubgraph(conceptId: number) {
    if (!workspaceId || !userId) {
      return;
    }
    try {
      const payload = await apiClient.getConceptSubgraph({
        workspace_id: workspaceId,
        concept_id: conceptId,
        user_id: userId,
        max_hops: 1,
      });
      setSubgraph(payload);
    } catch {
      setSubgraph(null);
    }
  }

  async function onSubmitChat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = query.trim();
    if (!text || !workspaceId || !userId) {
      return;
    }
    const sessionId = await ensureSession();
    if (!sessionId) {
      return;
    }

    const optimisticUser: TimelineMessage = {
      id: `tmp-user-${Date.now()}`,
      role: "user",
      text,
    };
    setMessages((prev) => [...prev, optimisticUser]);
    setQuery("");
    setChatLoading(true);
    setChatError(null);

    try {
      const response = await apiClient.respondChat({
        workspace_id: workspaceId,
        user_id: userId,
        session_id: sessionId,
        query: text,
        concept_id: currentConcept?.concept_id,
        suggested_concept_id: suggestedConceptId ?? undefined,
        concept_switch_decision: switchDecision ?? undefined,
        grounding_mode,
      });
      setMessages((prev) => [
        ...prev,
        {
          id: `tmp-assistant-${Date.now()}`,
          role: "assistant",
          text: response.text,
          response,
        },
      ]);

      const resolvedConceptId = response.conversation_meta?.resolved_concept_id;
      if (resolvedConceptId) {
        const resolved = concepts.find((item) => item.concept_id === resolvedConceptId);
        if (resolved) {
          setCurrentConcept(resolved);
        }
      }
      if (response.conversation_meta?.concept_switch_suggestion) {
        setSwitchSuggestion(response.conversation_meta.concept_switch_suggestion);
      } else {
        setSwitchSuggestion(null);
      }
      setSuggestedConceptId(null);
      setSwitchDecision(null);
      await refreshSessions();
    } catch (error: unknown) {
      setChatError(errorText(error, "Tutor request failed"));
    } finally {
      setChatLoading(false);
    }
  }

  async function startNewSession() {
    if (!workspaceId || !userId) {
      return;
    }
    setChatError(null);
    try {
      const created = await apiClient.createChatSession({ workspace_id: workspaceId, user_id: userId });
      setSessions((prev) => [created, ...prev]);
      setActiveSessionId(created.session_id);
      setMessages([]);
      dispatchLevelUp({ type: "reset" });
    } catch (error: unknown) {
      setSessionsError(errorText(error, "Could not create chat session"));
    }
  }

  async function deleteSession(sessionId: number) {
    if (!workspaceId || !userId) {
      return;
    }
    setSessionsError(null);
    try {
      await apiClient.deleteChatSession({
        workspace_id: workspaceId,
        user_id: userId,
        session_id: sessionId,
      });
      if (activeSessionId === sessionId) {
        setMessages([]);
        dispatchLevelUp({ type: "reset" });
      }
      localStorage.removeItem(`colearni_levelup_${workspaceId}_${userId}_${sessionId}`);
      await refreshSessions();
    } catch (error: unknown) {
      setSessionsError(errorText(error, "Could not delete chat session"));
    }
  }

  async function startLevelUp() {
    if (!workspaceId || !userId || !currentConcept) {
      dispatchLevelUp({ type: "create_error", error: "Pick a concept from the graph first." });
      return;
    }
    const sessionId = await ensureSession();
    if (!sessionId) {
      dispatchLevelUp({ type: "create_error", error: "Session is required." });
      return;
    }

    dispatchLevelUp({ type: "create_start" });
    try {
      const quiz = await apiClient.createLevelUpQuiz({
        workspace_id: workspaceId,
        user_id: userId,
        concept_id: currentConcept.concept_id,
        session_id: sessionId,
      });
      dispatchLevelUp({ type: "create_success", quiz });
    } catch (error: unknown) {
      dispatchLevelUp({ type: "create_error", error: errorText(error, "Create failed") });
    }
  }

  async function submitLevelUp() {
    if (!workspaceId || !userId || !levelUpState.quiz) {
      return;
    }

    dispatchLevelUp({ type: "submit_start" });
    try {
      const result = await apiClient.submitLevelUpQuiz(levelUpState.quiz.quiz_id, {
        workspace_id: workspaceId,
        user_id: userId,
        answers: toSubmitAnswers(levelUpState.quiz.items, levelUpState.answers),
      });
      dispatchLevelUp({ type: "submit_success", result });
    } catch (error: unknown) {
      dispatchLevelUp({ type: "submit_error", error: errorText(error, "Submit failed") });
    }
  }

  const timeline = useMemo(() => messages, [messages]);

  useEffect(() => {
    void refreshSessions();
    void loadConcepts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId, userId]);

  useEffect(() => {
    const handleGlobalClick = () => {
      if (contextMenuId) {
        setContextMenuId(null);
        setContextMenuPos(null);
      }
    };
    document.addEventListener("click", handleGlobalClick);
    return () => document.removeEventListener("click", handleGlobalClick);
  }, [contextMenuId]);

  useEffect(() => {
    if (activeSessionId) {
      void loadMessages(activeSessionId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSessionId]);

  useEffect(() => {
    if (showGraph && currentConcept) {
      void loadSubgraph(currentConcept.concept_id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showGraph, currentConcept?.concept_id, workspaceId, userId]);

  return (
    <section className={`tutor-shell${(showGraph || showQuiz) ? " with-drawer" : ""}`}>
      <aside className={`panel session-sidebar ${sidebarOpen ? "open" : "closed"}`}>
        <div className="button-row" style={{ justifyContent: "space-between" }}>
          <h2>Chats</h2>
          <button type="button" className="secondary icon-btn" onClick={() => { setSidebarOpen(false); localStorage.setItem("colearni-sidebar", "closed"); }} aria-label="Close sidebar">
            ✕
          </button>
        </div>
        <div className="button-row" style={{ marginTop: "0.5rem" }}>
          <button type="button" style={{ width: "100%" }} onClick={() => void startNewSession()}>
            + New chat
          </button>
        </div>
        <div className="session-list">
          {sessions.map((chat) => (
            <div key={chat.session_id} className={`session-item ${chat.session_id === activeSessionId ? "active" : ""} ${contextMenuId === chat.session_id ? "menu-open" : ""}`}>
              {renamingId === chat.session_id ? (
                <form
                  className="session-rename-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const trimmed = renameValue.trim();
                    if (trimmed) {
                      setSessions((prev) =>
                        prev.map((s) =>
                          s.session_id === chat.session_id ? { ...s, title: trimmed } : s
                        )
                      );
                    }
                    setRenamingId(null);
                  }}
                >
                  <input
                    type="text"
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onBlur={() => setRenamingId(null)}
                    onKeyDown={(e) => { if (e.key === "Escape") setRenamingId(null); }}
                    autoFocus
                  />
                </form>
              ) : (
                <button
                  type="button"
                  className="session-item-btn"
                  onClick={() => {
                    setActiveSessionId(chat.session_id);
                    setContextMenuId(null);
                    if (window.innerWidth < 768) {
                      setSidebarOpen(false);
                    }
                  }}
                >
                  <strong>{toTitleCase(chat.title || `Chat ${chat.session_id}`)}</strong>
                </button>
              )}
              <div className="session-actions">
                <button
                  type="button"
                  className="secondary icon-btn session-more-btn"
                  title="More options"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (contextMenuId === chat.session_id) {
                      setContextMenuId(null);
                      setContextMenuPos(null);
                    } else {
                      const rect = e.currentTarget.getBoundingClientRect();
                      const isNearBottom = rect.bottom > window.innerHeight - 120;
                      setContextMenuPos({ x: rect.right, y: isNearBottom ? rect.top : rect.bottom, top: isNearBottom });
                      setContextMenuId(chat.session_id);
                    }
                  }}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="1"></circle>
                    <circle cx="19" cy="12" r="1"></circle>
                    <circle cx="5" cy="12" r="1"></circle>
                  </svg>
                </button>
                {contextMenuId === chat.session_id && (
                  <div
                    className="session-context-menu"
                    style={contextMenuPos?.top ? { bottom: '100%', right: 0, marginBottom: '0.25rem' } : { top: '100%', right: 0, marginTop: '0.25rem' }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setRenameValue(chat.title || `Chat ${chat.session_id}`);
                        setRenamingId(chat.session_id);
                        setContextMenuId(null);
                        setContextMenuPos(null);
                      }}
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                      </svg>
                      Rename
                    </button>
                    <button
                      type="button"
                      className="danger-text"
                      onClick={(e) => {
                        e.stopPropagation();
                        setContextMenuId(null);
                        setContextMenuPos(null);
                        setDeleteConfirmId(chat.session_id);
                      }}
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                      </svg>
                      Delete
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
        {sessionsError ? <p className="status error">{sessionsError}</p> : null}
        {sessionsLoading ? <p className="status loading">Loading chats...</p> : null}
        <div className="sidebar-test-ids">
          <div className="grid">
            <label className="field">
              <span className="field-label">Workspace ID</span>
              <input type="number" min={1} value={workspace_id} onChange={(event) => setWorkspace(event.target.value)} />
            </label>
            <label className="field">
              <span className="field-label">User ID</span>
              <input type="number" min={1} value={user_id} onChange={(event) => setUser(event.target.value)} />
            </label>
          </div>
        </div>
      </aside>

      <section className="chat-main" style={{ background: 'var(--bg)', display: 'flex', flexDirection: 'column', height: '100%' }}>
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.75rem 1rem', borderBottom: '1px solid var(--line)', flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            {!sidebarOpen && (
              <button type="button" className="icon-btn" onClick={() => { setSidebarOpen(true); localStorage.setItem("colearni-sidebar", "open"); }} aria-label="Open sidebar" style={{ marginRight: '0.5rem' }}>
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
              </button>
            )}
            <span style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--text)' }}>Tutor Chat</span>
            {currentConcept && (
              <span style={{ fontSize: '0.85rem', color: 'var(--muted)', marginLeft: '0.5rem' }}>
                · {currentConcept.canonical_name} ({masteryLabel(currentConcept.mastery_status, currentConcept.mastery_score)})
              </span>
            )}
            {suggestedConceptId && (
              <span style={{ fontSize: '0.85rem', color: '#eab308', marginLeft: '0.5rem' }}>
                · Suggestion pending
              </span>
            )}
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <select
              value={grounding_mode}
              onChange={(event) => setGroundingMode(event.target.value as GroundingMode)}
              style={{ fontSize: '0.85rem', padding: '0.2rem 0.5rem', borderRadius: '0.5rem', border: '1px solid var(--line)', background: 'transparent', color: 'var(--text)' }}
            >
              <option value="hybrid">hybrid</option>
              <option value="strict">strict</option>
            </select>
            <button
              type="button"
              className={`header-action-btn${showQuiz ? ' active' : ''}`}
              onClick={() => {
                if (!showQuiz) {
                  setShowGraph(false);
                  setShowQuiz(true);
                  if (levelUpState.phase === "idle") void startLevelUp();
                } else {
                  setShowQuiz(false);
                }
              }}
            >
              {showQuiz ? 'Hide quiz' : 'Level-up quiz'}
            </button>
            <button
              type="button"
              className={`header-action-btn${showGraph ? ' active' : ''}`}
              onClick={() => {
                if (!showGraph) {
                  setShowQuiz(false);
                  setShowGraph(true);
                } else {
                  setShowGraph(false);
                }
              }}
            >
              {showGraph ? 'Hide graph' : 'Show graph'}
            </button>
          </div>
        </header>

        <div className="chat-timeline" aria-live="polite">
          {timeline.length === 0 ? <p className="status empty">Start chatting to build context.</p> : null}
          {timeline.map((message) => (
            <article key={message.id} className={`chat-message ${message.role === "assistant" ? "assistant" : message.role === "user" ? "user" : "system"}`}>
              <div className="chat-avatar">{message.role === "assistant" ? "🤖" : message.role === "user" ? "👤" : "⚙️"}</div>
              <div className="chat-content">
                <p className="chat-role">
                  {message.role === "assistant" ? "Tutor" : message.role === "user" ? "You" : "System"}
                </p>
                {message.role === "assistant" && message.response ? (
                  <ChatResponse response={message.response} />
                ) : (
                  <MarkdownContent content={message.text} />
                )}
              </div>
            </article>
          ))}

          {chatLoading ? <div style={{ display: 'flex', gap: '1rem', padding: '0.5rem 1rem', maxWidth: '48rem', margin: '0 auto', width: '100%' }}><div className="chat-avatar" style={{ background: 'var(--accent)', color: '#fff' }}>🤖</div><div style={{ color: 'var(--muted)', alignSelf: 'center', fontSize: '0.9rem' }}>Thinking...</div></div> : null}
          {chatError ? <p className="status error" style={{ maxWidth: '48rem', margin: '0 auto' }}>{chatError}</p> : null}
        </div>

        <div style={{ padding: '0.5rem 1rem 1rem 1rem', borderTop: 'none' }}>
          <form className="chat-composer" onSubmit={(event) => void onSubmitChat(event)}>
            <textarea
              rows={1}
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                event.target.style.height = 'auto';
                event.target.style.height = `${event.target.scrollHeight}px`;
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              style={{ overflowY: 'hidden', minHeight: '2.8rem', maxHeight: '12rem' }}
              placeholder="Ask a question"
              required
            />
            <button type="submit" disabled={chatLoading} className="send-btn" aria-label="Send">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M4 22L22 12L4 2V9L15 12L4 15V22Z" /></svg>
            </button>
          </form>
        </div>
      </section>

      {
        showGraph ? (
          <aside className="panel graph-drawer">
            <h2>Concept graph</h2>
            {conceptsLoading ? <p className="status loading">Loading concepts...</p> : null}
            {conceptsError ? <p className="status error">{conceptsError}</p> : null}
            {subgraph ? (
              <ConceptGraph
                nodes={subgraph.nodes}
                edges={subgraph.edges}
                selectedId={currentConcept?.concept_id}
                onSelect={(id) => {
                  setSuggestedConceptId(id);
                  const matched = concepts.find((item) => item.concept_id === id);
                  if (matched) {
                    setCurrentConcept(matched);
                  }
                }}
                width={320}
                height={350}
              />
            ) : !conceptsLoading ? (
              <p className="status empty">Select a concept to view its graph.</p>
            ) : null}
            {currentConcept ? (
              <div className="graph-legend">
                <p><strong>{currentConcept.canonical_name}</strong></p>
                <span className="field-label">{masteryLabel(currentConcept.mastery_status, currentConcept.mastery_score)}</span>
              </div>
            ) : null}
          </aside>
        ) : null
      }

      {
        showQuiz ? (
          <aside className="panel quiz-drawer">
            <LevelUpCard
              state={levelUpState}
              onStartQuiz={() => void startLevelUp()}
              onAnswerChange={(itemId, value) =>
                dispatchLevelUp({ type: "answer", item_id: itemId, answer: value })
              }
              onSubmitQuiz={() => void submitLevelUp()}
              onRetryCreate={() => void startLevelUp()}
              onRetrySubmit={() => void submitLevelUp()}
              onStartNew={() => dispatchLevelUp({ type: "reset" })}
            />
          </aside>
        ) : null
      }

      {
        switchSuggestion ? (
          <div className="switch-modal-backdrop" role="dialog" aria-modal="true">
            <div className="panel switch-modal">
              <h3>Concept switch suggested</h3>
              <p>
                The tutor inferred your latest message may be about <strong>{switchSuggestion.to_concept_name}</strong>
                instead of <strong>{switchSuggestion.from_concept_name}</strong>.
              </p>
              <p className="field-label">Reason: {switchSuggestion.reason}</p>
              <div className="button-row">
                <button
                  type="button"
                  onClick={() => {
                    const matched = concepts.find(
                      (item) => item.concept_id === switchSuggestion.to_concept_id,
                    );
                    if (matched) {
                      setCurrentConcept(matched);
                    }
                    setSuggestedConceptId(switchSuggestion.to_concept_id);
                    setSwitchDecision("accept");
                    setSwitchSuggestion(null);
                  }}
                >
                  Switch concept
                </button>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    setSwitchDecision("reject");
                    setSwitchSuggestion(null);
                    setMessages((prev) => [
                      ...prev,
                      {
                        id: `sys-${Date.now()}`,
                        role: "system",
                        text: "Concept switch rejected. Send your next message and the tutor will ask a clarifying question.",
                      },
                    ]);
                  }}
                >
                  Keep current
                </button>
              </div>
            </div>
          </div>
        ) : null
      }

      {deleteConfirmId ? (
        <div className="switch-modal-backdrop" role="dialog" aria-modal="true">
          <div className="panel switch-modal">
            <h3>Delete chat</h3>
            <p>Are you sure you want to delete this chat session? This action cannot be undone.</p>
            <div className="button-row">
              <button
                type="button"
                style={{ background: 'var(--danger)', borderColor: 'var(--danger)' }}
                onClick={() => {
                  const id = deleteConfirmId;
                  setDeleteConfirmId(null);
                  void deleteSession(id);
                }}
              >
                Delete
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => setDeleteConfirmId(null)}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
