"use client";

import { useEffect, useMemo, useState } from "react";

import { listWorkspaceQuizAttempts, listWorkspaceSources } from "@/lib/api";
import type {
  SourceAccess,
  SourceOrigin,
  WorkspaceQuizAttemptItem,
  WorkspaceSourceItem,
} from "@/lib/types";
import { ensureWorkspaceId } from "@/lib/workspace";

const originLabel: Record<SourceOrigin, string> = {
  research_agent: "Research Agent",
  user_upload: "User Upload",
  manual: "Manual",
  system: "System",
};

const accessLabel: Record<SourceAccess, string> = {
  public: "Public",
  private: "Private",
  restricted: "Restricted",
  unknown: "Unknown",
};

export default function SourcesPage() {
  const [sources, setSources] = useState<WorkspaceSourceItem[]>([]);
  const [quizAttempts, setQuizAttempts] = useState<WorkspaceQuizAttemptItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [trailFilter, setTrailFilter] = useState<string>("");
  const [conceptFilter, setConceptFilter] = useState<string>("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const id = await ensureWorkspaceId();
        const [sourcesData, attemptsData] = await Promise.all([
          listWorkspaceSources(id),
          listWorkspaceQuizAttempts(id).catch(() => ({ attempts: [] })),
        ]);
        if (cancelled) return;
        setSources(sourcesData.sources);
        setQuizAttempts(attemptsData.attempts);
        setLoading(false);
      } catch (exc) {
        if (cancelled) return;
        setError(exc instanceof Error ? exc.message : "Could not load sources");
        setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleTrailChange = (value: string) => {
    setTrailFilter(value);
    setConceptFilter("");
  };

  const trailOptions = useMemo(() => {
    const map = new Map<string, string>();
    sources.forEach((s) =>
      s.linked_concepts.forEach((lc) => map.set(lc.trail_id, lc.trail_title)),
    );
    return [...map.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [sources]);

  const conceptOptions = useMemo(() => {
    if (!trailFilter) return [];
    const map = new Map<string, string>();
    sources.forEach((s) =>
      s.linked_concepts
        .filter((lc) => lc.trail_id === trailFilter)
        .forEach((lc) => map.set(lc.concept_id, lc.concept_title)),
    );
    return [...map.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [sources, trailFilter]);

  const filteredSources = useMemo(() => {
    return sources.filter((s) => {
      if (!trailFilter) return true;
      const trailMatch = s.linked_concepts.some((lc) => lc.trail_id === trailFilter);
      if (!trailMatch) return false;
      if (!conceptFilter) return true;
      return s.linked_concepts.some((lc) => lc.concept_id === conceptFilter);
    });
  }, [sources, trailFilter, conceptFilter]);

  const conceptAttempts = useMemo(
    () =>
      conceptFilter
        ? quizAttempts.filter((a) => a.concept_id === conceptFilter)
        : [],
    [quizAttempts, conceptFilter],
  );

  const selectedConceptTitle = useMemo(() => {
    if (!conceptFilter) return "";
    const opt = conceptOptions.find(([id]) => id === conceptFilter);
    return opt ? opt[1] : "";
  }, [conceptFilter, conceptOptions]);

  return (
    <div className="w-full space-y-6 px-4 py-8">
      <header className="space-y-1 border-b border-slate-200 pb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Sources</h1>
        <p className="text-sm text-slate-500">
          All sources attached to concepts in your workspace.
        </p>
      </header>

      {loading ? (
        <p className="py-8 text-center text-sm text-slate-500">
          Loading sources...
        </p>
      ) : error ? (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      ) : sources.length === 0 ? (
        <p className="rounded-md border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-500">
          No sources yet. Add sources to a concept inside a Trail.
        </p>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <select
              value={trailFilter}
              onChange={(e) => handleTrailChange(e.target.value)}
              className="h-8 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-300"
            >
              <option value="">All Trails</option>
              {trailOptions.map(([id, title]) => (
                <option key={id} value={id}>
                  {title}
                </option>
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
                  <option key={id} value={id}>
                    {title}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white shadow-sm">
            {filteredSources.length === 0 ? (
              <p className="px-4 py-6 text-center text-sm text-slate-500">
                No sources match the selected filters.
              </p>
            ) : (
              filteredSources.map((source) => (
                <div
                  key={source.id}
                  className="flex items-start justify-between gap-4 p-4"
                >
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <p className="truncate text-sm font-medium text-slate-900">
                      {source.title}
                    </p>
                    {source.url && (
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block truncate text-xs text-blue-600 hover:underline"
                      >
                        {source.url}
                      </a>
                    )}
                    <span className="text-xs text-slate-400">
                      {originLabel[source.origin as SourceOrigin] ?? source.origin}
                      {" · "}
                      {accessLabel[source.access as SourceAccess] ?? source.access}
                    </span>
                    {source.linked_concepts.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 pt-0.5">
                        {source.linked_concepts.map((link) => (
                          <span
                            key={`${link.trail_id}-${link.concept_id}`}
                            className="inline-flex items-center rounded-md bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700"
                          >
                            {link.trail_title}
                            <span className="mx-1 text-indigo-400">›</span>
                            {link.concept_title}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>

          {conceptFilter && (
            <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
              <div className="border-b border-slate-100 px-4 py-3">
                <h2 className="text-sm font-semibold text-slate-900">
                  Quiz Attempts — {selectedConceptTitle}
                </h2>
              </div>
              {conceptAttempts.length === 0 ? (
                <p className="px-4 py-6 text-center text-sm text-slate-500">
                  No quiz attempts for this concept yet.
                </p>
              ) : (
                <div className="divide-y divide-slate-100">
                  {conceptAttempts.map((attempt) => (
                    <div
                      key={attempt.id}
                      className="flex items-center gap-3 px-4 py-2.5"
                    >
                      <span className="w-24 shrink-0 text-xs text-slate-400">
                        {new Date(attempt.created_at).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        })}
                      </span>
                      <span
                        className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                          attempt.quiz_type === "level_up"
                            ? "bg-violet-50 text-violet-700"
                            : "bg-blue-50 text-blue-700"
                        }`}
                      >
                        {attempt.quiz_type === "level_up" ? "Level-Up" : "Practice"}
                      </span>
                      <span
                        className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                          attempt.passed
                            ? "bg-emerald-50 text-emerald-700"
                            : "bg-red-50 text-red-600"
                        }`}
                      >
                        {attempt.passed ? "Passed" : "Failed"}
                      </span>
                      <span
                        className={`ml-auto text-sm font-semibold ${
                          attempt.score >= 0.8
                            ? "text-emerald-600"
                            : attempt.score >= 0.5
                              ? "text-amber-600"
                              : "text-red-500"
                        }`}
                      >
                        {Math.round(attempt.score * 100)}%
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
