"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState, useEffect } from "react";

import { deleteTrail, getTrail } from "@/lib/api";
import type { TrailDetail } from "@/lib/types";
import { ensureWorkspaceId } from "@/lib/workspace";

import { TrailGraph } from "./components/TrailGraph";

export default function TrailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [workspaceId, setWorkspaceId] = useState("");
  const [detail, setDetail] = useState<TrailDetail | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const id = await ensureWorkspaceId();
        const trail = await getTrail(id, params.id);
        if (!cancelled) {
          setWorkspaceId(id);
          setDetail(trail);
        }
      } catch (exc) {
        if (!cancelled) {
          setError(exc instanceof Error ? exc.message : "Could not load Trail");
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
  }, [params.id]);

  async function handleDelete() {
    setDeleting(true);
    setDeleteError("");
    try {
      await deleteTrail(workspaceId, params.id);
      router.push("/");
    } catch (exc) {
      setDeleteError(exc instanceof Error ? exc.message : "Delete failed");
      setDeleting(false);
      setConfirmingDelete(false);
    }
  }

  if (loading) {
    return <main className="p-6 text-sm text-slate-600">Loading graph...</main>;
  }

  if (error || !detail) {
    return (
      <main className="mx-auto max-w-3xl p-6">
        <Link
          href="/"
          className="text-sm font-medium text-slate-500 hover:text-slate-900"
        >
          CoLearni
        </Link>
        <div className="mt-6 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error || "Trail not found"}
        </div>
      </main>
    );
  }

  return (
    <main className="flex h-screen min-h-[680px] flex-col overflow-hidden bg-slate-50">
      <header className="flex shrink-0 items-center justify-between border-b border-slate-200 bg-white px-5 py-3">
        <div>
          <Link
            href="/"
            className="text-xs font-medium text-slate-500 hover:text-slate-900"
          >
            CoLearni
          </Link>
          <h1 className="text-lg font-semibold text-slate-950">
            {detail.trail.title}
          </h1>
        </div>
        <div className="flex items-center gap-3">
          {deleteError ? (
            <span className="text-xs text-red-600">{deleteError}</span>
          ) : null}
          {confirmingDelete ? (
            <>
              <span className="text-xs text-slate-500">Delete this Trail?</span>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="text-xs font-medium text-red-600 hover:text-red-800 disabled:opacity-50"
              >
                {deleting ? "Deleting..." : "Confirm"}
              </button>
              <button
                onClick={() => setConfirmingDelete(false)}
                disabled={deleting}
                className="text-xs text-slate-400 hover:text-slate-600 disabled:opacity-50"
              >
                Cancel
              </button>
            </>
          ) : (
            <button
              onClick={() => setConfirmingDelete(true)}
              className="text-xs text-slate-400 hover:text-red-600"
            >
              Delete Trail
            </button>
          )}
          <div className="text-right text-xs text-slate-500">
            {detail.mastery_summary.total} concepts
          </div>
        </div>
      </header>
      <TrailGraph
        workspaceId={workspaceId}
        trail={detail.trail}
        graph={detail.graph}
        masterySummary={detail.mastery_summary}
      />
    </main>
  );
}
