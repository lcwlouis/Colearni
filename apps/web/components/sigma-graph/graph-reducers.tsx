"use client";

import { useEffect } from "react";
import { useSigma } from "@react-sigma/core";
import { NodeBorderProgram } from "@sigma/node-border";
import type { GraphTheme } from "@/lib/graph/hooks/use-graph-theme";

type Props = {
  selectedId?: number;
  hoveredNode: string | null;
  searchMatchKeys?: Set<string>;
  hasSearchQuery?: boolean;
  highlightNeighbors?: boolean;
  theme?: GraphTheme;
};

/**
 * Renderless component that configures Sigma.js node/edge reducers for
 * selection highlighting, neighbour dimming, and search filtering.
 * Must be rendered inside a <SigmaContainer>.
 */
export function GraphReducers({ selectedId, hoveredNode, searchMatchKeys, hasSearchQuery, highlightNeighbors = true, theme }: Props) {
  const sigma = useSigma();

  useEffect(() => {
    // Ensure NodeBorderProgram is registered. During React StrictMode
    // remounting or SigmaContainer recreation, the program may be missing.
    const programs = sigma.getSetting("nodeProgramClasses") ?? {};
    if (!programs.bordered) {
      sigma.setSetting("nodeProgramClasses", { ...programs, bordered: NodeBorderProgram });
    }

    const selectedKey = selectedId != null ? String(selectedId) : null;
    const graph = sigma.getGraph();
    const dimmed = theme?.dimmedNodeColor ?? "#e0e0e0";
    const border = theme?.selectionBorderColor ?? "#ff6600";
    const hlEdge = theme?.highlightEdgeColor ?? "#88ccff";

    sigma.setSetting("nodeReducer", (node, data) => {
      const result = { ...data };
      const activeNode = hoveredNode || selectedKey;

      if (highlightNeighbors && activeNode && graph.hasNode(activeNode)) {
        const neighbors = new Set(graph.neighbors(activeNode));
        if (node === activeNode) {
          result.highlighted = true;
          result.borderColor = border;
          result.borderSize = 0.3;
          result.zIndex = 2;
        } else if (neighbors.has(node)) {
          result.highlighted = true;
          result.zIndex = 1;
        } else {
          result.color = dimmed;
          result.label = undefined;
          result.zIndex = 0;
        }
      } else if (!highlightNeighbors && activeNode && graph.hasNode(activeNode) && node === activeNode) {
        result.highlighted = true;
        result.borderColor = border;
        result.borderSize = 0.3;
        result.zIndex = 2;
      }

      if (hasSearchQuery) {
        if (!searchMatchKeys?.has(node)) {
          result.color = dimmed;
          result.label = undefined;
          result.zIndex = 0;
        } else {
          result.highlighted = true;
          result.zIndex = 2;
        }
      }

      return result;
    });

    sigma.setSetting("edgeReducer", (edge, data) => {
      const result = { ...data };
      const activeNode = hoveredNode || selectedKey;

      if (highlightNeighbors && activeNode && graph.hasNode(activeNode)) {
        const extremities = graph.extremities(edge);
        if (extremities.includes(activeNode)) {
          result.color = hlEdge;
          result.size = (data.size || 1) * 1.5;
          result.zIndex = 1;
        } else {
          result.hidden = true;
        }
      }

      return result;
    });

    // Guard against stale Sigma instance. In React StrictMode (dev) or during
    // SigmaContainer recreation, children effects re-run before the parent
    // effect recreates the Sigma instance, so refresh() may hit a killed
    // instance whose nodePrograms have been cleared.
    try {
      sigma.refresh();
    } catch {
      // Instance was killed; the replacement will render on its own.
    }

    return () => {
      try {
        sigma.setSetting("nodeReducer", null);
        sigma.setSetting("edgeReducer", null);
      } catch {
        // Instance already killed.
      }
    };
  }, [sigma, selectedId, hoveredNode, searchMatchKeys, hasSearchQuery, highlightNeighbors, theme]);

  return null;
}
