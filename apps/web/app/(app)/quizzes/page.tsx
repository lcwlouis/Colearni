"use client";

import { useEffect, useMemo, useState } from "react";

import { listWorkspaceQuizAttempts } from "@/lib/api";
import type { WorkspaceQuizAttemptItem } from "@/lib/types";
import { ensureWorkspaceId } from "@/lib/workspace";

type SortBy = "date-desc" | "date-asc" | "score-desc";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function QuizzesPage() {
  const [attempts, setAttempts] = useState<WorkspaceQuizAttemptItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<SortBy>("date-desc");
  const [trailFilter, setTrailFilter] = useState<string>("");
  const [conceptFilter, setConceptFilter] = useState<string>("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const id = await ensureWorkspaceId();
        const { attempts: data } = await listWorkspaceQuizAttempts(id);
        if (cancelled) return;
        setAttempts(data);
        setLoading(false);
      } catch (exc) {
        if (cancelled) return;
        setError(exc instanceof Error ? exc.message : "Could not load quiz attempts");
        setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const trailOptions = useMemo(() => {
    const map = new Map<string, string>();
    attempts.forEach((a) => map.set(a.trail_id, a.trail_title));
    return [...map.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [attempts]);

  const conceptOptions = useMemo(() => {
    if (!trailFilter) return [];
    const map = new Map<string, string>();
    attempts
      .filter((a) => a.trail_id === trailFilter)
      .forEach((a) => map.set(a.concept_id, a.concept_title));
    return [...map.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [attempts, trailFilter]);

  const filtered = useMemo(() => {
    let list = attempts;
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (a) =>
          a.concept_title.toLowerCase().includes(q) ||
          a.trail_title.toLowerCase().includes(q),
      );
    }
    if (trailFilter) {
      list = list.filter((a) => a.trail_id === trailFilter);
    }
    if (conceptFilter) {
      list = list.filter((a) => a.concept_id === conceptFilter);
    }
    return [...list].sort((a, b) => {
      if (sortBy === "date-asc")
        return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      if (sortBy === "score-desc") return b.score - a.score;
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });
  }, [attempts, search, sortBy, trailFilter, conceptFilter]);

  return (
    <div className="w-full space-y-6 px-4 py-8">
      <header className="space-y-1 border-b border-slate-200 pb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Quiz History</h1>
        <p className="text-sm leading-6 text-slate-500">
          All quiz attempts across your Trails.
        </p>
      </header>

      {!loading && !error && attempts.length > 0 && (
        <div className="flex flex-wrap items-center gap-3">
          <input
            type="search"
            placeholder="Search by concept or trail…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-8 min-w-48 flex-1 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-300"
          />
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortBy)}
            className="h-8 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
          >
            <option value="date-desc">Newest first</option>
            <option value="date-asc">Oldest first</option>
            <option value="score-desc">Score (high→low)</option>
          </select>
          <select
            value={trailFilter}
            onChange={(e) => { setTrailFilter(e.target.value); setConceptFilter(""); }}
            className="h-8 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
          >
            <option value="">All Trails</option>
            {trailOptions.map(([id, title]) => (
              <option key={id} value={id}>{title}</option>
            ))}
          </select>
          {trailFilter && (
            <select
              value={conceptFilter}
              onChange={(e) => setConceptFilter(e.target.value)}
              className="h-8 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
            >
              <option value="">All Concepts</option>
              {conceptOptions.map(([id, title]) => (
                <option key={id} value={id}>{title}</option>
              ))}
            </select>
          )}
        </div>
      )}

      {loading ? (
        <p className="py-8 text-center text-sm text-slate-500">
          Loading quiz attempts…
        </p>
      ) : error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      ) : attempts.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          No quizzes taken yet. Start learning a concept to take your first quiz.
        </p>
      ) : filtered.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          No results for &ldquo;{search}&rdquo;{trailFilter ? " in this trail" : ""}.
        </p>
      ) : (
        <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white shadow-sm">
          {filtered.map((attempt) => (
            <div
              key={attempt.id}
              className="flex items-center gap-4 px-4 py-3"
            >
              {/* Type + pass/fail */}
              <div className="flex shrink-0 flex-col gap-1">
                <span className="w-16 shrink-0 text-xs text-slate-500">
                  {attempt.quiz_type === "level_up" ? "Level-Up" : "Practice"}
                </span>
                <span className={`text-xs font-medium ${attempt.passed ? "text-emerald-600" : "text-red-500"}`}>
                  {attempt.passed ? "● Passed" : "● Failed"}
                </span>
              </div>

              {/* Main content */}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-slate-900">
                  {attempt.concept_title}
                </p>
                <div className="mt-0.5 flex items-center gap-2">
                  <span className="text-xs text-slate-400">{attempt.trail_title}</span>
                  <span className="text-xs text-slate-400">
                    {formatDate(attempt.created_at)}
                  </span>
                </div>
              </div>

              {/* Score */}
              <p
                className={`shrink-0 text-sm font-semibold tabular-nums ${
                  attempt.score >= 0.8
                    ? "text-emerald-600"
                    : attempt.score >= 0.5
                      ? "text-amber-600"
                      : "text-red-500"
                }`}
              >
                {Math.round(attempt.score * 100)}%
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
