"use client";

import { useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";
import { TIER_COLORS, MASTERY_INDICATORS, ACTIVE_CHAT_INDICATOR } from "@/lib/graph/constants";
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
        <span>Legend</span>
        <button
          className={styles.toggle}
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? "Expand legend" : "Collapse legend"}
        >
          {collapsed ? <ChevronRight size={14} style={{ display: 'block' }} /> : <ChevronDown size={14} style={{ display: 'block' }} />}
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
          {Object.entries(MASTERY_INDICATORS).map(([status, icon]) => (
            <div key={status} className={styles.item}>
              <span style={{ fontSize: 12, lineHeight: 1 }}>{icon.trim()}</span>
              <span>{status === "learned" ? "Mastered" : "Learning"}</span>
            </div>
          ))}
          <div className={styles.item}>
            <span style={{ fontSize: 12, lineHeight: 1 }}>{ACTIVE_CHAT_INDICATOR.trim()}</span>
            <span>Active Chat</span>
          </div>
        </div>
      )}
    </div>
  );
}
