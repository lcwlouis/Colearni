"use client";

import { useState, useEffect, useCallback } from "react";
import type { PracticeQuizHistoryEntry } from "@/lib/api/types";
import { apiClient } from "@/lib/api/client";
import { QuizViewer } from "./quiz-viewer";

type Props = {
  workspaceId: string;
  conceptId: number;
  onCreateQuiz?: () => void;
};

export function QuizHistory({ workspaceId, conceptId, onCreateQuiz }: Props) {
  const [quizzes, setQuizzes] = useState<PracticeQuizHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedQuizId, setSelectedQuizId] = useState<number | null>(null);
  const [retryingQuizId, setRetryingQuizId] = useState<number | null>(null);

  const fetchQuizzes = useCallback(async () => {
    setLoading(true);
    try {
      const result = await apiClient.listPracticeQuizzes(
        workspaceId,
        conceptId,
        50,
      );
      setQuizzes(result.quizzes);
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
        const result = await apiClient.listPracticeQuizzes(
          workspaceId,
          conceptId,
          50,
        );
        if (!cancelled) setQuizzes(result.quizzes);
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
        {onCreateQuiz && (
          <button type="button" onClick={onCreateQuiz}>
            Create practice quiz
          </button>
        )}
      </div>
    );
  }

  if (selectedQuizId != null) {
    return (
      <QuizViewer
        workspaceId={workspaceId}
        quizId={selectedQuizId}
        isRetry={retryingQuizId === selectedQuizId}
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
      <ul className="quiz-history__list">
        {quizzes.map((q) => (
          <li key={q.quiz_id} className="quiz-history__item">
            <div className="quiz-history__info">
              <span className="quiz-history__date">
                {new Date(q.created_at).toLocaleDateString()}
              </span>
              <span className="quiz-history__questions">
                {q.item_count} questions
              </span>
              {q.latest_attempt && (
                <span
                  className={`quiz-history__score ${q.latest_attempt.passed ? "quiz-history__score--pass" : "quiz-history__score--fail"}`}
                >
                  {Math.round(q.latest_attempt.score * 100)}%
                </span>
              )}
            </div>
            <div className="quiz-history__actions">
              <button
                type="button"
                className="secondary"
                onClick={() => setSelectedQuizId(q.quiz_id)}
              >
                View
              </button>
              <button
                type="button"
                onClick={() => {
                  setRetryingQuizId(q.quiz_id);
                  setSelectedQuizId(q.quiz_id);
                }}
              >
                Retry
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
