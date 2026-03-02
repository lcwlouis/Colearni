"use client";

import { useEffect } from "react";
import { useSigma } from "@react-sigma/core";

type Props = {
  selectedId?: number;
  hoveredNode: string | null;
  searchMatchKeys?: Set<string>;
  hasSearchQuery?: boolean;
  highlightNeighbors?: boolean;
};

/**
 * Renderless component that configures Sigma.js node/edge reducers for
 * selection highlighting, neighbour dimming, and search filtering.
 * Must be rendered inside a <SigmaContainer>.
 */
export function GraphReducers({ selectedId, hoveredNode, searchMatchKeys, hasSearchQuery, highlightNeighbors = true }: Props) {
  const sigma = useSigma();

  useEffect(() => {
    const selectedKey = selectedId != null ? String(selectedId) : null;
    const graph = sigma.getGraph();

    sigma.setSetting("nodeReducer", (node, data) => {
      const result = { ...data };
      const activeNode = hoveredNode || selectedKey;

      if (highlightNeighbors && activeNode && graph.hasNode(activeNode)) {
        const neighbors = new Set(graph.neighbors(activeNode));
        if (node === activeNode) {
          result.highlighted = true;
          result.borderColor = "#ff6600";
          result.borderSize = 0.3;
          result.zIndex = 2;
        } else if (neighbors.has(node)) {
          result.highlighted = true;
          result.zIndex = 1;
        } else {
          result.color = "#e0e0e0";
          result.label = undefined;
          result.zIndex = 0;
        }
      } else if (!highlightNeighbors && activeNode && graph.hasNode(activeNode) && node === activeNode) {
        result.highlighted = true;
        result.borderColor = "#ff6600";
        result.borderSize = 0.3;
        result.zIndex = 2;
      }

      if (hasSearchQuery) {
        if (!searchMatchKeys?.has(node)) {
          result.color = "#e0e0e0";
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
          result.color = "#88ccff";
          result.size = (data.size || 1) * 1.5;
          result.zIndex = 1;
        } else {
          result.hidden = true;
        }
      }

      return result;
    });

    // Defer refresh to next tick — programs may not be registered yet
    // when navigating to graph page from another route (fresh Sigma instance).
    const rafId = requestAnimationFrame(() => {
      try {
        sigma.refresh();
      } catch {
        // Swallow "no suitable program" if still initializing
      }
    });

    return () => {
      cancelAnimationFrame(rafId);
      sigma.setSetting("nodeReducer", null);
      sigma.setSetting("edgeReducer", null);
    };
  }, [sigma, selectedId, hoveredNode, searchMatchKeys, hasSearchQuery, highlightNeighbors]);

  return null;
}
