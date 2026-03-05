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

    // 1. Collect 2-hop neighborhood node keys
    const neighborhood = new Set<string>([nodeKey]);
    graph.forEachNeighbor(nodeKey, (n1) => {
      neighborhood.add(n1);
      graph.forEachNeighbor(n1, (n2) => neighborhood.add(n2));
    });

    // 2. Gather graph-space coordinates for the neighborhood
    const hoodPositions: Array<{ x: number; y: number }> = [];
    for (const key of neighborhood) {
      const attrs = graph.getNodeAttributes(key);
      if (attrs.x != null && attrs.y != null) {
        hoodPositions.push({ x: attrs.x as number, y: attrs.y as number });
      }
    }
    if (hoodPositions.length === 0) return;

    // 3. Compute neighborhood bounding box in graph space
    let hMinX = Infinity, hMaxX = -Infinity;
    let hMinY = Infinity, hMaxY = -Infinity;
    for (const p of hoodPositions) {
      hMinX = Math.min(hMinX, p.x);
      hMaxX = Math.max(hMaxX, p.x);
      hMinY = Math.min(hMinY, p.y);
      hMaxY = Math.max(hMaxY, p.y);
    }

    // 4. Compute full graph bounding box in graph space
    let gMinX = Infinity, gMaxX = -Infinity;
    let gMinY = Infinity, gMaxY = -Infinity;
    graph.forEachNode((_, attrs) => {
      if (attrs.x != null && attrs.y != null) {
        gMinX = Math.min(gMinX, attrs.x as number);
        gMaxX = Math.max(gMaxX, attrs.x as number);
        gMinY = Math.min(gMinY, attrs.y as number);
        gMaxY = Math.max(gMaxY, attrs.y as number);
      }
    });
    const graphSpan = Math.max(gMaxX - gMinX, gMaxY - gMinY) || 1;

    // 5. Convert neighborhood center to framed-graph coordinates
    //    (graphToViewport applies normalization + camera; viewportToFramedGraph
    //     inverts camera → gives pure normalized framed-graph coords)
    const hoodCenter = {
      x: (hMinX + hMaxX) / 2,
      y: (hMinY + hMaxY) / 2,
    };
    const vpCenter = sigma.graphToViewport(hoodCenter);
    const fgCenter = sigma.viewportToFramedGraph(vpCenter);

    // 6. Compute zoom ratio: fraction of graph the neighborhood occupies, with padding
    const hoodSpan = Math.max(hMaxX - hMinX, hMaxY - hMinY);
    const padding = 2.0;
    const ratio = Math.min(
      Math.max((hoodSpan / graphSpan) * padding, 0.05),
      1.0,
    );

    // 7. Animate camera to center on neighborhood
    sigma.getCamera().animate(
      { x: fgCenter.x, y: fgCenter.y, ratio },
      { duration: 400 },
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
