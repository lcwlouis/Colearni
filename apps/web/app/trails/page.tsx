"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";

import { generateTrail, deleteTrail, listTrails } from "@/lib/api";
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

  // amber-200 on the dark slate container gives good contrast;
  // blue-300 on the light blue container also reads cleanly.
  const shimmerColor = isThinking
    ? "rgba(251,191,36,0.20)"
    : "rgba(147,197,253,0.18)";
  const textColor = isThinking ? "text-amber-200" : "text-blue-300";
  const cursorColor = isThinking ? "text-amber-300" : "text-blue-400";

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

export default function TrailsPage() {
  const router = useRouter();
  const [workspaceId, setWorkspaceId] = useState("");
  const [trails, setTrails] = useState<Trail[]>([]);
  const [topic, setTopic] = useState("");
  const [goal, setGoal] = useState("");
  const [targetDepth, setTargetDepth] = useState<BloomLevel>("apply");
  const [maxNodes, setMaxNodes] = useState(40);
  const [progressLog, setProgressLog] = useState("");
  const [streamPreview, setStreamPreview] = useState("");
  const [thinkingPreview, setThinkingPreview] = useState("");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(
    null,
  );
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const id = await ensureWorkspaceId();
        const response = await listTrails(id);
        if (!cancelled) {
          setWorkspaceId(id);
          setTrails(response.trails);
        }
      } catch (exc) {
        if (!cancelled) {
          setError(
            exc instanceof Error ? exc.message : "Could not load Trails",
          );
        }
      } finally {
        if (!cancelled) {
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
    try {
      const response = await generateTrail(
        workspaceId,
        { topic, goal, target_depth: targetDepth, max_nodes: maxNodes },
        (message) => {
          setProgressLog((current) => `${current}\n${message}`.slice(-500));
        },
        (chunk) => {
          setStreamPreview((prev) => (prev + chunk).slice(-200));
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

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-8 px-6 py-8">
      <header className="flex items-center justify-between border-b border-slate-200 pb-6">
        <div>
          <Link
            href="/"
            className="text-sm font-medium text-slate-500 hover:text-slate-900"
          >
            CoLearni
          </Link>
          <h1 className="mt-2 text-2xl font-semibold">Trails</h1>
        </div>
      </header>

      <form
        onSubmit={onSubmit}
        className="grid gap-4 rounded-md border border-slate-200 bg-white p-5"
      >
        <div className="grid gap-2">
          <label htmlFor="topic" className="text-sm font-medium">
            Topic
          </label>
          <input
            id="topic"
            value={topic}
            onChange={(event) => setTopic(event.target.value)}
            required
            className="h-10 rounded-md border border-slate-300 px-3 text-sm outline-none focus:border-blue-500"
            placeholder="Linear Algebra"
          />
        </div>
        <div className="grid gap-2">
          <label htmlFor="goal" className="text-sm font-medium">
            Goal
          </label>
          <input
            id="goal"
            value={goal}
            onChange={(event) => setGoal(event.target.value)}
            required
            className="h-10 rounded-md border border-slate-300 px-3 text-sm outline-none focus:border-blue-500"
            placeholder="Understand enough for machine learning"
          />
        </div>
        <div className="grid gap-2 sm:max-w-xs">
          <label htmlFor="target-depth" className="text-sm font-medium">
            Target depth
          </label>
          <select
            id="target-depth"
            value={targetDepth}
            onChange={(event) =>
              setTargetDepth(event.target.value as BloomLevel)
            }
            className="h-10 rounded-md border border-slate-300 px-3 text-sm outline-none focus:border-blue-500"
          >
            {bloomLevels.map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>
        </div>
        <div className="grid gap-2 sm:max-w-xs">
          <label htmlFor="max-nodes" className="text-sm font-medium">
            Graph size
          </label>
          <select
            id="max-nodes"
            value={maxNodes}
            onChange={(event) => setMaxNodes(Number(event.target.value))}
            className="h-10 rounded-md border border-slate-300 px-3 text-sm outline-none focus:border-blue-500"
          >
            {[20, 40, 75, 100].map((count) => (
              <option key={count} value={count}>
                Up to {count} concepts
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={!workspaceId || generating}
            className="inline-flex h-10 items-center rounded-md bg-slate-950 px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {generating ? "Generating..." : "Generate Trail"}
          </button>
          {error ? <p className="text-sm text-red-700">{error}</p> : null}
        </div>
        {generating ? (
          <div className="rounded-md border border-blue-200 bg-blue-50 p-3">
            <div className="text-sm font-medium text-blue-950">
              Generating Trail
            </div>
            <pre className="mt-2 max-h-24 whitespace-pre-wrap text-xs leading-5 text-blue-900">
              {progressLog.slice(-500)}
            </pre>
            {thinkingPreview && !streamPreview ? (
              <div className="mt-2 rounded-sm border border-amber-700/50 bg-slate-800 p-2">
                <div className="mb-1 text-xs font-medium text-amber-400">
                  Reasoning
                </div>
                <StreamPreview text={thinkingPreview} variant="thinking" />
              </div>
            ) : null}
            {streamPreview ? <StreamPreview text={streamPreview} /> : null}
          </div>
        ) : null}
      </form>

      <section className="grid gap-3">
        <h2 className="text-lg font-semibold">Existing Trails</h2>
        {loading ? <p className="text-sm text-slate-500">Loading...</p> : null}
        {deleteError ? (
          <p className="text-sm text-red-700">{deleteError}</p>
        ) : null}
        {trails.map((trail) => (
          <div
            key={trail.id}
            className="flex items-center gap-2 rounded-md border border-slate-200 bg-white p-4 hover:border-slate-300"
          >
            <Link href={`/trails/${trail.id}`} className="min-w-0 flex-1">
              <h3 className="font-medium">{trail.title}</h3>
              <p className="mt-1 text-sm text-slate-600">
                {trail.node_count} concepts
              </p>
            </Link>
            <div className="flex shrink-0 items-center gap-2 border-l border-slate-100 pl-3">
              {confirmingDeleteId === trail.id ? (
                <>
                  <span className="text-xs text-slate-500">Delete?</span>
                  <button
                    onClick={() => handleDelete(trail.id)}
                    disabled={deletingId === trail.id}
                    className="text-xs font-medium text-red-600 hover:text-red-800 disabled:opacity-50"
                  >
                    {deletingId === trail.id ? "Deleting..." : "Confirm"}
                  </button>
                  <button
                    onClick={() => setConfirmingDeleteId(null)}
                    disabled={deletingId === trail.id}
                    className="text-xs text-slate-400 hover:text-slate-600 disabled:opacity-50"
                  >
                    Cancel
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setConfirmingDeleteId(trail.id)}
                  className="text-xs text-slate-400 hover:text-red-600"
                >
                  Delete
                </button>
              )}
            </div>
          </div>
        ))}
      </section>
    </main>
  );
}
