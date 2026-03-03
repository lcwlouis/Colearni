"use client";

import { useEffect, useRef, useCallback } from "react";
import { useSigma } from "@react-sigma/core";
import { useLayoutForceAtlas2 } from "@react-sigma/layout-forceatlas2";
import { useLayoutCircular } from "@react-sigma/layout-circular";
import { useLayoutNoverlap } from "@react-sigma/layout-noverlap";
import { useLayoutForce } from "@react-sigma/layout-force";
import { useLayoutRandom } from "@react-sigma/layout-random";
import { useLayoutCirclepack } from "@react-sigma/layout-circlepack";

export type LayoutType = "forceatlas2" | "circular" | "force" | "circlepack" | "random";

type Props = {
  layout: LayoutType;
  isRunning?: boolean;
  onAutoStop?: () => void;
};

/**
 * Runs layout algorithms inside <SigmaContainer>.
 * Follows the porting guide pattern for layout switching and play/pause.
 */
export function GraphLayout({ layout, isRunning, onAutoStop }: Props) {
  const sigma = useSigma();
  const hasRun = useRef(false);
  const animFrameRef = useRef<number>(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  const autoStopTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // --- Layout hooks ---
  const { assign: assignFA2 } = useLayoutForceAtlas2({
    iterations: 15,
  });

  const { assign: assignCircular } = useLayoutCircular();

  const { assign: assignNoverlap } = useLayoutNoverlap({
    maxIterations: 50,
    settings: {
      margin: 5,
      expansion: 1.1,
      gridSize: 1,
      ratio: 1,
      speed: 3,
    },
  });

  const { assign: assignForce } = useLayoutForce({
    maxIterations: 15,
    settings: {
      attraction: 0.0003,
      repulsion: 0.02,
      gravity: 0.02,
      inertia: 0.4,
      maxMove: 100,
    },
  });

  const { assign: assignRandom } = useLayoutRandom();

  const { assign: assignCirclepack } = useLayoutCirclepack();

  /** Capture current node positions. */
  const capturePositions = useCallback(() => {
    const graph = sigma.getGraph();
    const positions: Record<string, { x: number; y: number }> = {};
    graph.forEachNode((node) => {
      positions[node] = {
        x: graph.getNodeAttribute(node, "x") ?? 0,
        y: graph.getNodeAttribute(node, "y") ?? 0,
      };
    });
    return positions;
  }, [sigma]);

  /** Animate from `from` positions to current positions over `duration` ms. */
  const animateTransition = useCallback(
    (from: Record<string, { x: number; y: number }>, duration: number) => {
      const graph = sigma.getGraph();
      const to: Record<string, { x: number; y: number }> = {};
      graph.forEachNode((node) => {
        to[node] = {
          x: graph.getNodeAttribute(node, "x") ?? 0,
          y: graph.getNodeAttribute(node, "y") ?? 0,
        };
      });

      const startTime = performance.now();
      const step = (now: number) => {
        const t = Math.min((now - startTime) / duration, 1);
        const ease = t * (2 - t); // ease-out quad
        graph.forEachNode((node) => {
          const f = from[node];
          const dest = to[node];
          if (f && dest) {
            graph.setNodeAttribute(node, "x", f.x + (dest.x - f.x) * ease);
            graph.setNodeAttribute(node, "y", f.y + (dest.y - f.y) * ease);
          }
        });
        if (t < 1) {
          animFrameRef.current = requestAnimationFrame(step);
        }
      };
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = requestAnimationFrame(step);
    },
    [sigma],
  );

  // Main layout effect — runs when layout type changes
  useEffect(() => {
    const graph = sigma.getGraph();
    if (graph.order === 0) return;

    const prevPositions = hasRun.current ? capturePositions() : null;

    switch (layout) {
      case "circular":
        assignCircular();
        break;
      case "force":
        assignForce();
        break;
      case "circlepack":
        assignCirclepack();
        break;
      case "random":
        assignRandom();
        break;
      case "forceatlas2":
      default:
        assignFA2();
        break;
    }

    // Post-process to prevent node overlap
    assignNoverlap();

    // Animate transition if we had previous positions
    if (prevPositions) {
      animateTransition(prevPositions, 400);
    }

    hasRun.current = true;
  }, [layout, sigma, assignFA2, assignCircular, assignNoverlap, assignForce, assignCirclepack, assignRandom, capturePositions, animateTransition]);

  // Play/Pause continuous layout animation
  // Uses assign() to compute new positions synchronously, then animates.
  // Repeats every 200ms. Auto-stops after 3s.
  // This avoids the "giggling" caused by direct worker start/stop.
  useEffect(() => {
    if (!isRunning) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = undefined;
      }
      clearTimeout(autoStopTimer.current);
      return;
    }

    // Only ForceAtlas2 supports continuous mode
    if (layout !== "forceatlas2") return;

    const graph = sigma.getGraph();
    if (!graph || graph.order === 0) return;

    const updatePositions = () => {
      try {
        const from = capturePositions();
        assignFA2();
        animateTransition(from, 300);
      } catch {
        // Layout computation can fail if graph changes mid-computation
      }
    };

    // Immediate first frame
    updatePositions();

    // Continuous updates every 200ms
    intervalRef.current = setInterval(updatePositions, 200);

    // Auto-stop after 3 seconds
    autoStopTimer.current = setTimeout(() => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = undefined;
      }
      onAutoStop?.();
    }, 3000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = undefined;
      }
      clearTimeout(autoStopTimer.current);
    };
  }, [isRunning, layout, sigma, assignFA2, capturePositions, animateTransition, onAutoStop]);

  return null;
}
