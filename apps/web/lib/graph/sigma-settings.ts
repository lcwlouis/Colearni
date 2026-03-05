/**
 * Sigma.js renderer settings — separated from constants.ts because the
 * WebGL program imports cannot be loaded in a Node/JSDOM test environment.
 *
 * IMPORTANT: We explicitly import and register NodeCircleProgram and
 * NodeBorderProgram here rather than relying on sigma's internal
 * DEFAULT_NODE_PROGRAM_CLASSES. Turbopack
 * can produce stale module references for sigma's internal relative imports
 * during HMR and client-side navigation, causing "could not find program
 * for node type circle" errors. Our own top-level import is stable.
 */

import { NodeCircleProgram } from "sigma/rendering";
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
    circle: NodeCircleProgram,
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
  allowInvalidContainer: true,
} as const;
