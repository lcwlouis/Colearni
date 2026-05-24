import type {
  ConceptEdge,
  ConceptLevel,
  ConceptNode,
  Difficulty,
  MasteryRecord,
  MasteryStatus,
  TrailDetail,
} from "@/lib/types";

export interface RecommendedConcept {
  concept: ConceptNode;
  status: MasteryStatus;
  reason: string;
}

const LEVEL_PRIORITY: Record<ConceptLevel, number> = {
  topic: 0,
  subtopic: 1,
  umbrella: 2,
  granular: 3,
};

const DIFFICULTY_PRIORITY: Record<Difficulty, number> = {
  beginner: 0,
  intermediate: 1,
  advanced: 2,
};

const STATUS_PRIORITY: Record<MasteryStatus, number> = {
  needs_review: 0,
  learning: 1,
  not_started: 2,
  mastered: 3,
};

function statusOf(node: ConceptNode, mastery: Record<string, MasteryRecord>): MasteryStatus {
  return mastery[node.id]?.status ?? "not_started";
}

/**
 * Deterministic V1 "Recommended Next" pick.
 *
 * Priority order:
 *  1. Prefer `needs_review`, then `learning`, then `not_started`. If all are
 *     `mastered`, fall back to the lowest-difficulty mastered concept so we
 *     can suggest review / extension.
 *  2. Prefer concepts whose prerequisites are all `mastered` or `learning`.
 *  3. Prefer `topic` > `subtopic` > `umbrella` > `granular`.
 *  4. Prefer lower difficulty.
 *  5. Stable tiebreak on title for determinism.
 */
export function pickRecommendedConcept(
  nodes: ConceptNode[],
  edges: ConceptEdge[],
  mastery: Record<string, MasteryRecord>,
): RecommendedConcept | null {
  if (nodes.length === 0) {
    return null;
  }

  // Prerequisite map: concept_id -> list of prerequisite concept_ids
  const prereqsOf = new Map<string, string[]>();
  for (const edge of edges) {
    if (edge.relation_type !== "prerequisite") {
      continue;
    }
    // prerequisite edges go: source is a prerequisite for target
    const list = prereqsOf.get(edge.target_node_id) ?? [];
    list.push(edge.source_node_id);
    prereqsOf.set(edge.target_node_id, list);
  }

  const allMastered = nodes.every((n) => statusOf(n, mastery) === "mastered");

  const candidates = nodes.filter((n) => {
    const status = statusOf(n, mastery);
    return allMastered ? true : status !== "mastered";
  });

  if (candidates.length === 0) {
    return null;
  }

  function prereqsReady(node: ConceptNode): boolean {
    const prereqs = prereqsOf.get(node.id) ?? [];
    if (prereqs.length === 0) {
      return true;
    }
    return prereqs.every((pid) => {
      const s = mastery[pid]?.status ?? "not_started";
      return s === "mastered" || s === "learning";
    });
  }

  const sorted = [...candidates].sort((a, b) => {
    const sA = statusOf(a, mastery);
    const sB = statusOf(b, mastery);
    const statusDelta = STATUS_PRIORITY[sA] - STATUS_PRIORITY[sB];
    if (statusDelta !== 0) {
      return statusDelta;
    }
    const readyDelta = (prereqsReady(a) ? 0 : 1) - (prereqsReady(b) ? 0 : 1);
    if (readyDelta !== 0) {
      return readyDelta;
    }
    const levelDelta = LEVEL_PRIORITY[a.concept_level] - LEVEL_PRIORITY[b.concept_level];
    if (levelDelta !== 0) {
      return levelDelta;
    }
    const diffDelta = DIFFICULTY_PRIORITY[a.difficulty] - DIFFICULTY_PRIORITY[b.difficulty];
    if (diffDelta !== 0) {
      return diffDelta;
    }
    return a.title.localeCompare(b.title);
  });

  const top = sorted[0];
  const topStatus = statusOf(top, mastery);
  return {
    concept: top,
    status: topStatus,
    reason: reasonFor(topStatus, prereqsReady(top), allMastered),
  };
}

function reasonFor(status: MasteryStatus, ready: boolean, allMastered: boolean): string {
  if (allMastered) {
    return "All concepts mastered — review or explore further.";
  }
  if (status === "needs_review") {
    return "Marked for review — revisit weak points.";
  }
  if (status === "learning") {
    return "Continue where you left off.";
  }
  if (!ready) {
    return "Prerequisites not yet started — but a good next step.";
  }
  return "Prerequisites ready — good next step.";
}

export interface TrailProgress {
  detail: TrailDetail;
  total: number;
  mastered: number;
  learning: number;
  needs_review: number;
  not_started: number;
  /** 0..1 weighted progress; mastered counts full, learning counts half. */
  progress: number;
  recommended: RecommendedConcept | null;
  /** Most recently touched concept status timestamp, when available. */
  lastActivity: string | null;
}

export function summarizeTrail(detail: TrailDetail): TrailProgress {
  const summary = detail.mastery_summary;
  const total = Math.max(summary.total, 1);
  const progress =
    (summary.mastered + summary.learning * 0.5 + summary.needs_review * 0.25) / total;
  const recommended = pickRecommendedConcept(
    detail.graph.nodes,
    detail.graph.edges,
    detail.graph.mastery,
  );
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
    recommended,
    lastActivity,
  };
}

/**
 * Pick the Trail to surface as "Continue Learning".
 *
 * Prefer trails with the most recent activity. If none have activity, prefer
 * trails with any non-`not_started` work. Fall back to the newest Trail.
 */
export function pickContinueTrail(progresses: TrailProgress[]): TrailProgress | null {
  if (progresses.length === 0) {
    return null;
  }
  const withActivity = progresses
    .filter((p) => p.lastActivity)
    .sort((a, b) => (b.lastActivity ?? "").localeCompare(a.lastActivity ?? ""));
  if (withActivity.length > 0) {
    return withActivity[0];
  }
  const inProgress = progresses
    .filter((p) => p.learning + p.needs_review + p.mastered > 0)
    .sort((a, b) => b.progress - a.progress);
  if (inProgress.length > 0) {
    return inProgress[0];
  }
  const newest = [...progresses].sort((a, b) =>
    b.detail.trail.created_at.localeCompare(a.detail.trail.created_at),
  );
  return newest[0];
}
