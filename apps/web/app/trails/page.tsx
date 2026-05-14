"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { generateTrail, listTrails } from "@/lib/api";
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

export default function TrailsPage() {
  const router = useRouter();
  const [workspaceId, setWorkspaceId] = useState("");
  const [trails, setTrails] = useState<Trail[]>([]);
  const [topic, setTopic] = useState("");
  const [goal, setGoal] = useState("");
  const [targetDepth, setTargetDepth] = useState<BloomLevel>("apply");
  const [maxNodes, setMaxNodes] = useState(40);
  const [progressLog, setProgressLog] = useState("");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

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
          setError(exc instanceof Error ? exc.message : "Could not load Trails");
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

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setGenerating(true);
    setError("");
    setProgressLog("Preparing generation request...");
    try {
      const response = await generateTrail(workspaceId, {
        topic,
        goal,
        target_depth: targetDepth,
        max_nodes: maxNodes,
      }, (message) => {
        setProgressLog((current) => `${current}\n${message}`.slice(-300));
      });
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
          <Link href="/" className="text-sm font-medium text-slate-500 hover:text-slate-900">
            CoLearni
          </Link>
          <h1 className="mt-2 text-2xl font-semibold">Trails</h1>
        </div>
      </header>

      <form onSubmit={onSubmit} className="grid gap-4 rounded-md border border-slate-200 bg-white p-5">
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
            onChange={(event) => setTargetDepth(event.target.value as BloomLevel)}
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
            <div className="text-sm font-medium text-blue-950">Generating Trail</div>
            <pre className="mt-2 max-h-24 whitespace-pre-wrap text-xs leading-5 text-blue-900">
              {progressLog.slice(-300)}
            </pre>
          </div>
        ) : null}
      </form>

      <section className="grid gap-3">
        <h2 className="text-lg font-semibold">Existing Trails</h2>
        {loading ? <p className="text-sm text-slate-500">Loading...</p> : null}
        {trails.map((trail) => (
          <Link
            key={trail.id}
            href={`/trails/${trail.id}`}
            className="rounded-md border border-slate-200 bg-white p-4 hover:border-slate-300"
          >
            <h3 className="font-medium">{trail.title}</h3>
            <p className="mt-1 text-sm text-slate-600">{trail.node_count} concepts</p>
          </Link>
        ))}
      </section>
    </main>
  );
}
