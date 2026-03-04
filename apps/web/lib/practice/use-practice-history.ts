import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";
import type {
  PracticeQuizHistoryEntry,
  FlashcardRunSummary,
} from "@/lib/api/types";

export interface PracticeHistoryData {
  quizzes: PracticeQuizHistoryEntry[];
  flashcardRuns: FlashcardRunSummary[];
}

/**
 * Fetches past practice quiz and flashcard run history for a given
 * workspace, optionally scoped to a concept.
 */
export function usePracticeHistory(
  workspaceId: string | undefined,
  conceptId: number | null,
) {
  const [data, setData] = useState<PracticeHistoryData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!workspaceId) return;
    setLoading(true);
    setError(null);
    try {
      const [quizRes, flashRes] = await Promise.all([
        apiClient.listPracticeQuizzes(workspaceId, conceptId ?? undefined),
        apiClient.listFlashcardRuns(workspaceId, conceptId ?? undefined),
      ]);
      setData({
        quizzes: quizRes.quizzes,
        flashcardRuns: flashRes.runs,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load history");
    } finally {
      setLoading(false);
    }
  }, [workspaceId, conceptId]);

  useEffect(() => {
    if (workspaceId) {
      refresh();
    } else {
      setData(null);
    }
  }, [workspaceId, conceptId, refresh]);

  return { data, loading, error, refresh };
}
