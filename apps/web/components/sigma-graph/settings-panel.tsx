"use client";

import { useState } from "react";
import { Settings as SettingsIcon } from "lucide-react";
import { useGraphSettings } from "@/lib/graph/settings-store";
import type { LayoutType } from "./graph-layout";
import styles from "./settings-panel.module.css";

const LAYOUT_OPTIONS: { value: LayoutType; label: string }[] = [
  { value: "forceatlas2", label: "ForceAtlas2" },
  { value: "circular", label: "Circular" },
  { value: "force", label: "Force" },
  { value: "circlepack", label: "Circle Pack" },
  { value: "random", label: "Random" },
];

type Props = {
  onLayoutChange?: (layout: LayoutType) => void;
};

export function SettingsPanel({ onLayoutChange }: Props) {
  const [open, setOpen] = useState(false);
  const s = useGraphSettings();

  return (
    <>
      <button
        className={styles.trigger}
        onClick={() => setOpen((v) => !v)}
        aria-label="Graph settings"
        title="Graph settings"
      >
        <SettingsIcon size={16} />
      </button>

      {open && (
        <>
          <div className={styles.backdrop} onClick={() => setOpen(false)} />
          <div className={styles.panel}>
            <p className={styles.heading}>Graph Settings</p>

            {/* --- Toggles --- */}
            <div className={styles.group}>
              <div className={styles.row}>
                <span className={styles.label}>Show Labels</span>
                <input
                  type="checkbox"
                  checked={s.showLabels}
                  onChange={(e) => s.set({ showLabels: e.target.checked })}
                />
              </div>
            </div>

            <div className={styles.group}>
              <div className={styles.row}>
                <span className={styles.label}>Show Edge Labels</span>
                <input
                  type="checkbox"
                  checked={s.showEdgeLabels}
                  onChange={(e) => s.set({ showEdgeLabels: e.target.checked })}
                />
              </div>
            </div>

            <div className={styles.group}>
              <div className={styles.row}>
                <span className={styles.label}>Highlight Neighbors</span>
                <input
                  type="checkbox"
                  checked={s.highlightNeighbors}
                  onChange={(e) => s.set({ highlightNeighbors: e.target.checked })}
                />
              </div>
            </div>

            <div className={styles.group}>
              <div className={styles.row}>
                <span className={styles.label}>Show Legend</span>
                <input
                  type="checkbox"
                  checked={s.showLegend}
                  onChange={(e) => s.set({ showLegend: e.target.checked })}
                />
              </div>
            </div>

            <div className={styles.group}>
              <div className={styles.row}>
                <span className={styles.label}>Show Status Bar</span>
                <input
                  type="checkbox"
                  checked={s.showStatusBar}
                  onChange={(e) => s.set({ showStatusBar: e.target.checked })}
                />
              </div>
            </div>

            <hr className={styles.divider} />

            {/* --- Sliders --- */}
            <div className={styles.group}>
              <div className={styles.rangeRow}>
                <div className={styles.rangeHeader}>
                  <span className={styles.label}>Label Density</span>
                  <span className={styles.rangeValue}>{s.labelDensity.toFixed(1)}</span>
                </div>
                <input
                  className={styles.range}
                  type="range"
                  min={0.1}
                  max={3}
                  step={0.1}
                  value={s.labelDensity}
                  onChange={(e) => s.set({ labelDensity: Number(e.target.value) })}
                />
              </div>
            </div>

            <div className={styles.group}>
              <div className={styles.rangeRow}>
                <div className={styles.rangeHeader}>
                  <span className={styles.label}>Edge Curvature</span>
                  <span className={styles.rangeValue}>{s.edgeCurvature.toFixed(2)}</span>
                </div>
                <input
                  className={styles.range}
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={s.edgeCurvature}
                  onChange={(e) => s.set({ edgeCurvature: Number(e.target.value) })}
                />
              </div>
            </div>

            <div className={styles.group}>
              <div className={styles.rangeRow}>
                <div className={styles.rangeHeader}>
                  <span className={styles.label}>Animation (ms)</span>
                  <span className={styles.rangeValue}>{s.animationDuration}</span>
                </div>
                <input
                  className={styles.range}
                  type="range"
                  min={100}
                  max={2000}
                  step={100}
                  value={s.animationDuration}
                  onChange={(e) => s.set({ animationDuration: Number(e.target.value) })}
                />
              </div>
            </div>

            <hr className={styles.divider} />

            {/* --- Layout dropdown --- */}
            <div className={styles.group}>
              <div className={styles.row}>
                <span className={styles.label}>Default Layout</span>
                <select
                  className={styles.select}
                  value={s.defaultLayout}
                  onChange={(e) => {
                    const v = e.target.value as LayoutType;
                    s.set({ defaultLayout: v });
                    onLayoutChange?.(v);
                  }}
                >
                  {LAYOUT_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <hr className={styles.divider} />

            <button className={styles.resetBtn} onClick={s.reset}>
              Reset to Defaults
            </button>
          </div>
        </>
      )}
    </>
  );
}
