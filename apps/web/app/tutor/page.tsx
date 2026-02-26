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
  const [concepts, setConcepts] = useState<GraphConceptSummary[]>([]);
  const [conceptsLoading, setConceptsLoading] = useState(false);
  const [conceptsError, setConceptsError] = useState<string | null>(null);
  const [currentConcept, setCurrentConcept] = useState<GraphConceptSummary | null>(null);
  const [subgraph, setSubgraph] = useState<GraphSubgraphResponse | null>(null);

  const [suggestedConceptId, setSuggestedConceptId] = useState<number | null>(null);
  const [switchSuggestion, setSwitchSuggestion] = useState<ConceptSwitchSuggestion | null>(null);
  const [switchDecision, setSwitchDecision] = useState<"accept" | "reject" | null>(null);

  const [levelUpState, dispatchLevelUp] = useReducer(levelUpReducer, initialLevelUpState);

  const workspaceId = asPositiveInt(workspace_id);
  const userId = asPositiveInt(user_id);

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
    <section className={`tutor-shell${showGraph ? " with-graph" : ""}`}>
      <aside className="panel session-sidebar">
        <div className="button-row">
          <h2>Chats</h2>
          <button type="button" className="secondary" onClick={() => void startNewSession()}>
            New chat
          </button>
        </div>
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
        {sessionsError ? <p className="status error">{sessionsError}</p> : null}
        {sessionsLoading ? <p className="status loading">Loading chats...</p> : null}
        <div className="session-list">
          {sessions.map((chat) => (
            <div key={chat.session_id} className="session-row">
              <button
                type="button"
                className={`session-item ${chat.session_id === activeSessionId ? "active" : ""}`}
                onClick={() => setActiveSessionId(chat.session_id)}
              >
                <strong>{chat.title || `Chat ${chat.session_id}`}</strong>
                <span className="field-label">{new Date(chat.last_activity_at).toLocaleString()}</span>
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => {
                  if (window.confirm("Delete this chat session?")) {
                    void deleteSession(chat.session_id);
                  }
                }}
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      </aside>

      <section className="panel chat-main">
        <header className="chat-header">
          <h1>Tutor Chat</h1>
          <div className="button-row">
            <label className="field-inline">
              <span className="field-label">Grounding</span>
              <select value={grounding_mode} onChange={(event) => setGroundingMode(event.target.value as GroundingMode)}>
                <option value="hybrid">hybrid</option>
                <option value="strict">strict</option>
              </select>
            </label>
            <button type="button" className="secondary" onClick={() => setShowGraph((prev) => !prev)}>
              {showGraph ? "Hide graph" : "Show graph"}
            </button>
            <button type="button" onClick={() => void startLevelUp()}>
              Start level-up quiz
            </button>
          </div>
          <p className="field-label">
            Active concept: {currentConcept ? currentConcept.canonical_name : "None"}
            {currentConcept ? ` · ${masteryLabel(currentConcept.mastery_status, currentConcept.mastery_score)}` : ""}
            {suggestedConceptId ? ` · graph suggestion pending (${suggestedConceptId})` : ""}
          </p>
        </header>

        <div className="chat-timeline" aria-live="polite">
          {timeline.length === 0 ? <p className="status empty">Start chatting to build context.</p> : null}
          {timeline.map((message) => (
            <article key={message.id} className={`chat-message ${message.role === "assistant" ? "assistant" : message.role === "user" ? "user" : "system"}`}>
              <p className="chat-role">
                {message.role === "assistant" ? "Tutor" : message.role === "user" ? "You" : "System"}
              </p>
              {message.role === "assistant" && message.response ? (
                <ChatResponse response={message.response} />
              ) : (
                <MarkdownContent content={message.text} />
              )}
            </article>
          ))}

          {levelUpState.phase !== "idle" ? (
            <article className="chat-message assistant">
              <p className="chat-role">Tutor card</p>
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
            </article>
          ) : null}

          {chatLoading ? <p className="status loading">Tutor is responding...</p> : null}
          {chatError ? <p className="status error">{chatError}</p> : null}
        </div>

        <form className="chat-composer" onSubmit={(event) => void onSubmitChat(event)}>
          <textarea
            rows={3}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Ask a question"
            required
          />
          <div className="button-row">
            <button type="submit" disabled={chatLoading}>Send</button>
          </div>
        </form>
      </section>

      {showGraph ? (
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
      ) : null}

      {switchSuggestion ? (
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
      ) : null}
    </section>
  );
}
