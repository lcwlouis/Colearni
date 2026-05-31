import type { TrailProgress } from "@/lib/recommendation";
import type { Trail } from "@/lib/types";

export type TrailSortMode =
  | "recent"
  | "created_desc"
  | "created_asc"
  | "mastery_desc"
  | "mastery_asc";

export function sortTrailsForDashboard(
  trails: Trail[],
  progressByTrail: Record<string, TrailProgress>,
  pinnedIds: Set<string>,
  sortMode: TrailSortMode,
): Trail[] {
  return [...trails].sort((left, right) => {
    const leftPinned = pinnedIds.has(left.id);
    const rightPinned = pinnedIds.has(right.id);
    if (leftPinned !== rightPinned) {
      return leftPinned ? -1 : 1;
    }

    const leftProgress = progressByTrail[left.id];
    const rightProgress = progressByTrail[right.id];
    const leftRecent = leftProgress?.lastActivity ?? left.created_at ?? "";
    const rightRecent = rightProgress?.lastActivity ?? right.created_at ?? "";
    const leftMastery = leftProgress?.progress ?? 0;
    const rightMastery = rightProgress?.progress ?? 0;

    switch (sortMode) {
      case "created_asc":
        return compareTrailDate(left.created_at, right.created_at);
      case "created_desc":
        return compareTrailDate(right.created_at, left.created_at);
      case "mastery_asc":
        return (
          compareNumber(leftMastery, rightMastery) ||
          compareTrailDate(rightRecent, leftRecent) ||
          left.title.localeCompare(right.title)
        );
      case "mastery_desc":
        return (
          compareNumber(rightMastery, leftMastery) ||
          compareTrailDate(rightRecent, leftRecent) ||
          left.title.localeCompare(right.title)
        );
      case "recent":
      default:
        return (
          compareTrailDate(rightRecent, leftRecent) ||
          compareTrailDate(right.created_at, left.created_at) ||
          left.title.localeCompare(right.title)
        );
    }
  });
}

function compareTrailDate(left: string, right: string) {
  return left.localeCompare(right);
}

function compareNumber(left: number, right: number) {
  return left - right;
}
