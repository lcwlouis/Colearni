"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { getTrail } from "@/lib/api";
import type { TrailDetail } from "@/lib/types";
import { ensureWorkspaceId } from "@/lib/workspace";

import { TrailGraph } from "./components/TrailGraph";

export default function TrailPage() {
  const params = useParams<{ id: string }>();
  const [workspaceId, setWorkspaceId] = useState("");
  const [detail, setDetail] = useState<TrailDetail | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

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

  if (loading) {
    return <main className="p-6 text-sm text-slate-600">Loading graph...</main>;
  }

  if (error || !detail) {
    return (
      <main className="mx-auto max-w-3xl p-6">
        <Link href="/" className="text-sm font-medium text-slate-500 hover:text-slate-900">
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
          <Link href="/" className="text-xs font-medium text-slate-500 hover:text-slate-900">
            CoLearni
          </Link>
          <h1 className="text-lg font-semibold text-slate-950">{detail.trail.title}</h1>
        </div>
        <div className="text-right text-xs text-slate-500">
          {detail.mastery_summary.total} concepts
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
