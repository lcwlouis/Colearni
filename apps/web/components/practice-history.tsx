"use client";

import type {
  PracticeQuizHistoryEntry,
  FlashcardRunSummary,
} from "@/lib/api/types";

interface PracticeHistoryProps {
  quizzes: PracticeQuizHistoryEntry[];
  flashcardRuns: FlashcardRunSummary[];
  loading: boolean;
  error: string | null;
  onRefresh?: () => void;
}

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

function quizStatusLabel(entry: PracticeQuizHistoryEntry): string {
  if (entry.latest_attempt) {
    const pct = Math.round(entry.latest_attempt.score * 100);
    return entry.latest_attempt.passed ? `${pct}% ✓` : `${pct}%`;
  }
  return entry.status;
}

/**
 * Compact history section showing past quiz attempts and flashcard runs
 * for a selected concept.  Designed for embedding in the graph detail panel.
 */
export function PracticeHistory({
  quizzes,
  flashcardRuns,
  loading,
  error,
  onRefresh,
}: PracticeHistoryProps) {
  const empty = quizzes.length === 0 && flashcardRuns.length === 0;

  return (
    <div className="stack" style={{ gap: "0.5rem" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <h3 style={{ margin: 0 }}>History</h3>
        {onRefresh && (
          <button
            type="button"
            className="secondary"
            style={{ fontSize: "0.75rem", padding: "0.15rem 0.5rem" }}
            onClick={onRefresh}
            disabled={loading}
          >
            ↻
          </button>
        )}
      </div>

      {loading && <p className="field-label">Loading…</p>}
      {error && <p className="status error">{error}</p>}

      {!loading && !error && empty && (
        <p className="field-label">No practice history yet.</p>
      )}

      {quizzes.length > 0 && (
        <div>
          <h4 className="field-label" style={{ marginBottom: "0.25rem" }}>
            Quizzes ({quizzes.length})
          </h4>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {quizzes.map((q) => (
              <li
                key={q.quiz_id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  padding: "0.15rem 0",
                  fontSize: "0.85rem",
                }}
              >
                <span>
                  {q.concept_name ?? "Quiz"} · {q.item_count}q
                </span>
                <span className="field-label">
                  {quizStatusLabel(q)} · {fmtDate(q.created_at)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {flashcardRuns.length > 0 && (
        <div>
          <h4 className="field-label" style={{ marginBottom: "0.25rem" }}>
            Flashcard runs ({flashcardRuns.length})
          </h4>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {flashcardRuns.map((r) => (
              <li
                key={r.run_id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  padding: "0.15rem 0",
                  fontSize: "0.85rem",
                }}
              >
                <span>
                  {r.concept_name} · {r.item_count} cards
                </span>
                <span className="field-label">{fmtDate(r.created_at)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
