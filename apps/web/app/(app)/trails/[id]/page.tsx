"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useState, useEffect } from "react";

import { getTrail, getTrailNext } from "@/lib/api";
import type {
  MasteryRecord,
  MasteryStatus,
  NextConceptResponse,
  TrailDetail,
} from "@/lib/types";
import { ensureWorkspaceId } from "@/lib/workspace";

import { TrailGraph } from "./components/TrailGraph";

export default function TrailPage() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const initialConceptId = searchParams?.get("concept") ?? null;
  const [workspaceId, setWorkspaceId] = useState("");
  const [detail, setDetail] = useState<TrailDetail | null>(null);
  const [next, setNext] = useState<NextConceptResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const id = await ensureWorkspaceId();
        const [trail, recommendation] = await Promise.all([
          getTrail(id, params.id),
          getTrailNext(id, params.id).catch(() => null),
        ]);
        if (!cancelled) {
          setWorkspaceId(id);
          setDetail(trail);
          setNext(recommendation);
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

  function handleMasteryUpdated(
    conceptId: string,
    update: { status: MasteryStatus; score: number },
  ) {
    setDetail((current) => {
      if (!current) {
        return current;
      }
      const existing = current.graph.mastery[conceptId];
      const updatedRecord: MasteryRecord = {
        id: existing?.id ?? null,
        workspace_id: existing?.workspace_id ?? current.trail.workspace_id,
        concept_id: conceptId,
        status: update.status,
        bloom_level: existing?.bloom_level ?? "understand",
        score: update.score,
        updated_at: new Date().toISOString(),
      };
      const updatedMastery = {
        ...current.graph.mastery,
        [conceptId]: updatedRecord,
      };
      const nodes = current.graph.nodes;
      const summary = {
        total: nodes.length,
        not_started: 0,
        learning: 0,
        needs_review: 0,
        mastered: 0,
      };
      for (const node of nodes) {
        const status: MasteryStatus =
          updatedMastery[node.id]?.status ?? "not_started";
        summary[status] += 1;
      }
      return {
        ...current,
        graph: { ...current.graph, mastery: updatedMastery },
        mastery_summary: summary,
      };
    });
  }

  if (loading) {
    return <main className="p-6 text-sm text-slate-600">Loading graph...</main>;
  }

  if (error || !detail) {
    return (
      <main className="mx-auto max-w-3xl p-6">
        <Link
          href="/dashboard"
          className="text-sm font-medium text-slate-500 hover:text-slate-900"
        >
          Colearni
        </Link>
        <div className="mt-6 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error || "Trail not found"}
        </div>
      </main>
    );
  }

  return (
    <main className="flex h-[100svh] min-h-170 flex-col overflow-hidden bg-slate-50 md:h-screen">
      <TrailGraph
        workspaceId={workspaceId}
        trail={detail.trail}
        graph={detail.graph}
        masterySummary={detail.mastery_summary}
        initialConceptId={initialConceptId}
        recommendedConceptId={next?.concept_id ?? null}
        onMasteryUpdated={handleMasteryUpdated}
      />
    </main>
  );
}
