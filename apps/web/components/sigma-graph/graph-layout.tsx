"use client";
import { useEffect, useRef, useCallback, useMemo } from "react";
import { useSigma } from "@react-sigma/core";
import { useLayoutForceAtlas2 } from "@react-sigma/layout-forceatlas2";
import { useLayoutCircular } from "@react-sigma/layout-circular";
import { useLayoutNoverlap } from "@react-sigma/layout-noverlap";
import { useLayoutForce } from "@react-sigma/layout-force";
import { useLayoutRandom } from "@react-sigma/layout-random";
import { useLayoutCirclepack } from "@react-sigma/layout-circlepack";

export type LayoutType = "forceatlas2" | "circular" | "force" | "circlepack" | "random" | "noverlap";

const ITERATIVE_LAYOUTS: ReadonlySet<LayoutType> = new Set(["forceatlas2", "force", "noverlap"]);

type Props = {
  layout: LayoutType;
  isRunning?: boolean;
  onAutoStop?: () => void;
};

export function GraphLayout({ layout, isRunning, onAutoStop }: Props) {
  const sigma = useSigma();
  const hasRun = useRef(false);
  const animFrameRef = useRef<number>(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  const autoStopTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // --- Layout hooks ---
  const fa2 = useLayoutForceAtlas2({ iterations: 15 });
  const circular = useLayoutCircular();
  const noverlap = useLayoutNoverlap({
    maxIterations: 50,
    settings: { margin: 5, expansion: 1.1, gridSize: 1, ratio: 1, speed: 3 },
  });
  const force = useLayoutForce({
    maxIterations: 15,
    settings: { attraction: 0.0003, repulsion: 0.02, gravity: 0.02, inertia: 0.4, maxMove: 100 },
  });
  const random = useLayoutRandom();
  const circlepack = useLayoutCirclepack();

  // Registry for easy lookup
  const layoutMap = useMemo(() => ({
    forceatlas2: fa2,
    circular,
    noverlap,
    force,
    circlepack,
    random,
  }), [fa2, circular, noverlap, force, circlepack, random]);

  /** Animate nodes from current graph positions to target positions over duration ms. */
  const animateToPositions = useCallback(
    (target: Record<string, { [dim: string]: number }>, duration: number) => {
      const graph = sigma.getGraph();
      // Capture current positions as "from"
      const from: Record<string, { x: number; y: number }> = {};
      graph.forEachNode((node) => {
        from[node] = {
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
          const dest = target[node];
          if (f && dest) {
            graph.setNodeAttribute(node, "x", f.x + ((dest.x ?? f.x) - f.x) * ease);
            graph.setNodeAttribute(node, "y", f.y + ((dest.y ?? f.y) - f.y) * ease);
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

    const hook = layoutMap[layout];
    if (!hook) return;

    if (hasRun.current) {
      // Animated transition: get target positions without applying, then animate
      const target = hook.positions();
      animateToPositions(target, 400);
    } else {
      // First layout: apply immediately (no animation source)
      hook.assign();
    }

    hasRun.current = true;
  }, [layout, sigma, layoutMap, animateToPositions]);

  // Play/Pause continuous layout animation for iterative layouts
  useEffect(() => {
    if (!isRunning) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = undefined;
      }
      clearTimeout(autoStopTimer.current);
      return;
    }

    if (!ITERATIVE_LAYOUTS.has(layout)) return;

    const graph = sigma.getGraph();
    if (!graph || graph.order === 0) return;

    const hook = layoutMap[layout];
    if (!hook) return;

    const updatePositions = () => {
      try {
        const target = hook.positions();
        animateToPositions(target, 300);
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
  }, [isRunning, layout, sigma, layoutMap, animateToPositions, onAutoStop]);

  return null;
}
