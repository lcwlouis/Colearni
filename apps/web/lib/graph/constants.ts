/** Visual constants for the Sigma.js knowledge-graph renderer. */

export const TIER_COLORS: Record<string, string> = {
  umbrella: "#6366f1",
  topic: "#3b82f6",
  subtopic: "#14b8a6",
  granular: "#6b7280",
};

export const NODE_SIZE_RANGE = { min: 4, max: 15 } as const;
export const EDGE_SIZE_RANGE = { min: 0.5, max: 3 } as const;

export const DEFAULT_SIGMA_SETTINGS = {
  renderLabels: true,
  labelColor: { color: "var(--text)" },
  defaultEdgeColor: "var(--line)",
  defaultNodeColor: "#6b7280",
  defaultEdgeType: "arrow" as const,
  labelRenderedSizeThreshold: 6,
} as const;
