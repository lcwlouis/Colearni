"use client";

import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api/client";
import { QuizItemInput } from "@/components/quiz-item-input";
import type {
  PracticeQuizDetailResponse,
  PracticeQuizSubmitResponse,
  QuizSubmitAnswer,
  QuizFeedbackItem,
} from "@/lib/api/types";

type Props = {
  workspaceId: string;
  quizId: number;
  isRetry: boolean;
  source?: "practice" | "level_up";
  onBack: () => void;
  onRetryComplete?: () => void;
};

export function QuizViewer({
  workspaceId,
  quizId,
  isRetry,
  source = "practice",
  onBack,
  onRetryComplete,
}: Props) {
  const [quiz, setQuiz] = useState<PracticeQuizDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Retry state
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<PracticeQuizSubmitResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const detail = source === "level_up"
          ? await apiClient.getLevelUpQuiz(workspaceId, quizId)
          : await apiClient.getPracticeQuiz(workspaceId, quizId);
        if (!cancelled) setQuiz(detail);
      } catch (err) {
        if (!cancelled) setError("Failed to load quiz");
        console.error("Failed to load quiz:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [workspaceId, quizId, source]);

  function handleAnswer(itemId: number, value: string) {
    setAnswers((prev) => ({ ...prev, [itemId]: value }));
  }

  async function handleSubmit() {
    if (!quiz) return;
    setSubmitting(true);
    setError(null);
    try {
      const payload: QuizSubmitAnswer[] = quiz.items.map((item) => ({
        item_id: item.item_id,
        answer: answers[item.item_id] ?? "",
      }));
      // Retries always grade as practice (no mastery impact).
      // Only first-time level-up submissions use the level-up endpoint.
      const usePracticeSubmit = isRetry || source !== "level_up";
      const res = usePracticeSubmit
        ? await apiClient.submitPracticeQuiz(workspaceId, quizId, { answers: payload })
        : await apiClient.submitLevelUpQuiz(workspaceId, quizId, { answers: payload });
      setResult(res);
      onRetryComplete?.();
    } catch (err) {
      setError("Failed to submit quiz");
      console.error("Failed to submit quiz:", err);
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="quiz-viewer">
        <p style={{ color: "var(--muted)", padding: "1rem" }}>
          Loading quiz…
        </p>
      </div>
    );
  }

  if (error && !quiz) {
    return (
      <div className="quiz-viewer">
        <p className="status error">{error}</p>
        <button type="button" className="secondary" onClick={onBack}>
          ← Back
        </button>
      </div>
    );
  }

  if (!quiz) return null;

  const feedbackMap = new Map<number, QuizFeedbackItem>();
  if (result) {
    for (const fb of result.items) {
      feedbackMap.set(fb.item_id, fb);
    }
  } else if (quiz.latest_attempt?.grading_items) {
    for (const fb of quiz.latest_attempt.grading_items) {
      feedbackMap.set(fb.item_id, fb);
    }
  }

  const showResults = !isRetry || result != null;
  const allAnswered =
    quiz.items.length > 0 &&
    quiz.items.every((item) => (answers[item.item_id] ?? "").trim() !== "");

  return (
    <div className="quiz-viewer">
      <div className="quiz-viewer__header">
        <button type="button" className="secondary" onClick={onBack}>
          ← Back
        </button>
        {result ? (
          <span
            className={`quiz-viewer__score ${result.passed ? "quiz-viewer__score--pass" : "quiz-viewer__score--fail"}`}
          >
            {Math.round(result.score * 100)}%{" "}
            {result.passed ? "Passed" : "Not passed"}
          </span>
        ) : !isRetry && quiz.latest_attempt ? (
          <span
            className={`quiz-viewer__score ${quiz.latest_attempt.passed ? "quiz-viewer__score--pass" : "quiz-viewer__score--fail"}`}
          >
            {Math.round(quiz.latest_attempt.score * 100)}%{" "}
            {quiz.latest_attempt.passed ? "Passed" : "Not passed"}
          </span>
        ) : null}
      </div>

      <ol className="quiz-items">
        {quiz.items.map((item, idx) => {
          const fb = feedbackMap.get(item.item_id);
          return (
            <li key={item.item_id} className={`quiz-item${fb ? (fb.is_correct ? " correct" : " incorrect") : ""}`}>
              <p><strong>{idx + 1}. {item.prompt.replace(/^\d+[\.\)]\s*/, "")}</strong></p>
              <QuizItemInput
                item={item}
                value={answers[item.item_id] ?? ""}
                disabled={showResults || submitting}
                onChange={handleAnswer}
              />
              {fb && (
                <div className="quiz-item-feedback">
                  <span className={`quiz-item-result-label ${fb.is_correct ? "correct" : "incorrect"}`}>
                    {fb.is_correct ? "✓ Correct" : "✗ Incorrect"}
                  </span>
                  {fb.feedback && <p>{fb.feedback}</p>}
                </div>
              )}
            </li>
          );
        })}
      </ol>

      {submitting && (
        <p className="status loading">Submitting and grading...</p>
      )}

      {isRetry && !result && (
        <div className="button-row">
          {error && <p className="status error">{error}</p>}
          <button
            type="button"
            onClick={() => { void handleSubmit(); }}
            disabled={submitting || !allAnswered}
          >
            {submitting ? "Submitting…" : "Submit"}
          </button>
        </div>
      )}

      {result && (
        <div className="stack level-up-feedback">
          <h3>Results</h3>
          {result.overall_feedback && <p>{result.overall_feedback}</p>}
          <p className="field-label">
            Score: {Math.round(result.score * 100)}% · {result.passed ? "Passed" : "Not passed"}
          </p>
          {result.retry_hint && <p className="field-label">{result.retry_hint}</p>}
        </div>
      )}
    </div>
  );
}
