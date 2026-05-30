"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useState, useEffect } from "react";

import { deleteTrail, getTrail, getTrailNext } from "@/lib/api";
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
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialConceptId = searchParams?.get("concept") ?? null;
  const [workspaceId, setWorkspaceId] = useState("");
  const [detail, setDetail] = useState<TrailDetail | null>(null);
  const [next, setNext] = useState<NextConceptResponse | null>(null);
  const [focusConceptId, setFocusConceptId] = useState<string | null>(null);
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

  // A brand-new Trail: nothing has been started, learned, or mastered yet.
  // The /next result is presented as a suggested entry point in this case.
  const isFreshTrail = Boolean(
    detail &&
    detail.mastery_summary.total > 0 &&
    detail.mastery_summary.learning === 0 &&
    detail.mastery_summary.needs_review === 0 &&
    detail.mastery_summary.mastered === 0,
  );

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
      {next ? (
        <NextConceptBanner
          next={next}
          isFreshTrail={isFreshTrail}
          onFocus={() => {
            if (next.concept_id) {
              setFocusConceptId(next.concept_id);
            }
          }}
        />
      ) : null}
      <TrailGraph
        workspaceId={workspaceId}
        trail={detail.trail}
        graph={detail.graph}
        masterySummary={detail.mastery_summary}
        initialConceptId={initialConceptId}
        focusConceptId={focusConceptId}
        onMasteryUpdated={handleMasteryUpdated}
      />
    </main>
  );
}

function NextConceptBanner({
  next,
  isFreshTrail,
  onFocus,
}: {
  next: NextConceptResponse;
  isFreshTrail: boolean;
  onFocus: () => void;
}) {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) {
    return null;
  }
  if (!next.all_mastered && !next.concept_id) {
    return null;
  }

  // On a fresh Trail the recommendation is framed as a suggested starting point
  // rather than a "next" step. It stays purely a suggestion: the learner can
  // dismiss it and start from any node in the graph.
  const showSuggestedStart =
    isFreshTrail && !next.all_mastered && Boolean(next.concept_id);

  const ctaLabel = (() => {
    if (next.all_mastered) return null;
    if (showSuggestedStart) return "Start Here";
    switch (next.mastery_status) {
      case "needs_review":
        return "Review Weak Points";
      case "learning":
        return "Continue Tutor";
      case "mastered":
        return "Practice / Explore Further";
      default:
        return "Start Learning";
    }
  })();

  return (
    <section
      data-testid={
        showSuggestedStart ? "suggested-start-banner" : "next-concept-banner"
      }
      className="shrink-0 border-b border-blue-100 bg-blue-50 px-5 py-3 text-sm"
    >
      <div className="mx-auto flex max-w-6xl flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 flex-1">
          {next.all_mastered ? (
            <p className="font-medium text-slate-950">
              All concepts mastered — well done.
            </p>
          ) : showSuggestedStart ? (
            <p className="font-medium text-slate-950">
              Suggested starting point:{" "}
              <span className="text-blue-700">
                {next.concept_title ?? "Open concept"}
              </span>
            </p>
          ) : (
            <p className="font-medium text-slate-950">
              Recommended next:{" "}
              <span className="text-blue-700">
                {next.concept_title ?? "Open concept"}
              </span>
            </p>
          )}
          <p className="mt-0.5 text-xs text-slate-600">{next.reason}</p>
          {showSuggestedStart ? (
            <p className="mt-0.5 text-xs text-slate-500">
              Just a suggestion — you can start from any concept in the graph.
            </p>
          ) : null}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {ctaLabel && next.concept_id ? (
            <button
              type="button"
              data-testid="next-banner-cta"
              onClick={() => {
                onFocus();
                setDismissed(true);
              }}
              className="inline-flex h-8 items-center justify-center rounded-md bg-blue-600 px-3 text-xs font-medium text-white hover:bg-blue-700"
            >
              {ctaLabel}
            </button>
          ) : null}
          <button
            type="button"
            aria-label="Dismiss recommendation"
            onClick={() => setDismissed(true)}
            className="flex h-8 w-8 items-center justify-center rounded-md text-slate-400 hover:bg-blue-100 hover:text-slate-700"
          >
            ×
          </button>
        </div>
      </div>
    </section>
  );
}
