"use client";

import { useEffect, useRef } from "react";
import { useSigma } from "@react-sigma/core";
import { useLayoutForceAtlas2 } from "@react-sigma/layout-forceatlas2";
import { useLayoutCircular } from "@react-sigma/layout-circular";
import { useLayoutNoverlap } from "@react-sigma/layout-noverlap";

export type LayoutType = "forceatlas2" | "circular";

type Props = {
  layout: LayoutType;
};

/**
 * Runs layout algorithms inside <SigmaContainer>.
 * UXG.4: ForceAtlas2 as default, circular as alternative, noverlap post-processing.
 */
export function GraphLayout({ layout }: Props) {
  const sigma = useSigma();
  const hasRun = useRef(false);

  const { assign: assignFA2 } = useLayoutForceAtlas2({
    iterations: 100,
    settings: {
      gravity: 1,
      scalingRatio: 2,
      strongGravityMode: true,
      barnesHutOptimize: true,
    },
  });

  const { assign: assignCircular } = useLayoutCircular();

  const { assign: assignNoverlap } = useLayoutNoverlap({
    maxIterations: 50,
    settings: { margin: 5, ratio: 1.1 },
  });

  useEffect(() => {
    const graph = sigma.getGraph();
    if (graph.order === 0) return;

    switch (layout) {
      case "circular":
        assignCircular();
        break;
      case "forceatlas2":
      default:
        assignFA2();
        break;
    }

    // Post-process to prevent node overlap
    assignNoverlap();
    hasRun.current = true;
  }, [layout, sigma, assignFA2, assignCircular, assignNoverlap]);

  return null;
}
