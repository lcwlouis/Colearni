"use client";

import { useMemo } from "react";
import type { GraphSubgraphNode, GraphSubgraphEdge } from "@/lib/api/types";
import styles from "./status-bar.module.css";

type Props = {
  nodes: GraphSubgraphNode[];
  edges: GraphSubgraphEdge[];
  selectedId?: number;
  filteredTiers?: ReadonlySet<string>;
};

export function StatusBar({ nodes, edges, selectedId, filteredTiers }: Props) {
  const visibleNodes = useMemo(() => {
    if (!filteredTiers || filteredTiers.size === 0) return nodes.length;
    return nodes.filter((n) => filteredTiers.has(n.tier ?? "")).length;
  }, [nodes, filteredTiers]);

  const visibleEdges = useMemo(() => {
    if (!filteredTiers || filteredTiers.size === 0) return edges.length;
    const visibleIds = new Set(
      nodes.filter((n) => filteredTiers.has(n.tier ?? "")).map((n) => n.concept_id),
    );
    return edges.filter(
      (e) => visibleIds.has(e.src_concept_id) && visibleIds.has(e.tgt_concept_id),
    ).length;
  }, [nodes, edges, filteredTiers]);

  const selectedLabel = useMemo(() => {
    if (selectedId == null) return null;
    return nodes.find((n) => n.concept_id === selectedId)?.canonical_name ?? null;
  }, [nodes, selectedId]);

  return (
    <div className={styles.bar}>
      <span className={styles.stat}>Nodes: {nodes.length}</span>
      <span className={styles.separator} />
      <span className={styles.stat}>Edges: {edges.length}</span>
      <span className={styles.separator} />
      <span className={styles.stat}>Visible: {visibleNodes}N / {visibleEdges}E</span>
      {selectedLabel && (
        <>
          <span className={styles.separator} />
          <span className={styles.selected} title={selectedLabel}>
            Selected: {selectedLabel}
          </span>
        </>
      )}
    </div>
  );
}
