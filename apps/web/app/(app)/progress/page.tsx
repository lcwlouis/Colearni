"use client";

import { useEffect, useMemo, useState } from "react";

import { getWorkspaceProgress } from "@/lib/api";
import type { MasteryStatus, TrailProgressItem, WorkspaceProgressResponse } from "@/lib/types";
import { ensureWorkspaceId } from "@/lib/workspace";

const STATUS_DOT: Record<MasteryStatus, string> = {
  mastered: "bg-green-500",
  learning: "bg-blue-500",
  needs_review: "bg-yellow-500",
  not_started: "bg-gray-300 dark:bg-gray-600",
};

type SortOption = "mastery-desc" | "mastery-asc" | "name";

function trailMasteryPct(trail: TrailProgressItem): number {
  const { total, mastered } = trail.mastery_summary;
  return total > 0 ? mastered / total : 0;
}

function MasteryBar({ pct, className = "" }: { pct: number; className?: string }) {
  return (
    <div className={`h-1.5 w-full overflow-hidden rounded-full bg-slate-200 ${className}`}>
      <div className="h-full bg-green-500 transition-all" style={{ width: `${Math.round(pct * 100)}%` }} />
    </div>
  );
}

export default function ProgressPage() {
  const [data, setData] = useState<WorkspaceProgressResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [openTrails, setOpenTrails] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<SortOption>("mastery-desc");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const id = await ensureWorkspaceId();
        const progress = await getWorkspaceProgress(id);
        if (cancelled) return;
        setData(progress);
        setLoading(false);
      } catch (exc) {
        if (cancelled) return;
        setError(exc instanceof Error ? exc.message : "Could not load progress");
        setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  // Auto-expand trails where a concept matches the search query
  useEffect(() => {
    if (!search.trim() || !data) return;
    const q = search.toLowerCase();
    const toOpen = new Set<string>();
    data.trails.forEach((t) => {
      if (t.concepts.some((c) => c.concept_title.toLowerCase().includes(q))) {
        toOpen.add(t.trail_id);
      }
    });
    setOpenTrails((prev) => new Set([...prev, ...toOpen]));
  }, [search, data]);

  const filteredTrails = useMemo(() => {
    let trails = data?.trails ?? [];
    if (search.trim()) {
      const q = search.toLowerCase();
      trails = trails.filter(
        (t) =>
          t.trail_title.toLowerCase().includes(q) ||
          t.concepts.some((c) => c.concept_title.toLowerCase().includes(q)),
      );
    }
    return [...trails].sort((a, b) => {
      if (sortBy === "name") return a.trail_title.localeCompare(b.trail_title);
      const pA = trailMasteryPct(a);
      const pB = trailMasteryPct(b);
      return sortBy === "mastery-desc" ? pB - pA : pA - pB;
    });
  }, [data, search, sortBy]);

  const overall = useMemo(() => {
    const trails = data?.trails ?? [];
    return trails.reduce(
      (acc, t) => ({
        total: acc.total + t.mastery_summary.total,
        mastered: acc.mastered + t.mastery_summary.mastered,
        learning: acc.learning + t.mastery_summary.learning,
      }),
      { total: 0, mastered: 0, learning: 0 },
    );
  }, [data]);

  const notStarted = overall.total - overall.mastered - overall.learning;

  function toggleTrail(id: string) {
    setOpenTrails((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="w-full space-y-4 px-4 py-8">
      {/* Header */}
      <header className="space-y-1 border-b border-slate-200 pb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Progress</h1>
        <p className="text-sm leading-6 text-slate-500">
          Track mastery across all your Trails and concepts.
        </p>
        {!loading && !error && data && data.trails.length > 0 && (
          <p className="text-xs text-slate-500">
            {overall.total} concepts · {overall.mastered} mastered · {overall.learning} learning · {notStarted} not started
          </p>
        )}
      </header>

      {loading ? (
        <p className="py-8 text-center text-sm text-slate-500">Loading progress…</p>
      ) : error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>
      ) : !data || data.trails.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          No trails yet. Create a Trail to start tracking progress.
        </p>
      ) : (
        <>
          {/* Controls */}
          <div className="flex flex-wrap gap-2">
            <input
              type="search"
              placeholder="Search trails or concepts…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400"
            />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortOption)}
              className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-400"
            >
              <option value="mastery-desc">Mastery % (High → Low)</option>
              <option value="mastery-asc">Mastery % (Low → High)</option>
              <option value="name">Name (A → Z)</option>
            </select>
          </div>

          {/* Trail cards */}
          <div className="space-y-2">
            {filteredTrails.length === 0 && (
              <p className="rounded-xl border border-dashed border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
                No trails match your search.
              </p>
            )}
            {filteredTrails.map((trail) => {
              const masteredPct = trailMasteryPct(trail);
              const isOpen = openTrails.has(trail.trail_id);
              const { mastered, learning, total, not_started } = trail.mastery_summary;
              const visibleConcepts = search.trim()
                ? trail.concepts.filter((c) =>
                    c.concept_title.toLowerCase().includes(search.toLowerCase()),
                  )
                : trail.concepts;

              return (
                <div
                  key={trail.trail_id}
                  className="rounded-xl border border-slate-200 bg-white shadow-sm"
                >
                  {/* Trail header — clickable */}
                  <button
                    type="button"
                    onClick={() => toggleTrail(trail.trail_id)}
                    className="flex w-full items-center gap-3 px-4 py-3 text-left"
                  >
                    <svg
                      className={`h-3.5 w-3.5 shrink-0 text-slate-400 transition-transform ${isOpen ? "rotate-90" : ""}`}
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2.5}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                    </svg>
                    <span className="flex-1 truncate text-sm font-medium text-slate-800">
                      {trail.trail_title}
                    </span>
                    <span className="shrink-0 text-xs text-slate-500">
                      {Math.round(masteredPct * 100)}%
                    </span>
                    <div className="w-20 shrink-0">
                      <MasteryBar pct={masteredPct} />
                    </div>
                    <span className="shrink-0 text-xs text-slate-400 tabular-nums">
                      {mastered}/{total}
                      {learning > 0 && <> · {learning} learning</>}
                      {not_started > 0 && <> · {not_started} not started</>}
                    </span>
                  </button>

                  {/* Concept grid */}
                  {isOpen && (
                    <div className="border-t border-slate-100 px-4 py-3">
                      {visibleConcepts.length === 0 ? (
                        <p className="text-xs text-slate-400">No concepts match.</p>
                      ) : (
                        <div className="grid grid-cols-1 gap-x-6 gap-y-0.5 sm:grid-cols-2">
                          {visibleConcepts.map((concept) => (
                            <div
                              key={concept.concept_id}
                              className="flex items-center gap-2 py-1"
                            >
                              <span
                                className={`h-2 w-2 shrink-0 rounded-full ${STATUS_DOT[concept.status]}`}
                              />
                              <span className="min-w-0 flex-1 truncate text-xs text-slate-700">
                                {concept.concept_title}
                              </span>
                              <span className="shrink-0 text-xs tabular-nums text-slate-400">
                                {Math.round(concept.score * 100)}%
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
