"use client";

import { useState } from "react";
import { TIER_COLORS } from "@/lib/graph/constants";
import styles from "./graph-legend.module.css";

const TIER_LABELS: Record<string, string> = {
  umbrella: "Umbrella",
  topic: "Topic",
  subtopic: "Subtopic",
  granular: "Granular",
};

export function GraphLegend() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className={styles.legend}>
      <div className={styles.header}>
        <span>Tiers</span>
        <button
          className={styles.toggle}
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? "Expand legend" : "Collapse legend"}
        >
          {collapsed ? "▶" : "▼"}
        </button>
      </div>
      {!collapsed && (
        <div className={styles.items}>
          {Object.entries(TIER_COLORS).map(([tier, color]) => (
            <div key={tier} className={styles.item}>
              <span className={styles.dot} style={{ background: color }} />
              <span>{TIER_LABELS[tier] ?? tier}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
