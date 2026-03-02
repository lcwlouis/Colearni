/**
 * Sigma.js renderer settings — separated from constants.ts because the
 * WebGL program imports cannot be loaded in a Node/JSDOM test environment.
 */

import { NodeBorderProgram } from "@sigma/node-border";
import { EdgeCurvedArrowProgram } from "@sigma/edge-curve";

// WebGL renderer cannot read CSS custom properties — use literal hex colors.
export const DEFAULT_SIGMA_SETTINGS = {
  renderLabels: true,
  labelColor: { color: "#1a2e1a" },
  defaultEdgeColor: "#dce5dc",
  defaultNodeColor: "#6b7280",
  defaultEdgeType: "curvedArrow" as const,
  defaultNodeType: "bordered" as const,
  nodeProgramClasses: {
    bordered: NodeBorderProgram,
  },
  edgeProgramClasses: {
    curvedArrow: EdgeCurvedArrowProgram,
  },
  labelRenderedSizeThreshold: 8,
  labelGridCellSize: 100,
  labelDensity: 0.5,
  enableEdgeEvents: true,
  zIndex: true,
} as const;
