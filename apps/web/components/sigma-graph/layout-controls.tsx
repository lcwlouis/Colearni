"use client";

import type { LayoutType } from "./graph-layout";
import styles from "./layout-controls.module.css";

const LAYOUT_OPTIONS: { value: LayoutType; label: string }[] = [
  { value: "forceatlas2", label: "ForceAtlas2" },
  { value: "force", label: "Force Directed" },
  { value: "circular", label: "Circular" },
  { value: "circlepack", label: "Circle Pack" },
  { value: "random", label: "Random" },
];

type Props = {
  layout: LayoutType;
  onLayoutChange: (layout: LayoutType) => void;
  isRunning: boolean;
  onIsRunningChange: (running: boolean) => void;
};

export function LayoutControls({
  layout,
  onLayoutChange,
  isRunning,
  onIsRunningChange,
}: Props) {
  const canAnimate = layout === "forceatlas2";

  return (
    <div className={styles.controls}>
      <select
        className={styles.select}
        value={layout}
        onChange={(e) => onLayoutChange(e.target.value as LayoutType)}
        aria-label="Layout algorithm"
      >
        {LAYOUT_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      <button
        className={styles.playBtn}
        disabled={!canAnimate}
        onClick={() => onIsRunningChange(!isRunning)}
        aria-label={isRunning ? "Pause layout" : "Play layout"}
        title={canAnimate ? (isRunning ? "Pause" : "Play (auto-stops after 3s)") : "Only ForceAtlas2 supports continuous mode"}
      >
        {isRunning ? "⏸" : "▶"}
      </button>
    </div>
  );
}
