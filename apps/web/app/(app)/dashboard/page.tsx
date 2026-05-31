"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  Compass,
  Flame,
  MessageCircleQuestion,
  Pin,
  PinOff,
  Play,
  Plus,
  Sparkles,
  Target,
  Trash2,
  Trophy,
  Zap,
} from "lucide-react";

import { deleteTrail, getTrail, getTrailNext, listTrails } from "@/lib/api";
import {
  type TrailProgress,
  isFullyMastered,
  pickContinueTrail,
  summarizeTrail,
} from "@/lib/recommendation";
import type { NextConceptResponse, Trail } from "@/lib/types";
import { ensureWorkspaceId } from "@/lib/workspace";
import { type TrailSortMode, sortTrailsForDashboard } from "./sortTrails";

// Matches the hardcoded learner name used in the sidebar profile chip until
// auth + real user profiles land.
const LEARNER_NAME = "Louis";
const PINNED_STORAGE_KEY = "colearni.pinnedTrails";

type TrailFilter = "all" | "in_progress" | "completed" | "pinned";

const SORT_OPTIONS: Array<{ value: TrailSortMode; label: string }> = [
  { value: "recent", label: "Most recently used" },
  { value: "created_desc", label: "Created (newest first)" },
  { value: "created_asc", label: "Created (oldest first)" },
  { value: "mastery_desc", label: "Mastery completion (highest first)" },
  { value: "mastery_asc", label: "Mastery completion (lowest first)" },
];

export default function Home() {
  const [workspaceId, setWorkspaceId] = useState<string>("");
  const [trails, setTrails] = useState<Trail[]>([]);
  const [progressByTrail, setProgressByTrail] = useState<
    Record<string, TrailProgress>
  >({});
  const [nextByTrail, setNextByTrail] = useState<
    Record<string, NextConceptResponse>
  >({});
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [progressLoading, setProgressLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<TrailFilter>("all");
  const [sortMode, setSortMode] = useState<TrailSortMode>("recent");
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(
    null,
  );
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string>("");

  // Cosmetic gamification + pin placeholders, mirrored from the sidebar profile
  // chip. These read from localStorage and never touch backend state. Replace
  // streak/XP with real values when gamification ships, and pins with a
  // backend-backed pin endpoint when one exists.
  const [mounted, setMounted] = useState(false);
  const [streak, setStreak] = useState(0);
  const [xp, setXp] = useState(0);
  const [pinnedIds, setPinnedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    // localStorage is unavailable during SSR, so these cosmetic placeholders must
    // be hydrated after mount (mirrors UserProfileChip). The setState calls here
    // are intentional and run once.
    /* eslint-disable react-hooks/set-state-in-effect */
    setStreak(
      parseInt(localStorage.getItem("colearni.streak") ?? "0", 10) || 0,
    );
    setXp(parseInt(localStorage.getItem("colearni.xp") ?? "0", 10) || 0);
    try {
      const raw = localStorage.getItem(PINNED_STORAGE_KEY);
      const ids: unknown = raw ? JSON.parse(raw) : [];
      if (Array.isArray(ids)) {
        setPinnedIds(
          new Set(ids.filter((id): id is string => typeof id === "string")),
        );
      }
    } catch {
      // Ignore malformed pin storage.
    }
    setMounted(true);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

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
          setError(
            exc instanceof Error ? exc.message : "Could not load workspace",
          );
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

  const progresses = useMemo(
    () => Object.values(progressByTrail),
    [progressByTrail],
  );
  const continueTrail = useMemo(
    () => pickContinueTrail(progresses),
    [progresses],
  );
  const continueNext = continueTrail
    ? nextByTrail[continueTrail.detail.trail.id]
    : undefined;
  const conceptsMastered = useMemo(
    () => progresses.reduce((sum, p) => sum + p.mastered, 0),
    [progresses],
  );

  const sortedTrails = useMemo(
    () => sortTrailsForDashboard(trails, progressByTrail, pinnedIds, sortMode),
    [trails, progressByTrail, pinnedIds, sortMode],
  );

  const counts = useMemo(() => {
    let inProgress = 0;
    let completed = 0;
    for (const trail of trails) {
      const progress = progressByTrail[trail.id];
      if (progress && isFullyMastered(progress)) {
        completed += 1;
      } else if (progress && progress.progress > 0) {
        inProgress += 1;
      }
    }
    return {
      all: trails.length,
      in_progress: inProgress,
      completed,
      pinned: pinnedIds.size,
    };
  }, [trails, progressByTrail, pinnedIds]);

  const filteredTrails = useMemo(() => {
    const q = search.trim().toLowerCase();
    return sortedTrails.filter((trail) => {
      const progress = progressByTrail[trail.id];
      if (filter === "completed" && !(progress && isFullyMastered(progress))) {
        return false;
      }
      if (
        filter === "in_progress" &&
        !(progress && progress.progress > 0 && !isFullyMastered(progress))
      ) {
        return false;
      }
      if (filter === "pinned" && !pinnedIds.has(trail.id)) {
        return false;
      }
      if (!q) {
        return true;
      }
      return (
        trail.title.toLowerCase().includes(q) ||
        trail.topic.toLowerCase().includes(q) ||
        trail.goal.toLowerCase().includes(q)
      );
    });
  }, [sortedTrails, progressByTrail, filter, search, pinnedIds]);

  function togglePin(trailId: string) {
    setPinnedIds((current) => {
      const next = new Set(current);
      if (next.has(trailId)) {
        next.delete(trailId);
      } else {
        next.add(trailId);
      }
      try {
        localStorage.setItem(PINNED_STORAGE_KEY, JSON.stringify([...next]));
      } catch {
        // Ignore storage write failures (e.g. private mode quota).
      }
      return next;
    });
  }

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
    <main className="flex min-h-screen w-full flex-col gap-8 px-4 py-8">
      <WelcomeHeader
        trailCount={trails.length}
        conceptsMastered={conceptsMastered}
        streak={mounted ? streak : null}
        xp={mounted ? xp : null}
      />

      {error ? (
        <div
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {error}
        </div>
      ) : null}

      {loading ? <DashboardSkeleton /> : null}

      {!loading && trails.length === 0 ? <EmptyState /> : null}

      {!loading && trails.length > 0 ? (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <ContinueLearningCard
              progress={continueTrail}
              next={continueNext}
              loadingProgress={progressLoading && progresses.length === 0}
            />
            <RecommendedNextCard
              progress={continueTrail}
              next={continueNext}
              loadingProgress={progressLoading && progresses.length === 0}
            />
          </div>

          <QuickActions trail={continueTrail} next={continueNext} />

          <YourTrailsSection
            trails={filteredTrails}
            totalTrails={trails.length}
            progressByTrail={progressByTrail}
            nextByTrail={nextByTrail}
            pinnedIds={pinnedIds}
            filter={filter}
            counts={counts}
            search={search}
            deleteError={deleteError}
            confirmingDeleteId={confirmingDeleteId}
            deletingId={deletingId}
            sortMode={sortMode}
            onFilter={setFilter}
            onSearch={setSearch}
            onSort={setSortMode}
            onTogglePin={togglePin}
            onAskDelete={setConfirmingDeleteId}
            onCancelDelete={() => setConfirmingDeleteId(null)}
            onConfirmDelete={handleDelete}
          />
        </>
      ) : null}
    </main>
  );
}

function WelcomeHeader({
  trailCount,
  conceptsMastered,
  streak,
  xp,
}: {
  trailCount: number;
  conceptsMastered: number;
  streak: number | null;
  xp: number | null;
}) {
  return (
    <header className="flex flex-col gap-5 border-b border-slate-200 pb-6 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-950 sm:text-3xl">
          Welcome back, {LEARNER_NAME}! <span aria-hidden>👋</span>
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
          Pick up where you left off and learn one concept at a time. Your
          progress, next steps, and Trails are all here.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-slate-200 bg-slate-200 shadow-sm sm:grid-cols-4">
        {(
          [
            {
              icon: <Flame className="h-3.5 w-3.5 text-amber-500" aria-hidden />,
              value: streak === null ? "—" : String(streak),
              label: "day streak",
            },
            {
              icon: <Zap className="h-3.5 w-3.5 text-blue-500" aria-hidden />,
              value: xp === null ? "—" : xp.toLocaleString(),
              label: "XP",
            },
            {
              icon: <Trophy className="h-3.5 w-3.5 text-emerald-500" aria-hidden />,
              value: String(conceptsMastered),
              label: "mastered",
            },
            {
              icon: <Target className="h-3.5 w-3.5 text-slate-400" aria-hidden />,
              value: String(trailCount),
              label: trailCount === 1 ? "trail" : "trails",
            },
          ] as Array<{ icon: React.ReactNode; value: string; label: string }>
        ).map((stat, i) => (
          <div key={i} className="flex min-w-0 items-center gap-1.5 bg-white px-3 py-3 sm:gap-2 sm:px-4">
            {stat.icon}
            <span className="shrink-0 text-sm font-semibold tabular-nums text-slate-950">
              {stat.value}
            </span>
            <span className="min-w-0 truncate text-xs text-slate-400">{stat.label}</span>
          </div>
        ))}
      </div>
    </header>
  );
}


function DashboardSkeleton() {
  return (
    <div className="space-y-6" aria-hidden>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="h-44 animate-pulse rounded-2xl bg-slate-100" />
        <div className="h-44 animate-pulse rounded-2xl bg-slate-100" />
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-24 animate-pulse rounded-xl bg-slate-100" />
        ))}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <section
      data-testid="dashboard-empty"
      className="flex flex-col items-start gap-4 rounded-2xl border border-slate-200 bg-white p-8 shadow-sm"
    >
      <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50">
        <Sparkles className="h-6 w-6 text-blue-600" aria-hidden />
      </span>
      <div>
        <p className="text-lg font-semibold text-slate-950">No Trails yet</p>
        <p className="mt-1.5 max-w-md text-sm leading-6 text-slate-600">
          Create your first Trail to start learning. CoLearni will build a
          concept graph and a Socratic tutor for it.
        </p>
      </div>
      <Link
        href="/trails/new"
        className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white transition-colors hover:bg-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-300"
      >
        <Plus className="h-4 w-4" aria-hidden />
        Create your first Trail
      </Link>
    </section>
  );
}

function ContinueLearningCard({
  progress,
  next,
  loadingProgress,
}: {
  progress: TrailProgress | null;
  next: NextConceptResponse | undefined;
  loadingProgress: boolean;
}) {
  if (loadingProgress) {
    return (
      <CardShell>
        <CardEyebrow>Continue Learning</CardEyebrow>
        <p className="mt-3 text-sm text-slate-500">Loading progress…</p>
      </CardShell>
    );
  }

  if (!progress) {
    return (
      <CardShell>
        <CardEyebrow>Continue Learning</CardEyebrow>
        <p className="mt-3 text-sm text-slate-500">
          Pick a Trail below to start learning.
        </p>
      </CardShell>
    );
  }

  const allDone = isFullyMastered(progress);
  const pct = Math.round(progress.progress * 100);
  const trail = progress.detail.trail;
  const href =
    next?.concept_id && !next.all_mastered
      ? `/trails/${trail.id}?concept=${next.concept_id}`
      : `/trails/${trail.id}`;

  return (
    <CardShell className="flex flex-col">
      <div className="flex items-start gap-3">
        <TrailGlyph title={trail.title} />
        <div className="min-w-0 flex-1">
          <CardEyebrow>
            {allDone ? "All concepts mastered" : "Continue Learning"}
          </CardEyebrow>
          <h3 className="mt-1 truncate text-lg font-semibold text-slate-950">
            {trail.title}
          </h3>
          <p className="mt-0.5 line-clamp-1 text-sm text-slate-500">
            {trail.goal}
          </p>
        </div>
      </div>

      <div className="mt-4">
        <div className="mb-1.5 flex items-center justify-between text-xs font-medium text-slate-500">
          <span>{pct}% complete</span>
          <span>
            {progress.mastered}/{progress.total} mastered
          </span>
        </div>
        <SegmentedProgress progress={progress} />
      </div>

      <div className="mt-auto flex flex-wrap gap-2 pt-5">
        <Link
          href={href}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white transition-colors hover:bg-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-300"
        >
          <Play className="h-4 w-4" aria-hidden />
          {allDone ? "Review Trail" : "Continue Learning"}
        </Link>
        <Link
          href={`/trails/${trail.id}`}
          className="inline-flex h-10 items-center justify-center rounded-lg border border-slate-200 bg-white px-4 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
        >
          View graph
        </Link>
      </div>
    </CardShell>
  );
}

function RecommendedNextCard({
  progress,
  next,
  loadingProgress,
}: {
  progress: TrailProgress | null;
  next: NextConceptResponse | undefined;
  loadingProgress: boolean;
}) {
  if (loadingProgress) {
    return (
      <CardShell>
        <CardEyebrow>Recommended Next</CardEyebrow>
        <p className="mt-3 text-sm text-slate-500">Finding your next step…</p>
      </CardShell>
    );
  }

  const trail = progress?.detail.trail;
  const hasConcept = Boolean(next?.concept_id) && !next?.all_mastered;
  const allMastered =
    next?.all_mastered || (progress && isFullyMastered(progress));

  return (
    <CardShell className="flex flex-col">
      <div className="flex items-start gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-50">
          <Sparkles className="h-5 w-5 text-blue-600" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <CardEyebrow>Recommended Next</CardEyebrow>
          <h3 className="mt-1 truncate text-lg font-semibold text-slate-950">
            {hasConcept
              ? (next?.concept_title ?? "Next concept")
              : allMastered
                ? "You're all caught up"
                : "Open a Trail to begin"}
          </h3>
          {trail ? (
            <p className="mt-0.5 truncate text-sm text-slate-500">
              in {trail.title}
            </p>
          ) : null}
        </div>
      </div>

      <p className="mt-4 line-clamp-3 text-sm leading-6 text-slate-600">
        {next?.reason
          ? next.reason
          : allMastered
            ? "Every concept here is mastered. Try a deeper Trail or explore adjacent topics."
            : "We'll recommend a concept once you've started a Trail."}
      </p>

      <div className="mt-auto pt-5">
        {hasConcept && trail ? (
          <Link
            href={`/trails/${trail.id}?concept=${next?.concept_id}`}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-4 text-sm font-medium text-blue-700 transition-colors hover:bg-blue-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-300"
          >
            {primaryCtaLabelFor(next?.mastery_status)}
            <ArrowRight className="h-4 w-4" aria-hidden />
          </Link>
        ) : allMastered ? (
          <Link
            href="/explore"
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
          >
            <Compass className="h-4 w-4" aria-hidden />
            Explore adjacent topics
          </Link>
        ) : (
          <Link
            href="/trails"
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
          >
            Browse Trails
            <ArrowRight className="h-4 w-4" aria-hidden />
          </Link>
        )}
      </div>
    </CardShell>
  );
}

function QuickActions({
  trail,
  next,
}: {
  trail: TrailProgress | null;
  next: NextConceptResponse | undefined;
}) {
  const trailId = trail?.detail.trail.id;
  const conceptHref =
    trailId && next?.concept_id
      ? `/trails/${trailId}?concept=${next.concept_id}`
      : trailId
        ? `/trails/${trailId}`
        : "/trails";

  const actions: {
    icon: React.ReactNode;
    title: string;
    sub: string;
    href: string;
  }[] = [
    {
      icon: <Target className="h-5 w-5" aria-hidden />,
      title: "Review weak areas",
      sub: "Shore up concepts to revisit",
      href: trailId ? `/trails/${trailId}` : "/progress",
    },
    {
      icon: <Trophy className="h-5 w-5" aria-hidden />,
      title: "Level up quiz",
      sub: "Prove mastery and advance",
      href: "/quizzes",
    },
    {
      icon: <Compass className="h-5 w-5" aria-hidden />,
      title: "Explore adjacent",
      sub: "Discover related topics",
      href: "/explore",
    },
    {
      icon: <MessageCircleQuestion className="h-5 w-5" aria-hidden />,
      title: "Ask anything",
      sub: "Chat with your Socratic tutor",
      href: conceptHref,
    },
  ];

  return (
    <section
      aria-label="Quick actions"
      className="grid grid-cols-2 gap-3 sm:grid-cols-4"
    >
      {actions.map((action) => (
        <Link
          key={action.title}
          href={action.href}
          className="group flex flex-col gap-2.5 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-colors hover:border-blue-200 hover:bg-blue-50/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-300"
        >
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-blue-600 transition-colors group-hover:bg-blue-600 group-hover:text-white">
            {action.icon}
          </span>
          <span className="text-sm font-semibold text-slate-900">
            {action.title}
          </span>
          <span className="text-xs leading-5 text-slate-500">{action.sub}</span>
        </Link>
      ))}
    </section>
  );
}

function YourTrailsSection({
  trails,
  totalTrails,
  progressByTrail,
  nextByTrail,
  pinnedIds,
  filter,
  sortMode,
  counts,
  search,
  deleteError,
  confirmingDeleteId,
  deletingId,
  onFilter,
  onSearch,
  onSort,
  onTogglePin,
  onAskDelete,
  onCancelDelete,
  onConfirmDelete,
}: {
  trails: Trail[];
  totalTrails: number;
  progressByTrail: Record<string, TrailProgress>;
  nextByTrail: Record<string, NextConceptResponse>;
  pinnedIds: Set<string>;
  filter: TrailFilter;
  sortMode: TrailSortMode;
  counts: Record<TrailFilter, number>;
  search: string;
  deleteError: string;
  confirmingDeleteId: string | null;
  deletingId: string | null;
  onFilter: (filter: TrailFilter) => void;
  onSearch: (value: string) => void;
  onSort: (mode: TrailSortMode) => void;
  onTogglePin: (id: string) => void;
  onAskDelete: (id: string) => void;
  onCancelDelete: () => void;
  onConfirmDelete: (id: string) => void;
}) {
  const chips: { key: TrailFilter; label: string }[] = [
    { key: "all", label: "All" },
    { key: "in_progress", label: "In Progress" },
    { key: "completed", label: "Completed" },
    { key: "pinned", label: "Pinned" },
  ];

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Your Trails</h2>
          <p className="mt-1 text-xs text-slate-500">
            Pinned Trails stay at the top.
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <input
            aria-label="Search Trails"
            value={search}
            onChange={(e) => onSearch(e.target.value)}
            placeholder="Search Trails…"
            className="h-9 w-full rounded-lg border border-slate-300 px-3 text-sm outline-none transition-colors focus:border-blue-500 focus:ring-2 focus:ring-blue-100 sm:w-64"
          />
          <select
            aria-label="Sort Trails"
            value={sortMode}
            onChange={(event) => onSort(event.target.value as TrailSortMode)}
            className="h-9 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-700 outline-none transition-colors focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {chips.map((chip) => {
          const active = filter === chip.key;
          return (
            <button
              key={chip.key}
              type="button"
              onClick={() => onFilter(chip.key)}
              aria-pressed={active}
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-300 ${
                active
                  ? "border-blue-600 bg-blue-600 text-white"
                  : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900"
              }`}
            >
              {chip.label}
              <span
                className={`rounded-full px-1.5 text-[10px] font-semibold ${
                  active
                    ? "bg-blue-500/40 text-white"
                    : "bg-slate-100 text-slate-500"
                }`}
              >
                {counts[chip.key]}
              </span>
            </button>
          );
        })}
      </div>

      {deleteError ? (
        <p className="text-sm text-red-700">{deleteError}</p>
      ) : null}

      {trails.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-200 bg-slate-50/60 px-4 py-8 text-center text-sm text-slate-500">
          {totalTrails === 0
            ? "No Trails yet."
            : "No Trails match this filter."}
        </p>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {trails.map((trail) => (
            <li key={trail.id}>
              <TrailCard
                trail={trail}
                progress={progressByTrail[trail.id]}
                next={nextByTrail[trail.id]}
                pinned={pinnedIds.has(trail.id)}
                confirming={confirmingDeleteId === trail.id}
                deleting={deletingId === trail.id}
                onTogglePin={() => onTogglePin(trail.id)}
                onAskDelete={() => onAskDelete(trail.id)}
                onCancelDelete={onCancelDelete}
                onConfirmDelete={() => onConfirmDelete(trail.id)}
              />
            </li>
          ))}
          <li>
            <CreateTrailCard />
          </li>
        </ul>
      )}
    </section>
  );
}

function CreateTrailCard() {
  return (
    <Link
      href="/trails/new"
      className="group flex h-full min-h-44 flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed border-slate-200 bg-slate-50/40 p-5 text-center transition-colors hover:border-blue-300 hover:bg-blue-50/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-300"
    >
      <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-white text-blue-600 ring-1 ring-slate-200 transition-colors group-hover:bg-blue-600 group-hover:text-white group-hover:ring-blue-600">
        <Plus className="h-5 w-5" aria-hidden />
      </span>
      <span className="text-sm font-semibold text-slate-900">
        Create New Trail
      </span>
      <span className="text-xs text-slate-500">Start learning a new topic</span>
    </Link>
  );
}

function TrailCard({
  trail,
  progress,
  next,
  pinned,
  confirming,
  deleting,
  onTogglePin,
  onAskDelete,
  onCancelDelete,
  onConfirmDelete,
}: {
  trail: Trail;
  progress: TrailProgress | undefined;
  next: NextConceptResponse | undefined;
  pinned: boolean;
  confirming: boolean;
  deleting: boolean;
  onTogglePin: () => void;
  onAskDelete: () => void;
  onCancelDelete: () => void;
  onConfirmDelete: () => void;
}) {
  const status = trailStatus(progress);
  const pct = progress ? Math.round(progress.progress * 100) : 0;
  const startHref =
    next?.concept_id && !next.all_mastered
      ? `/trails/${trail.id}?concept=${next.concept_id}`
      : `/trails/${trail.id}`;

  return (
    <div className="flex h-full flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-colors hover:border-slate-300">
      <div className="flex items-start gap-3">
        <TrailGlyph title={trail.title} />
        <Link href={`/trails/${trail.id}`} className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-semibold text-slate-950">
            {trail.title}
          </h3>
          <p className="mt-0.5 line-clamp-2 text-xs leading-5 text-slate-500">
            {trail.goal}
          </p>
        </Link>
        <button
          type="button"
          onClick={onTogglePin}
          aria-pressed={pinned}
          aria-label={pinned ? `Unpin ${trail.title}` : `Pin ${trail.title}`}
          title={pinned ? "Unpin Trail" : "Pin Trail"}
          className={`inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-200 ${
            pinned
              ? "text-blue-600 hover:bg-blue-50"
              : "text-slate-300 hover:bg-slate-50 hover:text-slate-500"
          }`}
        >
          {pinned ? (
            <Pin className="h-4 w-4 fill-current" aria-hidden />
          ) : (
            <PinOff className="h-4 w-4" aria-hidden />
          )}
        </button>
      </div>

      <div className="mt-4">
        {progress ? (
          <>
            <div className="mb-1.5 flex items-center justify-between text-[11px] font-medium text-slate-500">
              <span>{pct}% complete</span>
              <span>
                {progress.mastered}/{progress.total} mastered
              </span>
            </div>
            <SegmentedProgress progress={progress} />
          </>
        ) : (
          <p className="text-xs text-slate-500">
            {trail.node_count} concepts · {trail.edge_count} edges
          </p>
        )}
      </div>

      <div className="mt-4 flex items-center justify-between gap-2 border-t border-slate-100 pt-4">
        <StatusPill status={status} />
        <div className="flex items-center gap-1">
          {next?.concept_id && !next.all_mastered ? (
            <Link
              href={startHref}
              title="Start recommended concept"
              className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg bg-blue-600 px-3 text-xs font-medium text-white transition-colors hover:bg-blue-700"
            >
              <Play className="h-3.5 w-3.5" aria-hidden />
              Continue
            </Link>
          ) : (
            <Link
              href={`/trails/${trail.id}`}
              className="inline-flex h-8 items-center justify-center rounded-lg border border-slate-200 px-3 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50"
            >
              Open
            </Link>
          )}
          {confirming ? (
            <div className="flex items-center gap-1.5 pl-1 text-xs">
              <button
                type="button"
                onClick={onConfirmDelete}
                disabled={deleting}
                className="font-medium text-red-600 hover:text-red-800 disabled:opacity-50"
              >
                {deleting ? "Deleting…" : "Confirm"}
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
              aria-label={`Delete ${trail.title}`}
              title="Delete Trail"
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-100"
            >
              <Trash2 className="h-4 w-4" aria-hidden />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function CardShell({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <article
      className={`rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6 ${className}`}
    >
      {children}
    </article>
  );
}

function CardEyebrow({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">
      {children}
    </p>
  );
}

function TrailGlyph({ title }: { title: string }) {
  const initial = title.trim().charAt(0).toUpperCase() || "T";
  return (
    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-base font-semibold text-white">
      {initial}
    </span>
  );
}

type TrailStatusKey = "completed" | "in_progress" | "not_started";

function trailStatus(progress: TrailProgress | undefined): TrailStatusKey {
  if (progress && isFullyMastered(progress)) {
    return "completed";
  }
  if (progress && progress.progress > 0) {
    return "in_progress";
  }
  return "not_started";
}

function StatusPill({ status }: { status: TrailStatusKey }) {
  const config: Record<TrailStatusKey, { label: string; className: string }> = {
    completed: {
      label: "Completed",
      className: "border-emerald-200 bg-emerald-50 text-emerald-700",
    },
    in_progress: {
      label: "In progress",
      className: "border-blue-200 bg-blue-50 text-blue-700",
    },
    not_started: {
      label: "Not started",
      className: "border-slate-200 bg-slate-50 text-slate-600",
    },
  };
  const { label, className } = config[status];
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${className}`}
    >
      {label}
    </span>
  );
}

function primaryCtaLabelFor(status: string | null | undefined): string {
  switch (status) {
    case "learning":
      return "Continue Tutor";
    case "needs_review":
      return "Review Weak Points";
    case "mastered":
      return "Practice / Explore Further";
    default:
      return "Start Learning";
  }
}

function SegmentedProgress({ progress }: { progress: TrailProgress }) {
  const total = Math.max(progress.total, 1);
  const masteredPct = (progress.mastered / total) * 100;
  const learningPct = (progress.learning / total) * 100;
  const reviewPct = (progress.needs_review / total) * 100;
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
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-500">
        <LegendDot
          className="bg-emerald-500"
          label={`Mastered ${progress.mastered}`}
        />
        <LegendDot
          className="bg-blue-400"
          label={`Learning ${progress.learning}`}
        />
        <LegendDot
          className="bg-amber-400"
          label={`Review ${progress.needs_review}`}
        />
        <LegendDot
          className="bg-slate-300"
          label={`New ${progress.not_started}`}
        />
      </div>
    </div>
  );
}

function LegendDot({ className, label }: { className: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`h-2 w-2 rounded-full ${className}`} aria-hidden />
      {label}
    </span>
  );
}
