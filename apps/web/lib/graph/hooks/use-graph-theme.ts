"use client";

import { useState, useEffect, useMemo } from "react";

export interface GraphTheme {
  labelColor: string;
  defaultEdgeColor: string;
  defaultNodeColor: string;
  dimmedNodeColor: string;
  highlightEdgeColor: string;
  selectionBorderColor: string;
  /** Background fill for the hover/highlighted label box. */
  hoverBackgroundColor: string;
  /** Shadow colour for the hover/highlighted label box. */
  hoverShadowColor: string;
  isDark: boolean;
}

const LIGHT: GraphTheme = {
  labelColor: "#1a2e1a",
  defaultEdgeColor: "#dce5dc",
  defaultNodeColor: "#6b7280",
  dimmedNodeColor: "#e0e0e0",
  highlightEdgeColor: "#88ccff",
  selectionBorderColor: "#ff6600",
  hoverBackgroundColor: "#FFFFFF",
  hoverShadowColor: "#000000",
  isDark: false,
};

const DARK: GraphTheme = {
  labelColor: "#e8ede8",
  defaultEdgeColor: "#3a4a55",
  defaultNodeColor: "#8a9b8a",
  dimmedNodeColor: "#2a3540",
  highlightEdgeColor: "#5dadec",
  selectionBorderColor: "#ff8833",
  hoverBackgroundColor: "#1e293b",
  hoverShadowColor: "#000000",
  isDark: true,
};

function resolveTheme(): GraphTheme {
  if (typeof document === "undefined") return LIGHT;
  return document.documentElement.getAttribute("data-theme") === "dark" ? DARK : LIGHT;
}

/**
 * Reads the current `data-theme` attribute and returns a resolved color
 * palette for the Sigma.js WebGL renderer (which cannot read CSS vars).
 * Re-renders when the theme toggles.
 */
export function useGraphTheme(): GraphTheme {
  const [theme, setTheme] = useState<GraphTheme>(resolveTheme);

  useEffect(() => {
    const observer = new MutationObserver(() => setTheme(resolveTheme()));
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    // Sync on mount in case SSR guessed wrong
    setTheme(resolveTheme());
    return () => observer.disconnect();
  }, []);

  return theme;
}
