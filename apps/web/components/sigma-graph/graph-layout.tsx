"use client";

import { useEffect, useRef, useCallback } from "react";
import { useSigma } from "@react-sigma/core";
import { useLayoutForceAtlas2 } from "@react-sigma/layout-forceatlas2";
import { useWorkerLayoutForceAtlas2 } from "@react-sigma/layout-forceatlas2";
import { useLayoutCircular } from "@react-sigma/layout-circular";
import { useLayoutNoverlap } from "@react-sigma/layout-noverlap";
import { useLayoutForce } from "@react-sigma/layout-force";

export type LayoutType = "forceatlas2" | "circular" | "force" | "circlepack" | "random";

/** Tier ordering for circlepack: inner rings first. */
const TIER_RING_ORDER: Record<string, number> = {
  umbrella: 0,
  topic: 1,
  subtopic: 2,
  granular: 3,
};

type Props = {
  layout: LayoutType;
  isRunning?: boolean;
  onAutoStop?: () => void;
};

/**
 * Runs layout algorithms inside <SigmaContainer>.
 * UXG.4: ForceAtlas2 as default, circular as alternative, noverlap post-processing.
 * UXG.9: Extended layout suite with force, circlepack, random, animated transitions.
 */
export function GraphLayout({ layout, isRunning, onAutoStop }: Props) {
  const sigma = useSigma();
  const hasRun = useRef(false);
  const animFrameRef = useRef<number>(0);
  const autoStopTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const { assign: assignFA2 } = useLayoutForceAtlas2({
    iterations: 100,
    settings: {
      gravity: 0.5,
      scalingRatio: 4,
      strongGravityMode: true,
      barnesHutOptimize: true,
    },
  });

  const { start: startFA2, stop: stopFA2 } = useWorkerLayoutForceAtlas2({
    settings: {
      gravity: 0.5,
      scalingRatio: 4,
      strongGravityMode: true,
      barnesHutOptimize: true,
    },
  });

  const { assign: assignCircular } = useLayoutCircular();

  const { assign: assignNoverlap } = useLayoutNoverlap({
    maxIterations: 50,
    settings: { margin: 5, ratio: 1.1, speed: 3 },
  });

  const { assign: assignForce } = useLayoutForce({
    maxIterations: 100,
    settings: { attraction: 0.0003, repulsion: 0.02, gravity: 0.02, inertia: 0.4 },
  });

  /** Simple deterministic hash for seeded randomness. */
  const seededRandom = useCallback((seed: string) => {
    let h = 0;
    for (let i = 0; i < seed.length; i++) {
      h = ((h << 5) - h + seed.charCodeAt(i)) | 0;
    }
    // Map to 0..1
    return ((h & 0x7fffffff) % 10000) / 10000;
  }, []);

  /** Assign random positions seeded by node key. */
  const assignRandom = useCallback(() => {
    const graph = sigma.getGraph();
    graph.forEachNode((node) => {
      graph.setNodeAttribute(node, "x", (seededRandom(node + "x") - 0.5) * 200);
      graph.setNodeAttribute(node, "y", (seededRandom(node + "y") - 0.5) * 200);
    });
  }, [sigma, seededRandom]);

  /** Arrange nodes in concentric rings grouped by tier. */
  const assignCirclepack = useCallback(() => {
    const graph = sigma.getGraph();
    const groups: Record<number, string[]> = {};
    graph.forEachNode((node) => {
      const tier = graph.getNodeAttribute(node, "tier") as string | null;
      const ring = TIER_RING_ORDER[tier ?? ""] ?? 3;
      (groups[ring] ??= []).push(node);
    });

    const sortedRings = Object.keys(groups).map(Number).sort((a, b) => a - b);
    let radius = 0;
    for (const ring of sortedRings) {
      const nodes = groups[ring];
      const count = nodes.length;
      radius += count <= 1 ? 0 : Math.max(30, count * 8);
      for (let i = 0; i < count; i++) {
        const angle = (2 * Math.PI * i) / count;
        graph.setNodeAttribute(nodes[i], "x", Math.cos(angle) * radius);
        graph.setNodeAttribute(nodes[i], "y", Math.sin(angle) * radius);
      }
      radius += Math.max(30, count * 8);
    }
  }, [sigma]);

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
      // Capture target positions
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

  // Main layout effect
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

  // Play/Pause continuous ForceAtlas2
  useEffect(() => {
    if (layout !== "forceatlas2") {
      stopFA2();
      return;
    }
    if (isRunning) {
      startFA2();
      autoStopTimer.current = setTimeout(() => {
        stopFA2();
        onAutoStop?.();
      }, 3000);
    } else {
      stopFA2();
    }
    return () => {
      clearTimeout(autoStopTimer.current);
      stopFA2();
    };
  }, [isRunning, layout, startFA2, stopFA2, onAutoStop]);

  return null;
}
