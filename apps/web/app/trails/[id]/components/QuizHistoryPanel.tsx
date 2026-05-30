"use client";

import { useEffect, useState } from "react";

import { listQuizAttempts } from "@/lib/api";
import type { QuizAttempt } from "@/lib/types";

import { QuizAttemptList } from "./quizShared";

type HistoryFilter = "all" | "level_up" | "practice";

interface QuizHistoryPanelProps {
  workspaceId: string;
  trailId: string;
  conceptId: string;
  onBack: () => void;
}

export function QuizHistoryPanel({
  workspaceId,
  trailId,
  conceptId,
  onBack,
}: QuizHistoryPanelProps) {
  const [filter, setFilter] = useState<HistoryFilter>("all");
  const [attempts, setAttempts] = useState<QuizAttempt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    // The panel is concept-keyed (remounts per concept), so loading/error start
    // at their initial values on every (re)mount; no synchronous reset needed.
    let cancelled = false;

    listQuizAttempts(workspaceId, trailId, conceptId, { limit: 25 })
      .then((response) => {
        if (cancelled) return;
        setAttempts(response.attempts);
        setLoading(false);
      })
      .catch((exc) => {
        if (cancelled) return;
        setError(
          exc instanceof Error ? exc.message : "Could not load attempts",
        );
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [workspaceId, trailId, conceptId]);

  const visible =
    filter === "all"
      ? attempts
      : attempts.filter((attempt) => attempt.quiz_type === filter);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-900">Past attempts</h3>
        <button
          type="button"
          onClick={onBack}
          className="text-xs text-slate-500 hover:text-slate-800"
        >
          Back
        </button>
      </div>

      <p className="text-xs text-slate-500">
        Review previous quizzes without starting a new one. Click an attempt to
        see the questions, your answers, and feedback.
      </p>

      <div className="flex gap-2">
        {(["all", "level_up", "practice"] as const).map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => setFilter(value)}
            className={`rounded-full border px-3 py-1 text-xs font-medium ${
              filter === value
                ? "border-blue-300 bg-blue-50 text-blue-700"
                : "border-slate-200 text-slate-600 hover:bg-slate-50"
            }`}
          >
            {value === "all"
              ? "All"
              : value === "level_up"
                ? "Level-up"
                : "Practice"}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="py-8 text-center text-sm text-slate-500">
          Loading past attempts...
        </p>
      ) : error ? (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      ) : visible.length === 0 ? (
        <p className="rounded-md border border-dashed border-slate-300 bg-slate-50 p-4 text-center text-sm text-slate-500">
          No attempts yet. Take a practice or level-up quiz to build a history.
        </p>
      ) : (
        <QuizAttemptList attempts={visible} />
      )}
    </div>
  );
}
