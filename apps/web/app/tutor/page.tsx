"use client";

import { FormEvent, useReducer, useState } from "react";

import { ChatThread } from "@/components/chat-thread";
import { LevelUpCard } from "@/components/level-up-card";
import { ApiError, apiClient } from "@/lib/api/client";
import type { ChatRespondRequest, GroundingMode } from "@/lib/api/types";
import {
  canRetryChat,
  chatReducer,
  initialChatState,
  type ChatAction,
} from "@/lib/tutor/chat-state";
import {
  canSubmitLevelUp,
  initialLevelUpState,
  levelUpReducer,
  toSubmitAnswers,
} from "@/lib/tutor/level-up-state";

const asInt = (value: string) =>
  Number.isInteger(Number(value)) && Number(value) > 0 ? Number(value) : undefined;

function messageFromError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}

export default function TutorPage() {
  const [workspace_id, setWorkspace] = useState("1");
  const [user_id, setUser] = useState("1");
  const [concept_id, setConcept] = useState("1");
  const [grounding_mode, setGroundingMode] = useState<GroundingMode>("hybrid");
  const [query, setQuery] = useState("");

  const [chatState, dispatchChat] = useReducer(chatReducer, initialChatState);
  const [levelUpState, dispatchLevelUp] = useReducer(levelUpReducer, initialLevelUpState);

  async function executeChatRequest(request: ChatRespondRequest, dispatchStart?: ChatAction): Promise<void> {
    if (dispatchStart) {
      dispatchChat(dispatchStart);
    }
    try {
      const response = await apiClient.respondChat(request);
      dispatchChat({ type: "receive", response });
    } catch (error: unknown) {
      dispatchChat({ type: "fail", error: messageFromError(error, "Tutor request failed") });
    }
  }

  async function onSubmitChat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = query.trim();
    if (!text) {
      return;
    }

    const payload: ChatRespondRequest = {
      workspace_id: Number(workspace_id),
      query: text,
      grounding_mode,
    };
    const userId = asInt(user_id);
    const conceptId = asInt(concept_id);
    if (userId) {
      payload.user_id = userId;
    }
    if (conceptId) {
      payload.concept_id = conceptId;
    }

    setQuery("");
    await executeChatRequest(payload, { type: "send", request: payload, user_text: text });
  }

  async function retryChat() {
    if (!chatState.retry_request) {
      return;
    }
    await executeChatRequest(chatState.retry_request, { type: "retry" });
  }

  async function startLevelUp() {
    const userId = asInt(user_id);
    const conceptId = asInt(concept_id);
    if (!userId || !conceptId) {
      dispatchLevelUp({ type: "create_error", error: "User ID and Concept ID are required." });
      return;
    }

    dispatchLevelUp({ type: "create_start" });
    try {
      const quiz = await apiClient.createLevelUpQuiz({
        workspace_id: Number(workspace_id),
        user_id: userId,
        concept_id: conceptId,
      });
      dispatchLevelUp({ type: "create_success", quiz });
    } catch (error: unknown) {
      dispatchLevelUp({ type: "create_error", error: messageFromError(error, "Create failed") });
    }
  }

  async function submitLevelUp() {
    if (!levelUpState.quiz) {
      return;
    }
    const userId = asInt(user_id);
    if (!userId) {
      return;
    }
    if (!canSubmitLevelUp(levelUpState)) {
      return;
    }

    dispatchLevelUp({ type: "submit_start" });
    try {
      const result = await apiClient.submitLevelUpQuiz(levelUpState.quiz.quiz_id, {
        workspace_id: Number(workspace_id),
        user_id: userId,
        answers: toSubmitAnswers(levelUpState.quiz.items, levelUpState.answers),
      });
      dispatchLevelUp({ type: "submit_success", result });
    } catch (error: unknown) {
      dispatchLevelUp({ type: "submit_error", error: messageFromError(error, "Submit failed") });
    }
  }

  return (
    <section className="stack">
      <section className="panel stack">
        <h1>Tutor</h1>
        <p>Backend policy remains authoritative for Socratic style, citations, strict grounding, and mastery gating.</p>
        <div className="grid two">
          <label className="field">
            <span className="field-label">Workspace ID</span>
            <input type="number" min={1} value={workspace_id} onChange={(event) => setWorkspace(event.target.value)} required />
          </label>
          <label className="field">
            <span className="field-label">Grounding mode</span>
            <select value={grounding_mode} onChange={(event) => setGroundingMode(event.target.value as GroundingMode)}>
              <option value="hybrid">hybrid</option>
              <option value="strict">strict</option>
            </select>
          </label>
        </div>
        <div className="grid two">
          <label className="field">
            <span className="field-label">User ID</span>
            <input type="number" min={1} value={user_id} onChange={(event) => setUser(event.target.value)} required />
          </label>
          <label className="field">
            <span className="field-label">Concept ID</span>
            <input type="number" min={1} value={concept_id} onChange={(event) => setConcept(event.target.value)} required />
          </label>
        </div>
        <form className="stack" onSubmit={(event) => void onSubmitChat(event)}>
          <label className="field">
            <span className="field-label">Question</span>
            <textarea
              rows={3}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Ask a question"
              required
            />
          </label>
          <div className="button-row">
            <button type="submit" disabled={chatState.status === "loading"}>
              Send
            </button>
            {canRetryChat(chatState) ? (
              <button
                type="button"
                className="secondary"
                onClick={() => void retryChat()}
                disabled={chatState.status === "loading"}
              >
                Retry last send
              </button>
            ) : null}
          </div>
          {chatState.status === "error" ? (
            <p className="status error">Tutor request failed: {chatState.error}</p>
          ) : null}
        </form>
        <ChatThread messages={chatState.messages} loading={chatState.status === "loading"} />
      </section>

      <LevelUpCard
        state={levelUpState}
        onStartQuiz={() => void startLevelUp()}
        onAnswerChange={(itemId, value) => dispatchLevelUp({ type: "answer", item_id: itemId, answer: value })}
        onSubmitQuiz={() => void submitLevelUp()}
        onRetryCreate={() => void startLevelUp()}
        onRetrySubmit={() => void submitLevelUp()}
        onStartNew={() => dispatchLevelUp({ type: "reset" })}
      />
    </section>
  );
}
