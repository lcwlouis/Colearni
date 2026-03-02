"use client";

import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api/client";
import type {
  PracticeQuizDetailResponse,
  PracticeQuizSubmitResponse,
  QuizItemSummary,
  QuizSubmitAnswer,
  QuizFeedbackItem,
} from "@/lib/api/types";

type Props = {
  workspaceId: string;
  quizId: number;
  isRetry: boolean;
  onBack: () => void;
  onRetryComplete?: () => void;
};

export function QuizViewer({
  workspaceId,
  quizId,
  isRetry,
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
        const detail = await apiClient.getPracticeQuiz(workspaceId, quizId);
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
  }, [workspaceId, quizId]);

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
      const res = await apiClient.submitPracticeQuiz(workspaceId, quizId, {
        answers: payload,
      });
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

      {result?.overall_feedback && (
        <p className="quiz-viewer__feedback">{result.overall_feedback}</p>
      )}

      <ol className="quiz-viewer__items">
        {quiz.items.map((item) => (
          <li key={item.item_id} className="quiz-viewer__item">
            <p className="quiz-viewer__prompt">{item.prompt}</p>
            {renderItemBody(item, showResults, feedbackMap, answers, handleAnswer)}
          </li>
        ))}
      </ol>

      {isRetry && !result && (
        <div className="quiz-viewer__submit-row">
          {error && <p className="status error">{error}</p>}
          <button
            type="button"
            disabled={submitting || !allAnswered}
            onClick={handleSubmit}
          >
            {submitting ? "Submitting…" : "Submit"}
          </button>
        </div>
      )}

      {result?.retry_hint && (
        <p className="quiz-viewer__retry-hint">{result.retry_hint}</p>
      )}
    </div>
  );
}

function renderItemBody(
  item: QuizItemSummary,
  showResults: boolean,
  feedbackMap: Map<number, QuizFeedbackItem>,
  answers: Record<number, string>,
  onAnswer: (itemId: number, value: string) => void,
) {
  const fb = feedbackMap.get(item.item_id);

  if (item.item_type === "mcq" && item.choices) {
    return (
      <ul className="quiz-viewer__choices">
        {item.choices.map((choice) => {
          const selected = answers[item.item_id] === choice.id;
          let cls = "quiz-viewer__choice";
          if (showResults && fb) {
            if (selected && fb.is_correct) cls += " quiz-viewer__choice--correct";
            else if (selected && !fb.is_correct) cls += " quiz-viewer__choice--incorrect";
          } else if (selected) {
            cls += " quiz-viewer__choice--selected";
          }

          return (
            <li key={choice.id} className={cls}>
              {showResults ? (
                <span>{choice.text}</span>
              ) : (
                <label>
                  <input
                    type="radio"
                    name={`q-${item.item_id}`}
                    value={choice.id}
                    checked={selected}
                    onChange={() => onAnswer(item.item_id, choice.id)}
                  />
                  {choice.text}
                </label>
              )}
            </li>
          );
        })}
      </ul>
    );
  }

  // Short answer
  if (showResults && fb) {
    return (
      <div>
        <p
          className={
            fb.is_correct
              ? "quiz-viewer__answer--correct"
              : "quiz-viewer__answer--incorrect"
          }
        >
          Your answer: {answers[item.item_id] ?? "—"}
        </p>
        {fb.feedback && (
          <p className="quiz-viewer__item-feedback">{fb.feedback}</p>
        )}
      </div>
    );
  }

  return (
    <input
      type="text"
      className="quiz-viewer__text-input"
      placeholder="Your answer…"
      value={answers[item.item_id] ?? ""}
      onChange={(e) => onAnswer(item.item_id, e.target.value)}
    />
  );
}
