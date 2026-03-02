"use client";

import { useState, useCallback, useEffect } from "react";
import { useSigma } from "@react-sigma/core";
import {
  expandFromNode,
  pruneToSubgraph,
  restoreFullGraph,
} from "@/lib/graph/subgraph-utils";
import styles from "./expand-prune-controls.module.css";

type Props = {
  selectedId?: number;
};

export function ExpandPruneControls({ selectedId }: Props) {
  const sigma = useSigma();
  const [depth, setDepth] = useState(0);
  const [expanded, setExpanded] = useState(false);

  // Reset expand/prune state when selection changes
  useEffect(() => {
    setDepth(0);
    setExpanded(false);
    restoreFullGraph(sigma.getGraph());
  }, [selectedId, sigma]);

  const nodeKey = selectedId != null ? String(selectedId) : null;

  const handleExpand = useCallback(() => {
    if (nodeKey == null) return;
    const graph = sigma.getGraph();
    if (!graph.hasNode(nodeKey)) return;
    const newDepth = expanded ? depth + 1 : 1;
    const keep = expandFromNode(graph, nodeKey, newDepth);
    pruneToSubgraph(graph, keep);
    setDepth(newDepth);
    setExpanded(true);
  }, [sigma, nodeKey, depth, expanded]);

  const handleRestore = useCallback(() => {
    restoreFullGraph(sigma.getGraph());
    setDepth(0);
    setExpanded(false);
  }, [sigma]);

  if (selectedId == null) return null;

  return (
    <div className={styles.toolbar}>
      {!expanded ? (
        <button
          className={styles.btn}
          onClick={handleExpand}
          aria-label="Expand neighbors"
          title="Show 1-hop neighbors only"
        >
          Expand
        </button>
      ) : (
        <>
          <span className={styles.depth}>Depth: {depth}</span>
          <div className={styles.separator} />
          {depth < 5 && (
            <button
              className={styles.btn}
              onClick={handleExpand}
              aria-label="Expand one more hop"
              title="Expand one more hop"
            >
              Expand +1
            </button>
          )}
          <button
            className={styles.btn}
            onClick={handleRestore}
            aria-label="Restore full graph"
            title="Show all nodes"
          >
            Restore
          </button>
        </>
      )}
    </div>
  );
}
