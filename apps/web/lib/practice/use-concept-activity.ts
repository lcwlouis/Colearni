/**
 * Shared concept-activity data hook (AR7.1).
 *
 * Provides a single hook for graph and tutor surfaces to fetch
 * aggregate study activity for a concept.
 */

"use client";

import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/lib/api/client";
import type { ConceptActivityResponse } from "@/lib/api/types";

export interface UseConceptActivityResult {
  activity: ConceptActivityResponse | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useConceptActivity(
  workspaceId: string | undefined,
  conceptId: number | undefined,
): UseConceptActivityResult {
  const [activity, setActivity] = useState<ConceptActivityResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!workspaceId || !conceptId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.getConceptActivity(workspaceId, conceptId);
      setActivity(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch concept activity");
    } finally {
      setLoading(false);
    }
  }, [workspaceId, conceptId]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { activity, loading, error, refetch: fetch };
}
