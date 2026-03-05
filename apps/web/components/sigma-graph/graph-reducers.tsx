"use client";

import { useEffect, useRef } from "react";
import { useSigma } from "@react-sigma/core";
import { NodeBorderProgram } from "@sigma/node-border";
import type { GraphTheme } from "@/lib/graph/hooks/use-graph-theme";
import { MASTERY_INDICATORS, ACTIVE_CHAT_INDICATOR, NODE_BORDER_COLOR_SELECTED } from "@/lib/graph/constants";

type Props = {
  selectedId?: number;
  hoveredNode: string | null;
  searchMatchKeys?: Set<string>;
  hasSearchQuery?: boolean;
  highlightNeighbors?: boolean;
  theme?: GraphTheme;
  activeChatKeys?: Set<string>;
  flashRef?: React.RefObject<boolean>;
};

/**
 * Renderless component that configures Sigma.js node/edge reducers for
 * selection highlighting, neighbour dimming, search filtering, and
 * mastery/activity label indicators.
 * Must be rendered inside a <SigmaContainer>.
 *
 * Uses refs for frequently-changing state to avoid reducer re-registration
 * (which causes visible flicker). Only structural changes (sigma instance,
 * theme) trigger re-registration.
 */
export function GraphReducers({
  selectedId,
  hoveredNode,
  searchMatchKeys,
  hasSearchQuery,
  highlightNeighbors = true,
  theme,
  activeChatKeys,
  flashRef,
}: Props) {
  const sigma = useSigma();

  // --- Refs for frequently-changing visual state ---
  const selectedKeyRef = useRef<string | null>(null);
  const hoveredRef = useRef<string | null>(null);
  const searchKeysRef = useRef<Set<string> | undefined>(undefined);
  const hasSearchRef = useRef(false);
  const highlightRef = useRef(true);
  const activeChatRef = useRef<Set<string> | undefined>(undefined);

  // Update refs synchronously during render
  selectedKeyRef.current = selectedId != null ? String(selectedId) : null;
  hoveredRef.current = hoveredNode;
  searchKeysRef.current = searchMatchKeys;
  hasSearchRef.current = hasSearchQuery ?? false;
  highlightRef.current = highlightNeighbors;
  activeChatRef.current = activeChatKeys;

  // --- Register reducers ONCE per sigma instance + theme ---
  useEffect(() => {
    // Safety: re-register NodeBorderProgram if missing. Turbopack HMR or
    // React StrictMode double-mount can lose program references.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const programs = sigma.getSetting("nodeProgramClasses") as any ?? {};
    if (!programs.bordered) {
      sigma.setSetting("nodeProgramClasses", { ...programs, bordered: NodeBorderProgram });
    }

    const graph = sigma.getGraph();
    const dimmed = theme?.dimmedNodeColor ?? "#e0e0e0";
    const hlEdge = theme?.highlightEdgeColor ?? "#88ccff";

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    sigma.setSetting("nodeReducer", (node: string, data: any) => {
      const result = { ...data };
      const activeNode = hoveredRef.current || selectedKeyRef.current;

      if (highlightRef.current && activeNode && graph.hasNode(activeNode)) {
        const neighbors = new Set(graph.neighbors(activeNode));
        if (node === activeNode) {
          result.highlighted = true;
          result.zIndex = 2;
          result.borderColor = NODE_BORDER_COLOR_SELECTED;
        } else if (neighbors.has(node)) {
          result.highlighted = true;
          result.zIndex = 1;
        } else {
          result.color = dimmed;
          result.borderColor = dimmed;
          result.label = undefined;
          result.zIndex = 0;
        }
      } else if (!highlightRef.current && activeNode && graph.hasNode(activeNode) && node === activeNode) {
        result.highlighted = true;
        result.zIndex = 2;
        result.borderColor = NODE_BORDER_COLOR_SELECTED;
      }

      if (hasSearchRef.current) {
        if (!searchKeysRef.current?.has(node)) {
          result.color = dimmed;
          result.label = undefined;
          result.zIndex = 0;
        } else {
          result.highlighted = true;
          result.zIndex = 2;
        }
      }

      // Label indicators for mastery and active chat (only when label is visible)
      if (result.label != null) {
        const mastery = data.masteryStatus as string | null;
        const indicator = mastery ? MASTERY_INDICATORS[mastery] : undefined;
        const isActiveChat = activeChatRef.current?.has(node);

        if (isActiveChat) {
          result.label = ACTIVE_CHAT_INDICATOR + result.label;
        } else if (indicator) {
          result.label = indicator + result.label;
        }
      }

      return result;
    });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    sigma.setSetting("edgeReducer", (edge: string, data: any) => {
      const result = { ...data };
      const activeNode = hoveredRef.current || selectedKeyRef.current;

      if (highlightRef.current && activeNode && graph.hasNode(activeNode)) {
        const extremities = graph.extremities(edge);
        if (extremities.includes(activeNode)) {
          result.color = hlEdge;
          result.size = ((data.size as number) || 1) * 1.5;
          result.zIndex = 1;
        } else {
          result.hidden = true;
        }
      }

      return result;
    });

    return () => {
      try {
        sigma.setSetting("nodeReducer", null);
        sigma.setSetting("edgeReducer", null);
      } catch {
        // Instance already killed
      }
    };
  }, [sigma, theme]);

  // --- Trigger sigma refresh when visual state changes ---
  useEffect(() => {
    try {
      sigma.refresh();
    } catch {
      // Instance may not be ready
    }
  }, [sigma, selectedId, hoveredNode, searchMatchKeys, hasSearchQuery, highlightNeighbors, activeChatKeys]);

  return null;
}
