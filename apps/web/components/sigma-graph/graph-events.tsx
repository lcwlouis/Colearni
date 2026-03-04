"use client";

import { useEffect, useRef, useCallback } from "react";
import { useSigma } from "@react-sigma/core";

type Props = {
  onSelect: (conceptId: number) => void;
  onBackgroundClick?: () => void;
  onHoverNode: (nodeKey: string | null) => void;
  focusNodeId?: number | null;
  onResetViewReady?: (resetFn: () => void) => void;
};

/**
 * Renderless component that wires Sigma.js user interactions (click, hover,
 * drag, zoom-to-node, reset-view) to React callbacks.
 * Must be rendered inside a <SigmaContainer>.
 */
export function GraphEvents({
  onSelect,
  onBackgroundClick,
  onHoverNode,
  focusNodeId,
  onResetViewReady,
}: Props) {
  const sigma = useSigma();
  const isDragging = useRef(false);
  const draggedNode = useRef<string | null>(null);

  // ---- Node click → onSelect ----
  useEffect(() => {
    const handler = (event: { node: string }) => {
      if (isDragging.current) return;
      const conceptId = Number(event.node);
      if (!isNaN(conceptId)) {
        onSelect(conceptId);
      }
    };
    sigma.on("clickNode", handler);
    return () => {
      sigma.off("clickNode", handler);
    };
  }, [sigma, onSelect]);

  // ---- Background click → deselect ----
  useEffect(() => {
    const handler = () => {
      if (isDragging.current) return;
      onBackgroundClick?.();
    };
    sigma.on("clickStage", handler);
    return () => {
      sigma.off("clickStage", handler);
    };
  }, [sigma, onBackgroundClick]);

  // ---- Hover ----
  useEffect(() => {
    const enterHandler = (event: { node: string }) => {
      onHoverNode(event.node);
      sigma.getContainer().style.cursor = "pointer";
    };
    const leaveHandler = () => {
      onHoverNode(null);
      sigma.getContainer().style.cursor = "default";
    };
    sigma.on("enterNode", enterHandler);
    sigma.on("leaveNode", leaveHandler);
    return () => {
      sigma.off("enterNode", enterHandler);
      sigma.off("leaveNode", leaveHandler);
    };
  }, [sigma, onHoverNode]);

  // ---- Drag ----
  useEffect(() => {
    const downHandler = (event: {
      node: string;
      preventSigmaDefault: () => void;
    }) => {
      isDragging.current = false;
      draggedNode.current = event.node;
      event.preventSigmaDefault();
      sigma.getGraph().setNodeAttribute(event.node, "highlighted", true);
    };

    const moveHandler = (event: {
      x: number;
      y: number;
      preventSigmaDefault: () => void;
    }) => {
      if (draggedNode.current) {
        isDragging.current = true;
        event.preventSigmaDefault();
        const pos = sigma.viewportToGraph({ x: event.x, y: event.y });
        sigma.getGraph().setNodeAttribute(draggedNode.current, "x", pos.x);
        sigma.getGraph().setNodeAttribute(draggedNode.current, "y", pos.y);
      }
    };

    const upHandler = () => {
      if (draggedNode.current) {
        sigma.getGraph().removeNodeAttribute(draggedNode.current, "highlighted");
      }
      draggedNode.current = null;
      setTimeout(() => {
        isDragging.current = false;
      }, 50);
    };

    sigma.on("downNode", downHandler);
    sigma.getMouseCaptor().on("mousemovebody", moveHandler);
    sigma.getMouseCaptor().on("mouseup", upHandler);

    return () => {
      sigma.off("downNode", downHandler);
      sigma.getMouseCaptor().off("mousemovebody", moveHandler);
      sigma.getMouseCaptor().off("mouseup", upHandler);
    };
  }, [sigma]);

  // ---- Zoom-to-node (focusNodeId) ----
  useEffect(() => {
    if (focusNodeId == null) return;
    const nodeKey = String(focusNodeId);
    const graph = sigma.getGraph();
    if (!graph.hasNode(nodeKey)) return;

    const nodeDisplayData = sigma.getNodeDisplayData(nodeKey);
    if (!nodeDisplayData) return;

    sigma.getCamera().animate(
      { x: nodeDisplayData.x, y: nodeDisplayData.y, ratio: 0.3 },
      { duration: 500 },
    );
  }, [sigma, focusNodeId]);

  // ---- Reset view callback ----
  const resetView = useCallback(() => {
    sigma.getCamera().animate(
      { x: 0.5, y: 0.5, ratio: 1 },
      { duration: 500 },
    );
  }, [sigma]);

  useEffect(() => {
    onResetViewReady?.(resetView);
  }, [onResetViewReady, resetView]);

  return null;
}
