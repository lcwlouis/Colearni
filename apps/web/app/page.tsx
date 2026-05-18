"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { deleteTrail, listTrails } from "@/lib/api";
import type { Trail } from "@/lib/types";
import { ensureWorkspaceId } from "@/lib/workspace";

export default function Home() {
  const [workspaceId, setWorkspaceId] = useState<string>("");
  const [trails, setTrails] = useState<Trail[]>([]);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(
    null,
  );
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string>("");

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
            exc instanceof Error ? exc.message : "Could not load workspace",
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

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-8 px-6 py-8">
      <header className="flex flex-col gap-4 border-b border-slate-200 pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-normal text-slate-950">
            CoLearni
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Create a Trail, inspect the graph, and open a concept panel.
          </p>
        </div>
        <Link
          href="/trails/new"
          className="inline-flex h-10 items-center justify-center rounded-md bg-slate-950 px-4 text-sm font-medium text-white hover:bg-slate-800"
        >
          Create Trail
        </Link>
      </header>

      {workspaceId ? (
        <p className="text-xs text-slate-500">Workspace: {workspaceId}</p>
      ) : null}

      {error ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      <section className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Trails</h2>
          <Link
            href="/trails/new"
            className="text-sm font-medium text-blue-700 hover:text-blue-900"
          >
            New Trail
          </Link>
        </div>
        {loading ? (
          <p className="text-sm text-slate-500">Loading trails...</p>
        ) : null}
        {!loading && trails.length === 0 ? (
          <div className="rounded-md border border-slate-200 bg-white p-6 text-sm text-slate-600">
            No Trails yet.
          </div>
        ) : null}
        <div className="grid gap-3">
          {deleteError ? (
            <p className="text-sm text-red-700">{deleteError}</p>
          ) : null}
          {trails.map((trail) => (
            <div
              key={trail.id}
              className="flex items-center gap-2 rounded-md border border-slate-200 bg-white p-4 hover:border-slate-300"
            >
              <Link href={`/trails/${trail.id}`} className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <h3 className="font-medium text-slate-950">
                      {trail.title}
                    </h3>
                    <p className="mt-1 truncate text-sm text-slate-600">
                      {trail.goal}
                    </p>
                  </div>
                  <span className="shrink-0 text-xs text-slate-500">
                    {trail.node_count} nodes / {trail.edge_count} edges
                  </span>
                </div>
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
        </div>
      </section>
    </main>
  );
}
