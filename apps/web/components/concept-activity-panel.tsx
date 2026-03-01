"use client";

import type {
  ConceptActivityResponse,
  ConceptActivityQuiz,
  ConceptActivityFlashcardRun,
} from "@/lib/api/types";

interface ConceptActivityPanelProps {
  activity: ConceptActivityResponse | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  onOpenQuiz?: (quizId: number) => void;
  onRetryQuiz?: (quizId: number) => void;
  onOpenFlashcardRun?: (runId: string) => void;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

function quizScoreLabel(q: ConceptActivityQuiz): string {
  if (q.latest_score != null) {
    const pct = Math.round(q.latest_score * 100);
    return q.passed ? `${pct}% ✓` : `${pct}%`;
  }
  return "pending";
}

function QuizRow({
  quiz,
  label,
  onOpen,
  onRetry,
}: {
  quiz: ConceptActivityQuiz;
  label: string;
  onOpen?: (id: number) => void;
  onRetry?: (id: number) => void;
}) {
  return (
    <li
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0.2rem 0",
        fontSize: "0.85rem",
        gap: "0.5rem",
      }}
    >
      <span style={{ flex: 1 }}>
        {label} · {quizScoreLabel(quiz)}
        {quiz.graded_at ? ` · ${fmtDate(quiz.graded_at)}` : ""}
      </span>
      <span style={{ display: "flex", gap: "0.25rem" }}>
        {onOpen && (
          <button
            type="button"
            className="secondary"
            style={{ fontSize: "0.75rem", padding: "0.1rem 0.4rem" }}
            onClick={() => onOpen(quiz.quiz_id)}
          >
            Open
          </button>
        )}
        {quiz.can_retry && onRetry && (
          <button
            type="button"
            className="secondary"
            style={{ fontSize: "0.75rem", padding: "0.1rem 0.4rem" }}
            onClick={() => onRetry(quiz.quiz_id)}
          >
            Retry
          </button>
        )}
      </span>
    </li>
  );
}

function FlashcardRunRow({
  run,
  onOpen,
}: {
  run: ConceptActivityFlashcardRun;
  onOpen?: (id: string) => void;
}) {
  return (
    <li
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0.2rem 0",
        fontSize: "0.85rem",
        gap: "0.5rem",
      }}
    >
      <span style={{ flex: 1 }}>
        {run.item_count} cards
        {run.exhausted ? " · exhausted" : run.has_more ? " · more available" : ""}
        {run.created_at ? ` · ${fmtDate(run.created_at)}` : ""}
      </span>
      {run.can_open && onOpen && (
        <button
          type="button"
          className="secondary"
          style={{ fontSize: "0.75rem", padding: "0.1rem 0.4rem" }}
          onClick={() => onOpen(run.run_id)}
        >
          Open
        </button>
      )}
    </li>
  );
}

/**
 * Interactive concept activity panel showing prior quizzes and flashcard runs
 * with open/retry affordances.  Replaces the passive PracticeHistory in the
 * graph detail panel.
 */
export function ConceptActivityPanel({
  activity,
  loading,
  error,
  onRefresh,
  onOpenQuiz,
  onRetryQuiz,
  onOpenFlashcardRun,
}: ConceptActivityPanelProps) {
  if (loading && !activity) {
    return <p className="field-label">Loading activity…</p>;
  }
  if (error && !activity) {
    return <p className="status error">{error}</p>;
  }
  if (!activity) return null;

  const { practice_quizzes, level_up_quizzes, flashcard_runs } = activity;
  const empty =
    practice_quizzes.count === 0 &&
    level_up_quizzes.count === 0 &&
    flashcard_runs.count === 0;

  return (
    <div className="stack" style={{ gap: "0.5rem" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <h3 style={{ margin: 0 }}>Activity</h3>
        <button
          type="button"
          className="secondary"
          style={{ fontSize: "0.75rem", padding: "0.15rem 0.5rem" }}
          onClick={onRefresh}
          disabled={loading}
        >
          ↻
        </button>
      </div>

      {empty && <p className="field-label">No activity yet.</p>}

      {practice_quizzes.count > 0 && (
        <div>
          <h4 className="field-label" style={{ marginBottom: "0.25rem" }}>
            Practice quizzes ({practice_quizzes.count})
            {practice_quizzes.average_score != null && (
              <> · avg {Math.round(practice_quizzes.average_score * 100)}%</>
            )}
          </h4>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {practice_quizzes.quizzes.map((q) => (
              <QuizRow
                key={q.quiz_id}
                quiz={q}
                label={q.title}
                onOpen={onOpenQuiz}
                onRetry={onRetryQuiz}
              />
            ))}
          </ul>
        </div>
      )}

      {level_up_quizzes.count > 0 && (
        <div>
          <h4 className="field-label" style={{ marginBottom: "0.25rem" }}>
            Level-up quizzes ({level_up_quizzes.count})
            {level_up_quizzes.passed_count > 0 && (
              <> · {level_up_quizzes.passed_count} passed</>
            )}
          </h4>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {level_up_quizzes.quizzes.map((q) => (
              <QuizRow
                key={q.quiz_id}
                quiz={q}
                label={q.title}
                onOpen={onOpenQuiz}
                onRetry={onRetryQuiz}
              />
            ))}
          </ul>
        </div>
      )}

      {flashcard_runs.count > 0 && (
        <div>
          <h4 className="field-label" style={{ marginBottom: "0.25rem" }}>
            Flashcard runs ({flashcard_runs.count})
            {flashcard_runs.total_cards_generated > 0 && (
              <> · {flashcard_runs.total_cards_generated} cards total</>
            )}
          </h4>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {flashcard_runs.runs.map((r) => (
              <FlashcardRunRow
                key={r.run_id}
                run={r}
                onOpen={onOpenFlashcardRun}
              />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
