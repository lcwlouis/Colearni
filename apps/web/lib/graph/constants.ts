/** Visual constants for the Sigma.js knowledge-graph renderer. */

export const TIER_COLORS: Record<string, string> = {
  umbrella: "#6366f1",
  topic: "#3b82f6",
  subtopic: "#14b8a6",
  granular: "#6b7280",
};

/** Label indicators prepended to node titles for mastery / activity status. */
export const MASTERY_INDICATORS: Record<string, string> = {
  learned: "✅ ",
  learning: "📖 ",
};

export const ACTIVE_CHAT_INDICATOR = "💬 ";

export const NODE_SIZE_RANGE = { min: 4, max: 15 } as const;
export const EDGE_SIZE_RANGE = { min: 0.5, max: 3 } as const;

/** Border ring colours (used by NodeBorderProgram). */
export const NODE_BORDER_COLOR = "#EEEEEE";
export const NODE_BORDER_COLOR_SELECTED = "#F57F17";
export const NODE_BORDER_SIZE = 0.2;
