import { describe, expect, test } from "vitest";

import { pickContinueTrail, pickRecommendedConcept, summarizeTrail } from "@/lib/recommendation";
import type {
  ConceptEdge,
  ConceptLevel,
  ConceptNode,
  Difficulty,
  MasteryRecord,
  MasteryStatus,
  TrailDetail,
} from "@/lib/types";

function node(
  id: string,
  overrides: Partial<ConceptNode> & { level?: ConceptLevel; difficulty?: Difficulty } = {},
): ConceptNode {
  return {
    id,
    trail_id: "trail-1",
    slug: id,
    title: overrides.title ?? id,
    node_type: "concept",
    concept_level: overrides.level ?? "topic",
    difficulty: overrides.difficulty ?? "beginner",
    bloom_level: "understand",
    mastery_check_labels: [],
    metadata_json: {},
  };
}

function edge(source: string, target: string): ConceptEdge {
  return {
    id: `${source}->${target}`,
    trail_id: "trail-1",
    source_node_id: source,
    target_node_id: target,
    relation_type: "prerequisite",
  };
}

function mastery(
  concept_id: string,
  status: MasteryStatus,
  updated_at: string | null = null,
): MasteryRecord {
  return {
    id: null,
    workspace_id: "workspace-1",
    concept_id,
    status,
    bloom_level: "understand",
    score: status === "mastered" ? 1 : status === "learning" ? 0.5 : 0,
    updated_at,
  };
}

describe("pickRecommendedConcept", () => {
  test("returns null when there are no nodes", () => {
    expect(pickRecommendedConcept([], [], {})).toBeNull();
  });

  test("prefers needs_review over learning over not_started over mastered", () => {
    const nodes = [
      node("a"),
      node("b"),
      node("c"),
      node("d"),
    ];
    const rec = pickRecommendedConcept(nodes, [], {
      a: mastery("a", "not_started"),
      b: mastery("b", "learning"),
      c: mastery("c", "needs_review"),
      d: mastery("d", "mastered"),
    });
    expect(rec?.concept.id).toBe("c");
    expect(rec?.status).toBe("needs_review");
  });

  test("falls back to review/extension when every concept is mastered", () => {
    const nodes = [
      node("a", { difficulty: "advanced", title: "Advanced" }),
      node("b", { difficulty: "beginner", title: "Beginner" }),
    ];
    const rec = pickRecommendedConcept(nodes, [], {
      a: mastery("a", "mastered"),
      b: mastery("b", "mastered"),
    });
    // Lower difficulty wins on tiebreak when all mastered.
    expect(rec?.concept.id).toBe("b");
    expect(rec?.status).toBe("mastered");
    expect(rec?.reason).toMatch(/mastered/i);
  });

  test("prefers candidates whose prerequisites are mastered/learning", () => {
    const nodes = [
      node("intro", { title: "Intro" }),
      node("advanced", { title: "Advanced" }),
    ];
    const edges = [edge("intro", "advanced")];
    // Both not_started, but "advanced" has an unstarted prereq, so "intro" wins.
    const rec = pickRecommendedConcept(nodes, edges, {});
    expect(rec?.concept.id).toBe("intro");
  });

  test("prefers topic > subtopic > umbrella > granular when status ties", () => {
    const nodes = [
      node("u", { level: "umbrella", title: "U" }),
      node("t", { level: "topic", title: "T" }),
      node("s", { level: "subtopic", title: "S" }),
      node("g", { level: "granular", title: "G" }),
    ];
    const rec = pickRecommendedConcept(nodes, [], {});
    expect(rec?.concept.id).toBe("t");
  });
});

describe("summarizeTrail + pickContinueTrail", () => {
  function makeDetail(
    id: string,
    summary: { mastered: number; learning: number; needs_review: number; not_started: number },
    created_at: string,
    latestActivity: string | null,
  ): TrailDetail {
    const total =
      summary.mastered + summary.learning + summary.needs_review + summary.not_started;
    return {
      trail: {
        id,
        workspace_id: "workspace-1",
        title: id,
        topic: id,
        goal: id,
        target_depth: "understand",
        created_at,
        node_count: total,
        edge_count: 0,
      },
      graph: {
        nodes: [],
        edges: [],
        mastery: latestActivity
          ? { x: mastery("x", "learning", latestActivity) }
          : {},
      },
      mastery_summary: { total, ...summary },
    };
  }

  test("weights mastered=1, learning=0.5, needs_review=0.25", () => {
    const detail = makeDetail(
      "t",
      { mastered: 2, learning: 2, needs_review: 4, not_started: 2 },
      "2026-01-01T00:00:00Z",
      null,
    );
    const p = summarizeTrail(detail);
    // (2 + 2*0.5 + 4*0.25) / 10 = 4/10
    expect(p.progress).toBeCloseTo(0.4, 5);
  });

  test("pickContinueTrail prefers most recent lastActivity", () => {
    const a = summarizeTrail(
      makeDetail("a", { mastered: 0, learning: 1, needs_review: 0, not_started: 0 }, "2026-01-01T00:00:00Z", "2026-05-01T00:00:00Z"),
    );
    const b = summarizeTrail(
      makeDetail("b", { mastered: 0, learning: 1, needs_review: 0, not_started: 0 }, "2026-01-01T00:00:00Z", "2026-05-20T00:00:00Z"),
    );
    expect(pickContinueTrail([a, b])?.detail.trail.id).toBe("b");
  });

  test("pickContinueTrail falls back to most progress when no activity timestamps", () => {
    const fresh = summarizeTrail(
      makeDetail("fresh", { mastered: 0, learning: 0, needs_review: 0, not_started: 5 }, "2026-01-02T00:00:00Z", null),
    );
    const started = summarizeTrail(
      makeDetail("started", { mastered: 1, learning: 1, needs_review: 0, not_started: 3 }, "2026-01-01T00:00:00Z", null),
    );
    expect(pickContinueTrail([fresh, started])?.detail.trail.id).toBe("started");
  });

  test("pickContinueTrail falls back to newest trail when nothing started", () => {
    const older = summarizeTrail(
      makeDetail("older", { mastered: 0, learning: 0, needs_review: 0, not_started: 3 }, "2026-01-01T00:00:00Z", null),
    );
    const newer = summarizeTrail(
      makeDetail("newer", { mastered: 0, learning: 0, needs_review: 0, not_started: 3 }, "2026-02-01T00:00:00Z", null),
    );
    expect(pickContinueTrail([older, newer])?.detail.trail.id).toBe("newer");
  });
});
