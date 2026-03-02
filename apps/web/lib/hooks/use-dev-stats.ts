"use client";
import { useState, useCallback, useEffect } from "react";
import { apiClient } from "@/lib/api/client";

const STORAGE_KEY = "colearni:showDevStats";

export function useDevStats() {
  const [showDevStats, setShowDevStats] = useState(false);

  useEffect(() => {
    // Prefer backend feature flag; fall back to localStorage override
    apiClient.getFeatureFlags()
      .then((flags) => {
        const localOverride = localStorage.getItem(STORAGE_KEY);
        setShowDevStats(localOverride !== null ? localOverride === "true" : flags.include_dev_stats);
      })
      .catch(() => {
        try {
          setShowDevStats(localStorage.getItem(STORAGE_KEY) === "true");
        } catch {}
      });
  }, []);

  const toggleDevStats = useCallback(() => {
    setShowDevStats(prev => {
      const next = !prev;
      try { localStorage.setItem(STORAGE_KEY, String(next)); } catch {}
      return next;
    });
  }, []);

  return { showDevStats, toggleDevStats };
}
