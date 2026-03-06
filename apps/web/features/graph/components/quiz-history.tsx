"use client";

import { useState, useEffect, useCallback } from "react";
import type { PracticeQuizHistoryEntry } from "@/lib/api/types";
import { apiClient } from "@/lib/api/client";
import { QuizViewer } from "./quiz-viewer";

type QuizSource = "practice" | "level_up";
type QuizHistoryItem = PracticeQuizHistoryEntry & { source: QuizSource };

type Props = {
  workspaceId: string;
  conceptId: number;
  onCreateQuiz?: () => void;
};

export function QuizHistory({ workspaceId, conceptId, onCreateQuiz }: Props) {
  const [quizzes, setQuizzes] = useState<QuizHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedQuizId, setSelectedQuizId] = useState<number | null>(null);
  const [selectedSource, setSelectedSource] = useState<QuizSource>("practice");
  const [retryingQuizId, setRetryingQuizId] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);

  const fetchQuizzes = useCallback(async () => {
    setLoading(true);
    try {
      const [practiceResult, levelUpResult] = await Promise.all([
        apiClient.listPracticeQuizzes(workspaceId, conceptId, 50),
        apiClient.listLevelUpQuizzes(workspaceId, conceptId, 50),
      ]);
      const merged: QuizHistoryItem[] = [
        ...practiceResult.quizzes.map((q) => ({ ...q, source: "practice" as const })),
        ...levelUpResult.quizzes.map((q) => ({ ...q, source: "level_up" as const })),
      ].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
      setQuizzes(merged);
    } catch (err) {
      console.error("Failed to fetch quizzes:", err);
    } finally {
      setLoading(false);
    }
  }, [workspaceId, conceptId]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const [practiceResult, levelUpResult] = await Promise.all([
          apiClient.listPracticeQuizzes(workspaceId, conceptId, 50),
          apiClient.listLevelUpQuizzes(workspaceId, conceptId, 50),
        ]);
        if (!cancelled) {
          const merged: QuizHistoryItem[] = [
            ...practiceResult.quizzes.map((q) => ({ ...q, source: "practice" as const })),
            ...levelUpResult.quizzes.map((q) => ({ ...q, source: "level_up" as const })),
          ].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
          setQuizzes(merged);
        }
      } catch (err) {
        console.error("Failed to fetch quizzes:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [workspaceId, conceptId]);

  async function handleCreate() {
    setCreating(true);
    try {
      const newQuiz = await apiClient.createPracticeQuiz(workspaceId, {
        concept_id: conceptId,
      });
      onCreateQuiz?.();
      setSelectedQuizId(newQuiz.quiz_id);
      await fetchQuizzes();
    } catch (err) {
      console.error("Failed to create quiz:", err);
    } finally {
      setCreating(false);
    }
  }

  if (loading) {
    return (
      <p style={{ color: "var(--muted)", padding: "1rem" }}>
        Loading quizzes…
      </p>
    );
  }

  if (quizzes.length === 0) {
    return (
      <div style={{ padding: "1rem", textAlign: "center" }}>
        <p style={{ color: "var(--muted)", marginBottom: "0.5rem" }}>
          No quizzes yet
        </p>
        <button type="button" disabled={creating} onClick={() => { void handleCreate(); }}>
          {creating ? "Creating…" : "Create practice quiz"}
        </button>
      </div>
    );
  }

  if (selectedQuizId != null) {
    return (
      <QuizViewer
        workspaceId={workspaceId}
        quizId={selectedQuizId}
        isRetry={retryingQuizId != null}
        source={selectedSource}
        onBack={() => {
          setSelectedQuizId(null);
          setRetryingQuizId(null);
        }}
        onRetryComplete={() => {
          fetchQuizzes();
        }}
      />
    );
  }

  return (
    <div className="quiz-history">
      <div style={{ padding: "0.5rem 0", textAlign: "center" }}>
        <button type="button" disabled={creating} onClick={() => { void handleCreate(); }}>
          {creating ? "Creating…" : "＋ New practice quiz"}
        </button>
      </div>
      <ul className="quiz-history__list">
        {quizzes.map((q) => (
          <li key={q.quiz_id} className="quiz-history__item">
            <div className="quiz-history__info">
              <span className="quiz-history__type" style={{ fontSize: "0.7rem", color: "var(--muted)" }}>
                {q.source === "level_up" ? "🎯 Level-up" : "📝 Practice"}
              </span>
              {q.concept_name && (
                <span className="quiz-history__concept">{q.concept_name}</span>
              )}
              <span className="quiz-history__date">
                {new Date(q.created_at).toLocaleDateString()}
              </span>
              <span className="quiz-history__questions">
                {q.item_count} questions
              </span>
              {q.latest_attempt ? (
                <span
                  className={`quiz-history__score ${q.latest_attempt.passed ? "quiz-history__score--pass" : "quiz-history__score--fail"}`}
                >
                  {Math.round(q.latest_attempt.score * 100)}%{" "}
                  {q.latest_attempt.passed ? "Passed" : "Failed"}
                </span>
              ) : (
                <span className="quiz-history__score quiz-history__score--pending">
                  Not attempted
                </span>
              )}
            </div>
            <div className="quiz-history__actions">
              <button
                type="button"
                className="secondary"
                onClick={() => { setSelectedQuizId(q.quiz_id); setSelectedSource(q.source); }}
              >
                View
              </button>
              {q.latest_attempt != null && (
                <button
                  type="button"
                  onClick={() => {
                    setSelectedQuizId(q.quiz_id);
                    setSelectedSource(q.source);
                    setRetryingQuizId(q.quiz_id);
                  }}
                >
                  Retry
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
