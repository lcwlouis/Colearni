"use client";
import { useState, useCallback, useEffect } from "react";

const STORAGE_KEY = "colearni:showDevStats";

export function useDevStats() {
  const [showDevStats, setShowDevStats] = useState(false);

  useEffect(() => {
    try {
      setShowDevStats(localStorage.getItem(STORAGE_KEY) === "true");
    } catch {}
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
