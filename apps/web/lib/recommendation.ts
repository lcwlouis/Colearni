import type { TrailDetail } from "@/lib/types";

export interface TrailProgress {
  detail: TrailDetail;
  total: number;
  mastered: number;
  learning: number;
  needs_review: number;
  not_started: number;
  /** 0..1 weighted progress; mastered counts full, learning counts half. */
  progress: number;
  /** Most recently touched concept status timestamp, when available. */
  lastActivity: string | null;
}

/** True when every concept in the trail has been mastered. */
export function isFullyMastered(progress: TrailProgress): boolean {
  return progress.total > 0 && progress.mastered >= progress.total;
}

export function summarizeTrail(detail: TrailDetail): TrailProgress {
  const summary = detail.mastery_summary;
  const total = Math.max(summary.total, 1);
  const progress =
    (summary.mastered + summary.learning * 0.5 + summary.needs_review * 0.25) / total;
  let lastActivity: string | null = null;
  for (const rec of Object.values(detail.graph.mastery)) {
    if (rec.updated_at && (!lastActivity || rec.updated_at > lastActivity)) {
      lastActivity = rec.updated_at;
    }
  }
  return {
    detail,
    total: summary.total,
    mastered: summary.mastered,
    learning: summary.learning,
    needs_review: summary.needs_review,
    not_started: summary.not_started,
    progress,
    lastActivity,
  };
}

/**
 * Pick the Trail to surface as "Continue Learning".
 *
 * Fully-mastered trails are excluded from the candidate pool so that the
 * section always points to a trail that still has learning to do. If every
 * trail is fully mastered the section falls back to the most recently active
 * trail (the user still deserves to see their work) but the caller can use
 * `isFullyMastered` to render a different "all done" state in that case.
 */
export function pickContinueTrail(progresses: TrailProgress[]): TrailProgress | null {
  if (progresses.length === 0) {
    return null;
  }

  // Prefer trails that still have learning to do.
  const active = progresses.filter((p) => !isFullyMastered(p));
  // Fall back to the full list only if everything is mastered.
  const pool = active.length > 0 ? active : progresses;

  const withActivity = pool
    .filter((p) => p.lastActivity)
    .sort((a, b) => (b.lastActivity ?? "").localeCompare(a.lastActivity ?? ""));
  if (withActivity.length > 0) {
    return withActivity[0];
  }
  const inProgress = pool
    .filter((p) => p.learning + p.needs_review + p.mastered > 0)
    .sort((a, b) => b.progress - a.progress);
  if (inProgress.length > 0) {
    return inProgress[0];
  }
  return [...pool].sort((a, b) =>
    b.detail.trail.created_at.localeCompare(a.detail.trail.created_at),
  )[0];
}
