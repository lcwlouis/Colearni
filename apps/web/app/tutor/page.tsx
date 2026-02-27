"use client";

import { FormEvent, useEffect, useMemo, useReducer, useState } from "react";

import { ChatResponse } from "@/components/chat-response";
import { ConceptGraph } from "@/components/concept-graph";
import { LevelUpCard } from "@/components/level-up-card";
import { MarkdownContent } from "@/components/markdown-content";
import { useChatSession } from "@/lib/tutor/chat-session-context";
import { ApiError, apiClient } from "@/lib/api/client";
import type {
  AssistantResponseEnvelope,
  ChatMessageRecord,
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
import { useRequireAuth } from "@/lib/auth";

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
  const { user, isLoading: authLoading, activeWorkspaceId } = useRequireAuth();
  const wsId = activeWorkspaceId ?? undefined;

  const {
    activeSessionId,
    startNewSession,
    refreshSessions
  } = useChatSession();

  const [grounding_mode, setGroundingMode] = useState<GroundingMode>("hybrid");
  const [query, setQuery] = useState("");

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

  // Restore existing session data for levelup
  useEffect(() => {
    if (!wsId || !activeSessionId) return;
    const key = `colearni_levelup_${wsId}_${activeSessionId}`;
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
  }, [wsId, activeSessionId]);

  useEffect(() => {
    if (!wsId || !activeSessionId) return;
    const key = `colearni_levelup_${wsId}_${activeSessionId}`;
    if (levelUpState.phase === "idle") {
      localStorage.removeItem(key);
    } else {
      localStorage.setItem(key, JSON.stringify(levelUpState));
    }
  }, [wsId, activeSessionId, levelUpState]);

  async function ensureSession(): Promise<string | null> {
    if (!wsId) return null;
    if (activeSessionId) return activeSessionId;
    return await startNewSession();
  }

  async function loadMessages(sessionId: string) {
    if (!wsId) return;
    setChatLoading(true);
    setChatError(null);
    try {
      const payload = await apiClient.getChatMessages(wsId, sessionId, {
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
    if (!wsId) return;
    setConceptsLoading(true);
    setConceptsError(null);
    try {
      const payload = await apiClient.listConcepts(wsId, {
        limit: 120,
      });
      setConcepts(payload.concepts);
      setCurrentConcept((prev) => {
        if (prev) {
          const matched = payload.concepts.find((item) => item.concept_id === prev.concept_id);
          if (matched) return matched;
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
    if (!wsId) return;
    try {
      const payload = await apiClient.getConceptSubgraph(wsId, conceptId, { max_hops: 2, max_nodes: 40, max_edges: 80 });
      // Filter to mastered/learning nodes + active concept (limit unlearned topology)
      const allowedIds = new Set<number>();
      for (const node of payload.nodes) {
        if (
          node.concept_id === conceptId ||
          node.mastery_status === "learned" ||
          node.mastery_status === "learning" ||
          node.hop_distance <= 1
        ) {
          allowedIds.add(node.concept_id);
        }
      }
      const filteredNodes = payload.nodes.filter((n) => allowedIds.has(n.concept_id));
      const filteredEdges = payload.edges.filter(
        (e) => allowedIds.has(e.src_concept_id) && allowedIds.has(e.tgt_concept_id),
      );
      setSubgraph({ ...payload, nodes: filteredNodes, edges: filteredEdges });
    } catch {
      setSubgraph(null);
    }
  }

  async function onSubmitChat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = query.trim();
    if (!text || !wsId) return;

    const sessionId = await ensureSession();
    if (!sessionId) return;

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
      const response = await apiClient.respondChat(wsId, {
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
      await refreshSessions(); // update session titles if it changed
    } catch (error: unknown) {
      setChatError(errorText(error, "Tutor request failed"));
    } finally {
      setChatLoading(false);
    }
  }

  async function startLevelUp() {
    if (!wsId || !currentConcept) {
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
      const quiz = await apiClient.createLevelUpQuiz(wsId, {
        concept_id: currentConcept.concept_id,
        session_id: sessionId,
      });
      dispatchLevelUp({ type: "create_success", quiz });
    } catch (error: unknown) {
      dispatchLevelUp({ type: "create_error", error: errorText(error, "Create failed") });
    }
  }

  async function submitLevelUp() {
    if (!wsId || !levelUpState.quiz) return;

    dispatchLevelUp({ type: "submit_start" });
    try {
      const result = await apiClient.submitLevelUpQuiz(wsId, levelUpState.quiz.quiz_id, {
        answers: toSubmitAnswers(levelUpState.quiz.items, levelUpState.answers),
      });
      dispatchLevelUp({ type: "submit_success", result });
    } catch (error: unknown) {
      dispatchLevelUp({ type: "submit_error", error: errorText(error, "Submit failed") });
    }
  }

  const timeline = useMemo(() => messages, [messages]);

  useEffect(() => {
    void loadConcepts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wsId]);

  useEffect(() => {
    if (activeSessionId) {
      void loadMessages(activeSessionId);
    } else {
      setMessages([]);
      dispatchLevelUp({ type: "reset" });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSessionId]);

  useEffect(() => {
    if (showGraph && currentConcept) {
      void loadSubgraph(currentConcept.concept_id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showGraph, currentConcept?.concept_id, wsId]);

  if (authLoading || !user) {
    return (
      <div className="flex items-center justify-center" style={{ height: "100%" }}>
        <p style={{ color: "var(--muted)" }}>Loading…</p>
      </div>
    );
  }

  return (
    <section className={`tutor-shell${(showGraph || showQuiz) ? " with-drawer" : ""}`}>
      <section className="chat-main" style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--bg)' }}>
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.75rem 1rem', borderBottom: '1px solid var(--line)', flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
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
              {currentConcept.description ? (
                <p style={{ fontSize: '0.85rem', color: 'var(--muted)', marginTop: '0.35rem', lineHeight: 1.5 }}>
                  {currentConcept.description.length > 200
                    ? currentConcept.description.slice(0, 200) + '…'
                    : currentConcept.description}
                </p>
              ) : null}
            </div>
          ) : null}
        </aside>
      ) : null}

      {showQuiz ? (
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
            onStartNew={() => {
              dispatchLevelUp({ type: "reset" });
              // Auto-start new quiz after reset
              setTimeout(() => void startLevelUp(), 0);
            }}
          />
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
