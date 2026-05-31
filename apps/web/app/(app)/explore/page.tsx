"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { listTrails } from "@/lib/api";
import type { Trail } from "@/lib/types";
import { ensureWorkspaceId } from "@/lib/workspace";

export default function ExplorePage() {
  const [trails, setTrails] = useState<Trail[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const id = await ensureWorkspaceId();
        const { trails: loaded } = await listTrails(id);
        if (cancelled) return;
        setTrails(loaded);
        setLoading(false);
      } catch (exc) {
        if (cancelled) return;
        setError(exc instanceof Error ? exc.message : "Could not load trails");
        setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = query.trim()
    ? trails.filter(
        (t) =>
          t.title.toLowerCase().includes(query.toLowerCase()) ||
          t.topic.toLowerCase().includes(query.toLowerCase()),
      )
    : trails;

  return (
    <div className="w-full space-y-6 px-4 py-8">
      <header className="space-y-1 border-b border-slate-200 pb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Explore</h1>
        <p className="text-sm leading-6 text-slate-500">
          Discover your Trails or import a shared Trail Pack.
        </p>
      </header>

      {/* Trail Pack Import CTA */}
      <div className="flex items-start gap-3 rounded-md border border-dashed border-blue-300 bg-blue-50 p-4">
        <span className="mt-0.5 text-xl">📦</span>
        <div>
          <p className="text-sm font-medium text-blue-800">Trail Pack Import</p>
          <p className="mt-0.5 text-xs text-blue-600">
            Import a shared Trail Pack — coming soon.
          </p>
        </div>
      </div>

      {/* Cross-trail search */}
      <div>
        <label
          htmlFor="trail-search"
          className="mb-1 block text-xs font-medium text-slate-600"
        >
          Search across Trails
        </label>
        <input
          id="trail-search"
          type="search"
          placeholder="Filter by title or topic…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>

      {loading ? (
        <p className="py-8 text-center text-sm text-slate-500">
          Loading trails…
        </p>
      ) : error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      ) : filtered.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          {query.trim()
            ? "No trails match your search."
            : "No trails yet. Create one from the Trails page."}
        </p>
      ) : (
        <div className="space-y-3">
          {filtered.map((trail) => (
            <Link
              key={trail.id}
              href={`/trails/${trail.id}`}
              className="flex items-start justify-between rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-colors hover:border-blue-300 hover:bg-blue-50"
            >
              <div className="space-y-0.5">
                <p className="text-sm font-medium text-slate-900">
                  {trail.title}
                </p>
                <p className="text-xs text-slate-500">{trail.topic}</p>
              </div>
              <span className="ml-4 shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                {trail.node_count} concept{trail.node_count !== 1 ? "s" : ""}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
