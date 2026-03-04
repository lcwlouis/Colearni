"use client";
import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api/client";

export function useDevStats() {
  const [showDevStats, setShowDevStats] = useState(false);

  useEffect(() => {
    apiClient.getFeatureFlags()
      .then((flags) => setShowDevStats(flags.include_dev_stats))
      .catch(() => setShowDevStats(false));
  }, []);

  return { showDevStats };
}
