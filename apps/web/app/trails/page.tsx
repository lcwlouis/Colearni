"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";
import { Trash2 } from "lucide-react";

import { generateTrail, deleteTrail, getTrail, listTrails } from "@/lib/api";
import { formatBloomLevel, formatGraphSize } from "@/lib/display";
import { type TrailProgress, summarizeTrail } from "@/lib/recommendation";
import type { BloomLevel, Trail } from "@/lib/types";
import { ensureWorkspaceId } from "@/lib/workspace";

const bloomLevels: BloomLevel[] = [
  "remember",
  "understand",
  "apply",
  "analyze",
  "evaluate",
  "create",
];

const graphSizes = [20, 40, 75, 100];

// Cosmetic cap on how many concept "nodes" we render in the building-graph
// preview so a large stream never floods the DOM.
const MAX_GRAPH_PREVIEW_NODES = 24;

// Placeholder pill widths used for the animated skeleton when no concept
// titles can be parsed from the stream yet.
const SKELETON_NODE_WIDTHS = [
  "3.5rem",
  "5rem",
  "4.25rem",
  "6rem",
  "4.5rem",
  "5.5rem",
];

// Matches a complete JSON `"title": "..."` pair, tolerating escaped quotes.
// Incomplete titles (no closing quote yet) simply won't match, so we only ever
// surface fully-streamed concept names.
const TITLE_PATTERN = /"title"\s*:\s*"((?:[^"\\]|\\.)*)"/g;

/**
 * Defensively scan an accumulating (possibly partial) JSON stream for concept
 * `title` values, decode JSON escapes, dedupe, and cap the result. Never
 * throws on malformed/partial input — this is a purely cosmetic preview.
 */
function extractConceptTitles(raw: string): string[] {
  const titles: string[] = [];
  const seen = new Set<string>();
  try {
    TITLE_PATTERN.lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = TITLE_PATTERN.exec(raw)) !== null) {
      let title = match[1];
      try {
        title = JSON.parse(`"${match[1]}"`) as string;
      } catch {
        // Partial/invalid escape sequence — keep the raw capture.
      }
      title = title.trim();
      if (!title || seen.has(title)) {
        continue;
      }
      seen.add(title);
      titles.push(title);
      if (titles.length >= MAX_GRAPH_PREVIEW_NODES) {
        break;
      }
    }
  } catch {
    // Never throw on partial JSON; just return what we have so far.
  }
  return titles;
}

/**
 * Returns how many characters at the start of `curr` are shared with the end
 * of `prev`.  Used to split the rolling stream window into stable (already
 * shown) and fresh (just arrived) portions.
 *
 * curr = (prev + chunk).slice(-200), so curr always starts with some suffix of
 * prev followed by the new chunk characters.
 */
function freshOffset(prev: string, curr: string): number {
  if (curr.startsWith(prev)) return prev.length; // no rolling yet
  for (let d = 1; d <= prev.length; d++) {
    if (curr.startsWith(prev.slice(d))) return prev.length - d;
  }
  return 0;
}

function StreamPreview({
  text,
  variant = "output",
}: {
  text: string;
  variant?: "output" | "thinking";
}) {
  const isThinking = variant === "thinking";
  const prevRef = useRef("");
  const [stable, setStable] = useState("");
  const [fresh, setFresh] = useState("");
  // Incrementing key forces React to remount the fresh span so the CSS
  // animations restart on every new chunk.
  const [epoch, setEpoch] = useState(0);

  useEffect(() => {
    const prev = prevRef.current;
    const offset = freshOffset(prev, text);
    setStable(text.slice(0, offset));
    setFresh(text.slice(offset));
    setEpoch((e) => e + 1);
    prevRef.current = text;
  }, [text]);

  // Calm, flat slate palette so the preview reads cleanly on the light, flat
  // generation panel instead of needing its own coloured box. Thinking text is
  // de-emphasised (lighter + italic) versus the streamed output.
  const shimmerColor = "rgba(148,163,184,0.16)";
  const textColor = isThinking
    ? "italic text-slate-500 dark:text-slate-400"
    : "text-slate-600 dark:text-slate-300";
  const cursorColor = isThinking ? "text-slate-400" : "text-slate-500";

  return (
    <div className="relative mt-2 max-h-16 overflow-hidden rounded-sm">
      {/* sweeping shimmer overlay */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background: `linear-gradient(90deg, transparent 20%, ${shimmerColor} 50%, transparent 80%)`,
          backgroundSize: "200% 100%",
          animation: "stream-shimmer 1.8s linear infinite",
        }}
      />
      <pre
        className={`relative break-all whitespace-pre-wrap text-xs leading-5 ${textColor}`}
      >
        {/* characters already visible — no animation */}
        <span>{stable}</span>
        {/* fresh characters animate in one by one */}
        <span key={epoch}>
          {fresh.split("").map((ch, i) => (
            <span
              key={i}
              style={{
                display: "inline",
                opacity: 0,
                animation: "stream-char-in 80ms ease-out both",
                animationDelay: `${i * 3}ms`,
              }}
            >
              {ch}
            </span>
          ))}
        </span>
        {/* blinking block cursor */}
        <span
          className={cursorColor}
          style={{ animation: "stream-cursor 0.9s step-end infinite" }}
        >
          ▋
        </span>
      </pre>
    </div>
  );
}

/** Uppercase, label-led section heading used across the generation panel. */
function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
      {children}
    </div>
  );
}

/** Compact three-segment mastery bar mirroring the dashboard's ProgressBar. */
function MiniProgressBar({ progress }: { progress: TrailProgress }) {
  const total = Math.max(progress.total, 1);
  const masteredPct = (progress.mastered / total) * 100;
  const learningPct = (progress.learning / total) * 100;
  const reviewPct = (progress.needs_review / total) * 100;
  const pct = Math.round(progress.progress * 100);
  return (
    <div
      className="flex h-1.5 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"
      role="img"
      aria-label={`${pct}% progress`}
    >
      <span
        className="h-full bg-emerald-500"
        style={{ width: `${masteredPct}%` }}
        aria-hidden
      />
      <span
        className="h-full bg-blue-400"
        style={{ width: `${learningPct}%` }}
        aria-hidden
      />
      <span
        className="h-full bg-amber-400"
        style={{ width: `${reviewPct}%` }}
        aria-hidden
      />
    </div>
  );
}

export default function TrailsPage() {
  const router = useRouter();
  const [workspaceId, setWorkspaceId] = useState("");
  const [trails, setTrails] = useState<Trail[]>([]);
  const [progressByTrail, setProgressByTrail] = useState<
    Record<string, TrailProgress>
  >({});
  const [topic, setTopic] = useState("");
  const [goal, setGoal] = useState("");
  const [targetDepth, setTargetDepth] = useState<BloomLevel>("apply");
  const [maxNodes, setMaxNodes] = useState(40);
  const [priorKnowledge, setPriorKnowledge] = useState("");
  const [progressLog, setProgressLog] = useState("");
  const [streamPreview, setStreamPreview] = useState("");
  const [thinkingPreview, setThinkingPreview] = useState("");
  const [conceptTitles, setConceptTitles] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(
    null,
  );
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState("");

  // Full accumulated raw stream (the per-character preview only keeps the last
  // 200 chars, which is not enough to scan for concept titles).
  const streamBufferRef = useRef("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const id = await ensureWorkspaceId();
        const response = await listTrails(id);
        if (cancelled) {
          return;
        }
        setWorkspaceId(id);
        setTrails(response.trails);
        // Render the table immediately; mastery progress loads behind it.
        setLoading(false);
        if (response.trails.length === 0) {
          return;
        }
        const details = await Promise.all(
          response.trails.map(async (trail) => {
            try {
              return await getTrail(trail.workspace_id, trail.id);
            } catch {
              return null;
            }
          }),
        );
        if (cancelled) {
          return;
        }
        const map: Record<string, TrailProgress> = {};
        for (const detail of details) {
          if (detail) {
            map[detail.trail.id] = summarizeTrail(detail);
          }
        }
        setProgressByTrail(map);
      } catch (exc) {
        if (!cancelled) {
          setError(
            exc instanceof Error ? exc.message : "Could not load Trails",
          );
          setLoading(false);
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleDelete(trailId: string) {
    setDeletingId(trailId);
    setDeleteError("");
    try {
      await deleteTrail(workspaceId, trailId);
      setTrails((current) => current.filter((t) => t.id !== trailId));
      setProgressByTrail((current) => {
        const next = { ...current };
        delete next[trailId];
        return next;
      });
      setConfirmingDeleteId(null);
    } catch (exc) {
      setDeleteError(exc instanceof Error ? exc.message : "Delete failed");
    } finally {
      setDeletingId(null);
    }
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setGenerating(true);
    setError("");
    setProgressLog("Preparing generation request...");
    setStreamPreview("");
    setThinkingPreview("");
    setConceptTitles([]);
    streamBufferRef.current = "";
    try {
      const response = await generateTrail(
        workspaceId,
        {
          topic,
          goal,
          target_depth: targetDepth,
          max_nodes: maxNodes,
          prior_knowledge: priorKnowledge.trim() || null,
        },
        (message) => {
          setProgressLog((current) => `${current}\n${message}`.slice(-500));
        },
        (chunk) => {
          setStreamPreview((prev) => (prev + chunk).slice(-200));
          // Keep a full buffer so concept titles can be surfaced as they
          // appear in the streamed graph JSON.
          streamBufferRef.current += chunk;
          const titles = extractConceptTitles(streamBufferRef.current);
          if (titles.length > 0) {
            setConceptTitles(titles);
          }
        },
        (chunk) => {
          setThinkingPreview((prev) => (prev + chunk).slice(-200));
        },
      );
      router.push(`/trails/${response.trail.id}`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Trail generation failed");
    } finally {
      setGenerating(false);
    }
  }

  const latestProgress =
    progressLog
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .pop() ?? "Preparing generation request...";

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-8 px-6 py-8">
      <header className="flex items-center justify-between border-b border-slate-200 pb-6">
        <div>
          <Link
            href="/dashboard"
            className="text-sm font-medium text-slate-500 hover:text-slate-900"
          >
            Colearni
          </Link>
          <h1 className="mt-2 text-2xl font-semibold">Trails</h1>
        </div>
      </header>

      <form
        onSubmit={onSubmit}
        className="grid gap-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
      >
        <div>
          <h2 className="text-lg font-semibold text-slate-950">
            Create a new Trail
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Describe what you want to learn and we&apos;ll build a concept graph
            tailored to your goal.
          </p>
        </div>

        {/* Single-column stack keeps every field full-width with consistent
            label spacing and control heights, so the short Topic input and the
            taller Goal / prior-knowledge textareas read as intentional. */}
        <div className="grid gap-5">
          <div className="grid gap-2">
            <label
              htmlFor="topic"
              className="text-sm font-medium text-slate-700"
            >
              Topic
            </label>
            <input
              id="topic"
              value={topic}
              onChange={(event) => setTopic(event.target.value)}
              required
              className="h-11 w-full rounded-lg border border-slate-300 bg-white px-3.5 text-sm shadow-sm outline-none transition-colors placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              placeholder="What do you want to learn?"
            />
          </div>

          <div className="grid gap-2">
            <label
              htmlFor="goal"
              className="text-sm font-medium text-slate-700"
            >
              Goal
            </label>
            <textarea
              id="goal"
              value={goal}
              onChange={(event) => setGoal(event.target.value)}
              required
              rows={3}
              maxLength={2000}
              className="w-full resize-y rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm leading-6 shadow-sm outline-none transition-colors placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              placeholder="Understand the major turning points of world history so I can follow documentaries and books with confidence."
            />
          </div>

          <div className="grid gap-2">
            <label
              htmlFor="prior-knowledge"
              className="text-sm font-medium text-slate-700"
            >
              What do you already know about this?{" "}
              <span className="font-normal text-slate-400">(optional)</span>
            </label>
            <textarea
              id="prior-knowledge"
              value={priorKnowledge}
              onChange={(event) => setPriorKnowledge(event.target.value)}
              rows={3}
              maxLength={2000}
              className="w-full resize-y rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm leading-6 shadow-sm outline-none transition-colors placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              placeholder="e.g. I know a few big dates but not how the events connect"
            />
            <p className="text-xs text-slate-400">
              Leave blank and we&apos;ll assume you&apos;re starting from
              scratch.
            </p>
          </div>
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <fieldset className="grid gap-2">
            <legend className="text-sm font-medium text-slate-700">
              Target depth
            </legend>
            <div
              role="radiogroup"
              aria-label="Target depth"
              className="grid grid-cols-3 gap-1 rounded-lg border border-slate-200 bg-slate-100 p-1"
            >
              {bloomLevels.map((level) => {
                const selected = targetDepth === level;
                return (
                  <button
                    key={level}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => setTargetDepth(level)}
                    className={`rounded-md px-2 py-1.5 text-center text-sm font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-blue-300 ${
                      selected
                        ? "bg-white text-slate-950 shadow-sm"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    {formatBloomLevel(level)}
                  </button>
                );
              })}
            </div>
          </fieldset>

          <fieldset className="grid gap-2">
            <legend className="text-sm font-medium text-slate-700">
              Graph size
            </legend>
            <div
              role="radiogroup"
              aria-label="Graph size"
              className="grid grid-cols-2 gap-1 rounded-lg border border-slate-200 bg-slate-100 p-1"
            >
              {graphSizes.map((count) => {
                const selected = maxNodes === count;
                return (
                  <button
                    key={count}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => setMaxNodes(count)}
                    className={`rounded-md px-2 py-1.5 text-center text-sm font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-blue-300 ${
                      selected
                        ? "bg-white text-slate-950 shadow-sm"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    {formatGraphSize(count)}
                  </button>
                );
              })}
            </div>
          </fieldset>
        </div>

        <div className="flex flex-wrap items-center gap-3 border-t border-slate-100 pt-5">
          <button
            type="submit"
            disabled={!workspaceId || generating}
            className="inline-flex h-11 items-center rounded-lg bg-slate-950 px-5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {generating ? "Generating..." : "Generate Trail"}
          </button>
          {error ? <p className="text-sm text-red-700">{error}</p> : null}
        </div>

        {generating ? (
          <div className="border-l-2 border-slate-300 pl-4 dark:border-slate-700">
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              <span className="size-1.5 animate-pulse rounded-full bg-blue-500" />
              Building your Trail
            </div>

            <div className="mt-3">
              <SectionLabel>Progress</SectionLabel>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                {latestProgress}
              </p>
            </div>

            {thinkingPreview && !streamPreview ? (
              <div className="mt-3 border-t border-slate-100 pt-3 dark:border-slate-800">
                <SectionLabel>Reasoning</SectionLabel>
                <StreamPreview text={thinkingPreview} variant="thinking" />
              </div>
            ) : null}

            {streamPreview ? (
              <div className="mt-3 border-t border-slate-100 pt-3 dark:border-slate-800">
                <SectionLabel>Output</SectionLabel>
                <StreamPreview text={streamPreview} />
              </div>
            ) : null}

            <div className="mt-3 border-t border-slate-100 pt-3 dark:border-slate-800">
              <SectionLabel>Building graph</SectionLabel>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {conceptTitles.length > 0
                  ? conceptTitles.map((title, i) => (
                      <span
                        key={title}
                        className="inline-flex max-w-56 items-center rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 shadow-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                        style={{
                          opacity: 0,
                          animation: "stream-char-in 260ms ease-out both",
                          animationDelay: `${i * 45}ms`,
                        }}
                      >
                        <span
                          aria-hidden
                          className="mr-1.5 size-1.5 shrink-0 rounded-full bg-blue-400"
                        />
                        <span className="truncate">{title}</span>
                      </span>
                    ))
                  : SKELETON_NODE_WIDTHS.map((width, i) => (
                      <span
                        key={i}
                        aria-hidden
                        className="h-6 rounded-full bg-slate-100 animate-pulse dark:bg-slate-800"
                        style={{ width, animationDelay: `${i * 120}ms` }}
                      />
                    ))}
              </div>
            </div>
          </div>
        ) : null}
      </form>

      <section className="grid gap-3">
        <h2 className="text-lg font-semibold">Existing Trails</h2>
        {loading ? <p className="text-sm text-slate-500">Loading...</p> : null}
        {deleteError ? (
          <p className="text-sm text-red-700">{deleteError}</p>
        ) : null}
        {!loading && trails.length === 0 ? (
          <p className="text-sm text-slate-500">No Trails yet.</p>
        ) : null}
        {trails.length > 0 ? (
          <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
            <table className="w-full table-fixed text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-2 font-medium">Title</th>
                  <th className="hidden w-40 px-3 py-2 font-medium sm:table-cell">
                    Progress
                  </th>
                  <th className="w-28 px-3 py-2 text-right font-medium">
                    Mastery
                  </th>
                  <th className="w-20 px-3 py-2 text-right font-medium">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {trails.map((trail) => {
                  const progress = progressByTrail[trail.id];
                  const pct = progress
                    ? Math.round(progress.progress * 100)
                    : null;
                  return (
                    <tr key={trail.id} className="hover:bg-slate-50">
                      <td className="px-4 py-2">
                        <Link
                          href={`/trails/${trail.id}`}
                          className="block truncate font-medium text-slate-900 hover:text-blue-700"
                        >
                          {trail.title}
                        </Link>
                      </td>
                      <td className="hidden px-3 py-2 align-middle sm:table-cell">
                        {progress ? (
                          <MiniProgressBar progress={progress} />
                        ) : (
                          <div
                            className="h-1.5 w-full animate-pulse rounded-full bg-slate-100"
                            aria-hidden
                          />
                        )}
                      </td>
                      <td className="px-3 py-2 text-right align-middle tabular-nums">
                        {progress ? (
                          <>
                            <div className="font-semibold text-slate-950">
                              {pct}%
                            </div>
                            <div className="text-xs text-slate-500">
                              {progress.mastered}/{progress.total} mastered
                            </div>
                          </>
                        ) : (
                          <div className="text-xs text-slate-400">
                            {trail.node_count} concepts
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex items-center justify-end">
                          {confirmingDeleteId === trail.id ? (
                            <div className="flex items-center gap-2 text-xs">
                              <button
                                onClick={() => handleDelete(trail.id)}
                                disabled={deletingId === trail.id}
                                className="font-medium text-red-600 hover:text-red-800 disabled:opacity-50"
                              >
                                {deletingId === trail.id
                                  ? "Deleting..."
                                  : "Confirm"}
                              </button>
                              <button
                                onClick={() => setConfirmingDeleteId(null)}
                                disabled={deletingId === trail.id}
                                className="text-slate-400 hover:text-slate-600 disabled:opacity-50"
                              >
                                Cancel
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => setConfirmingDeleteId(trail.id)}
                              aria-label={`Delete ${trail.title}`}
                              title="Delete Trail"
                              className="inline-flex h-8 w-8 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600 focus:outline-none focus:ring-2 focus:ring-red-100"
                            >
                              <Trash2 className="h-4 w-4" aria-hidden="true" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </main>
  );
}
