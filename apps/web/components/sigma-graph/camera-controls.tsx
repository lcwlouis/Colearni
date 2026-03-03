"use client";

import { useCallback } from "react";
import { ZoomIn, ZoomOut, Home, RotateCw, RotateCcw, Maximize } from "lucide-react";
import { useSigma } from "@react-sigma/core";
import styles from "./camera-controls.module.css";

type Props = {
  containerRef: React.RefObject<HTMLDivElement | null>;
};

export function CameraControls({ containerRef }: Props) {
  const sigma = useSigma();

  const zoomIn = useCallback(() => {
    sigma.getCamera().animatedZoom({ duration: 200 });
  }, [sigma]);

  const zoomOut = useCallback(() => {
    sigma.getCamera().animatedUnzoom({ duration: 200 });
  }, [sigma]);

  const resetView = useCallback(() => {
    sigma.getCamera().animate(
      { x: 0.5, y: 0.5, ratio: 1.1 },
      { duration: 1000 },
    );
  }, [sigma]);

  const rotateCW = useCallback(() => {
    const angle = sigma.getCamera().getState().angle;
    sigma.getCamera().animate(
      { angle: angle + Math.PI / 8 },
      { duration: 200 },
    );
  }, [sigma]);

  const rotateCCW = useCallback(() => {
    const angle = sigma.getCamera().getState().angle;
    sigma.getCamera().animate(
      { angle: angle - Math.PI / 8 },
      { duration: 200 },
    );
  }, [sigma]);

  const toggleFullscreen = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      el.requestFullscreen();
    }
  }, [containerRef]);

  return (
    <div className={styles.toolbar}>
      <button
        className={styles.btn}
        onClick={zoomIn}
        aria-label="Zoom in"
        title="Zoom in (+)"
      >
        <ZoomIn size={16} />
      </button>
      <button
        className={styles.btn}
        onClick={zoomOut}
        aria-label="Zoom out"
        title="Zoom out (−)"
      >
        <ZoomOut size={16} />
      </button>
      <div className={styles.separator} />
      <button
        className={styles.btn}
        onClick={resetView}
        aria-label="Reset view"
        title="Reset view (R)"
      >
        <Home size={16} />
      </button>
      <div className={styles.separator} />
      <button
        className={styles.btn}
        onClick={rotateCW}
        aria-label="Rotate clockwise"
        title="Rotate clockwise"
      >
        <RotateCw size={16} />
      </button>
      <button
        className={styles.btn}
        onClick={rotateCCW}
        aria-label="Rotate counter-clockwise"
        title="Rotate counter-clockwise"
      >
        <RotateCcw size={16} />
      </button>
      <div className={styles.separator} />
      <button
        className={styles.btn}
        onClick={toggleFullscreen}
        aria-label="Toggle fullscreen"
        title="Fullscreen (F)"
      >
        <Maximize size={16} />
      </button>
    </div>
  );
}
