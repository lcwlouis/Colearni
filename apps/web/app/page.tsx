"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { deleteTrail, getTrail, getTrailNext, listTrails } from "@/lib/api";
import {
  type TrailProgress,
  isFullyMastered,
  pickContinueTrail,
  summarizeTrail,
} from "@/lib/recommendation";
import type { NextConceptResponse, Trail } from "@/lib/types";
import { ensureWorkspaceId } from "@/lib/workspace";

const RECENT_LIMIT = 4;

export default function Home() {
  const [workspaceId, setWorkspaceId] = useState<string>("");
  const [trails, setTrails] = useState<Trail[]>([]);
  const [progressByTrail, setProgressByTrail] = useState<Record<string, TrailProgress>>({});
  const [nextByTrail, setNextByTrail] = useState<Record<string, NextConceptResponse>>({});
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [progressLoading, setProgressLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string>("");

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
        setLoading(false);
        if (response.trails.length === 0) {
          return;
        }
        setProgressLoading(true);
        const summaries = await Promise.all(
          response.trails.map(async (trail) => {
            try {
              const [detail, next] = await Promise.all([
                getTrail(trail.workspace_id, trail.id),
                getTrailNext(trail.workspace_id, trail.id).catch(() => null),
              ]);
              return { detail, next };
            } catch {
              return null;
            }
          }),
        );
        if (cancelled) {
          return;
        }
        const map: Record<string, TrailProgress> = {};
        const nextMap: Record<string, NextConceptResponse> = {};
        for (const result of summaries) {
          if (result) {
            map[result.detail.trail.id] = summarizeTrail(result.detail);
            if (result.next) {
              nextMap[result.detail.trail.id] = result.next;
            }
          }
        }
        setProgressByTrail(map);
        setNextByTrail(nextMap);
      } catch (exc) {
        if (!cancelled) {
          setError(exc instanceof Error ? exc.message : "Could not load workspace");
          setLoading(false);
        }
      } finally {
        if (!cancelled) {
          setProgressLoading(false);
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const progresses = useMemo(() => Object.values(progressByTrail), [progressByTrail]);
  const continueTrail = useMemo(() => pickContinueTrail(progresses), [progresses]);
  const sortedTrails = useMemo(
    () =>
      [...trails].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [trails],
  );
  const recentTrails = useMemo(() => sortedTrails.slice(0, RECENT_LIMIT), [sortedTrails]);
  const olderTrails = useMemo(() => sortedTrails.slice(RECENT_LIMIT), [sortedTrails]);
  const filteredOlder = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) {
      return olderTrails;
    }
    return olderTrails.filter(
      (t) =>
        t.title.toLowerCase().includes(q) ||
        t.topic.toLowerCase().includes(q) ||
        t.goal.toLowerCase().includes(q),
    );
  }, [olderTrails, search]);

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
      setNextByTrail((current) => {
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

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-8 px-5 py-8 sm:px-6">
      <header className="flex flex-col gap-4 border-b border-slate-200 pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-normal text-slate-950">
            CoLearni
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Continue a Trail, see your progress, and learn one concept at a time.
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
        <div
          role="alert"
          className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {error}
        </div>
      ) : null}

      {loading ? (
        <p className="text-sm text-slate-500">Loading your dashboard...</p>
      ) : null}

      {!loading && trails.length === 0 ? (
        <EmptyState />
      ) : null}

      {!loading && trails.length > 0 ? (
        <>
          <ContinueLearningSection
            progress={continueTrail}
            next={continueTrail ? nextByTrail[continueTrail.detail.trail.id] : undefined}
            loadingProgress={progressLoading && progresses.length === 0}
          />

          <RecentTrailsSection
            trails={recentTrails}
            progressByTrail={progressByTrail}
            nextByTrail={nextByTrail}
            confirmingDeleteId={confirmingDeleteId}
            deletingId={deletingId}
            deleteError={deleteError}
            onAskDelete={setConfirmingDeleteId}
            onCancelDelete={() => setConfirmingDeleteId(null)}
            onConfirmDelete={handleDelete}
          />

          {olderTrails.length > 0 ? (
            <OlderTrailsSection
              trails={filteredOlder}
              progressByTrail={progressByTrail}
              search={search}
              onSearch={setSearch}
            />
          ) : null}
        </>
      ) : null}
    </main>
  );
}

function EmptyState() {
  return (
    <section
      data-testid="dashboard-empty"
      className="rounded-md border border-slate-200 bg-white p-6 text-sm text-slate-600"
    >
      <p className="font-medium text-slate-900">No Trails yet.</p>
      <p className="mt-2">
        Create your first Trail to start learning. CoLearni will build a concept
        graph and a Socratic tutor for it.
      </p>
      <Link
        href="/trails/new"
        className="mt-4 inline-flex h-9 items-center justify-center rounded-md bg-slate-950 px-4 text-sm font-medium text-white hover:bg-slate-800"
      >
        Create your first Trail
      </Link>
    </section>
  );
}

function ContinueLearningSection({
  progress,
  next,
  loadingProgress,
}: {
  progress: TrailProgress | null;
  next: NextConceptResponse | undefined;
  loadingProgress: boolean;
}) {
  // True when pickContinueTrail fell back to an all-mastered trail because
  // every trail is complete. Use local data so we don't wait for /next.
  const allDone = progress !== null && isFullyMastered(progress);

  return (
    <section data-testid="continue-learning" className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold text-slate-950">Continue Learning</h2>
      {loadingProgress ? (
        <p className="text-sm text-slate-500">Loading progress...</p>
      ) : null}
      {!loadingProgress && !progress ? (
        <p className="text-sm text-slate-500">Pick a Trail below to start.</p>
      ) : null}

      {/* All trails fully mastered — achievement state */}
      {progress && allDone ? (
        <article
          data-testid="continue-learning-all-done"
          className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 shadow-sm sm:p-5"
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <p className="text-xs font-medium uppercase tracking-wide text-emerald-700">
                All trails mastered
              </p>
              <h3 className="mt-1 truncate text-base font-semibold text-slate-950">
                {progress.detail.trail.title}
              </h3>
              <p className="mt-1 text-sm text-slate-600">
                You have mastered every concept. Ready to go deeper?
              </p>
            </div>
            <div className="shrink-0">
              <ProgressBadge progress={progress} />
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link
              href="/trails/new"
              className="inline-flex h-9 items-center justify-center rounded-md bg-emerald-600 px-4 text-sm font-medium text-white hover:bg-emerald-700"
            >
              Create New Trail
            </Link>
            <Link
              href={`/trails/${progress.detail.trail.id}`}
              className="inline-flex h-9 items-center justify-center rounded-md border border-slate-200 bg-white px-4 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              View graph
            </Link>
          </div>
        </article>
      ) : null}

      {/* Normal state — there is learning to do */}
      {progress && !allDone ? (
        <article className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <p className="text-xs font-medium uppercase tracking-wide text-blue-700">
                Pick up where you left off
              </p>
              <h3 className="mt-1 truncate text-base font-semibold text-slate-950">
                {progress.detail.trail.title}
              </h3>
              <p className="mt-1 text-sm text-slate-600">{progress.detail.trail.goal}</p>
            </div>
            <div className="shrink-0">
              <ProgressBadge progress={progress} />
            </div>
          </div>
          {next ? (
            <div className="mt-4 rounded-md border border-blue-100 bg-blue-50/60 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-blue-700">
                Recommended next concept
              </p>
              <p className="mt-1 text-sm font-medium text-slate-950">
                {next.concept_title ?? "Open Trail"}
              </p>
              <p className="mt-1 text-xs text-slate-600">{next.reason}</p>
            </div>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-2">
            <Link
              href={
                next?.concept_id
                  ? `/trails/${progress.detail.trail.id}?concept=${next.concept_id}`
                  : `/trails/${progress.detail.trail.id}`
              }
              className="inline-flex h-9 items-center justify-center rounded-md bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-700"
            >
              {next?.concept_id ? primaryCtaLabelFor(next.mastery_status) : "Open Trail"}
            </Link>
            <Link
              href={`/trails/${progress.detail.trail.id}`}
              className="inline-flex h-9 items-center justify-center rounded-md border border-slate-200 bg-white px-4 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              View graph
            </Link>
          </div>
        </article>
      ) : null}
    </section>
  );
}

function RecentTrailsSection({
  trails,
  progressByTrail,
  nextByTrail,
  confirmingDeleteId,
  deletingId,
  deleteError,
  onAskDelete,
  onCancelDelete,
  onConfirmDelete,
}: {
  trails: Trail[];
  progressByTrail: Record<string, TrailProgress>;
  nextByTrail: Record<string, NextConceptResponse>;
  confirmingDeleteId: string | null;
  deletingId: string | null;
  deleteError: string;
  onAskDelete: (id: string) => void;
  onCancelDelete: () => void;
  onConfirmDelete: (id: string) => void;
}) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-950">Recent Trails</h2>
        <Link
          href="/trails/new"
          className="text-sm font-medium text-blue-700 hover:text-blue-900"
        >
          New Trail
        </Link>
      </div>
      {deleteError ? (
        <p className="text-sm text-red-700">{deleteError}</p>
      ) : null}
      <ul className="grid gap-3">
        {trails.map((trail) => (
          <li key={trail.id}>
            <TrailCard
              trail={trail}
              progress={progressByTrail[trail.id]}
              next={nextByTrail[trail.id]}
              confirming={confirmingDeleteId === trail.id}
              deleting={deletingId === trail.id}
              onAskDelete={() => onAskDelete(trail.id)}
              onCancelDelete={onCancelDelete}
              onConfirmDelete={() => onConfirmDelete(trail.id)}
            />
          </li>
        ))}
      </ul>
    </section>
  );
}

function OlderTrailsSection({
  trails,
  progressByTrail,
  search,
  onSearch,
}: {
  trails: Trail[];
  progressByTrail: Record<string, TrailProgress>;
  search: string;
  onSearch: (value: string) => void;
}) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-lg font-semibold text-slate-950">Older Trails</h2>
        <input
          aria-label="Search older Trails"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          placeholder="Search older Trails"
          className="h-9 w-full rounded-md border border-slate-300 px-3 text-sm outline-none focus:border-blue-500 sm:w-64"
        />
      </div>
      {trails.length === 0 ? (
        <p className="text-sm text-slate-500">No matches.</p>
      ) : (
        <ul className="grid gap-2">
          {trails.map((trail) => (
            <li key={trail.id}>
              <Link
                href={`/trails/${trail.id}`}
                className="flex items-center justify-between gap-3 rounded-md border border-slate-200 bg-white px-4 py-3 hover:border-slate-300"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-slate-950">
                    {trail.title}
                  </p>
                  <p className="truncate text-xs text-slate-500">{trail.goal}</p>
                </div>
                <div className="shrink-0 text-right">
                  {progressByTrail[trail.id] ? (
                    <ProgressBadge progress={progressByTrail[trail.id]} compact />
                  ) : (
                    <span className="text-xs text-slate-500">
                      {trail.node_count} concepts
                    </span>
                  )}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function TrailCard({
  trail,
  progress,
  next,
  confirming,
  deleting,
  onAskDelete,
  onCancelDelete,
  onConfirmDelete,
}: {
  trail: Trail;
  progress: TrailProgress | undefined;
  next: NextConceptResponse | undefined;
  confirming: boolean;
  deleting: boolean;
  onAskDelete: () => void;
  onCancelDelete: () => void;
  onConfirmDelete: () => void;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-md border border-slate-200 bg-white p-4 hover:border-slate-300 sm:flex-row sm:items-stretch sm:gap-4">
      <Link href={`/trails/${trail.id}`} className="min-w-0 flex-1">
        <h3 className="truncate text-sm font-semibold text-slate-950">
          {trail.title}
        </h3>
        <p className="mt-1 line-clamp-2 text-xs text-slate-600">{trail.goal}</p>
        <div className="mt-3">
          {progress ? (
            <ProgressBar progress={progress} />
          ) : (
            <p className="text-xs text-slate-500">
              {trail.node_count} concepts / {trail.edge_count} edges
            </p>
          )}
        </div>
      </Link>
      <div className="flex shrink-0 flex-row items-center justify-between gap-3 border-t border-slate-100 pt-3 sm:w-52 sm:flex-col sm:items-stretch sm:justify-between sm:border-l sm:border-t-0 sm:pl-4 sm:pt-0">
        {next?.concept_id && !next.all_mastered ? (
          <Link
            href={`/trails/${trail.id}?concept=${next.concept_id}`}
            className="inline-flex h-8 items-center justify-center rounded-md border border-blue-200 bg-blue-50 px-3 text-xs font-medium text-blue-800 hover:bg-blue-100"
          >
            Start Recommended
          </Link>
        ) : next?.all_mastered ? (
          <Link
            href={`/trails/${trail.id}`}
            className="inline-flex h-8 items-center justify-center rounded-md border border-emerald-200 bg-emerald-50 px-3 text-xs font-medium text-emerald-800 hover:bg-emerald-100"
          >
            All mastered
          </Link>
        ) : (
          <span className="inline-flex h-8 items-center justify-center text-xs text-slate-500">
            No suggestion
          </span>
        )}
        {confirming ? (
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-500">Delete?</span>
            <button
              type="button"
              onClick={onConfirmDelete}
              disabled={deleting}
              className="font-medium text-red-600 hover:text-red-800 disabled:opacity-50"
            >
              {deleting ? "Deleting..." : "Confirm"}
            </button>
            <button
              type="button"
              onClick={onCancelDelete}
              disabled={deleting}
              className="text-slate-400 hover:text-slate-600 disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={onAskDelete}
            className="self-end text-xs text-slate-400 hover:text-red-600"
          >
            Delete
          </button>
        )}
      </div>
    </div>
  );
}

function ProgressBadge({
  progress,
  compact = false,
}: {
  progress: TrailProgress;
  compact?: boolean;
}) {
  const pct = Math.round(progress.progress * 100);
  return (
    <div className={`text-right ${compact ? "text-xs" : "text-sm"}`}>
      <div className="font-semibold text-slate-950">{pct}%</div>
      <div className="text-xs text-slate-500">
        {progress.mastered}/{progress.total} mastered
      </div>
    </div>
  );
}

function primaryCtaLabelFor(status: string | null | undefined): string {
  switch (status) {
    case "learning":     return "Continue Tutor";
    case "needs_review": return "Review Weak Points";
    case "mastered":     return "Practice / Explore Further";
    default:             return "Start Learning";
  }
}

function ProgressBar({ progress }: { progress: TrailProgress }) {
  const masteredPct = (progress.mastered / Math.max(progress.total, 1)) * 100;
  const learningPct = (progress.learning / Math.max(progress.total, 1)) * 100;
  const reviewPct = (progress.needs_review / Math.max(progress.total, 1)) * 100;
  return (
    <div>
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-slate-100">
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
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-600">
        <span>Mastered {progress.mastered}</span>
        <span>Learning {progress.learning}</span>
        <span>Review {progress.needs_review}</span>
        <span>New {progress.not_started}</span>
      </div>
    </div>
  );
}
