"use client";

/**
 * Drop-in replacement for @react-sigma/core's SigmaContainer that creates
 * the Sigma instance ONCE and updates graph/settings in-place — avoiding
 * the kill→recreate lifecycle that causes "could not find a suitable program
 * for node type circle" errors with Turbopack HMR and Next.js navigation.
 *
 * Children access the Sigma instance via useSigma() from @react-sigma/core
 * (we provide the same context shape).
 */

import React, {
  useRef,
  useState,
  useEffect,
  useLayoutEffect,
  useMemo,
  type PropsWithChildren,
  type CSSProperties,
} from "react";
import { Sigma } from "sigma";
import { SigmaProvider } from "@react-sigma/core";
import type Graph from "graphology";
import type { Settings } from "sigma/settings";

type Props = PropsWithChildren<{
  graph: Graph;
  settings?: Partial<Settings>;
  style?: CSSProperties;
  className?: string;
}>;

export function StableSigmaContainer({
  graph,
  settings = {},
  style,
  className,
  children,
}: Props) {
  const rootRef = useRef<HTMLDivElement>(null);
  const sigmaContainerRef = useRef<HTMLDivElement>(null);
  const sigmaRef = useRef<Sigma | null>(null);
  const [sigma, setSigma] = useState<Sigma | null>(null);

  // --- Create Sigma ONCE when the DOM container mounts ---
  useEffect(() => {
    if (!sigmaContainerRef.current) return;

    const instance = new Sigma(graph, sigmaContainerRef.current, settings);
    sigmaRef.current = instance;
    setSigma(instance);

    return () => {
      // Actual cleanup is done synchronously in useLayoutEffect below.
      // This effect just clears the ref for safety.
      sigmaRef.current = null;
    };
    // Only run on mount/unmount — graph and settings are updated in-place below
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- Update graph in-place when it changes ---
  useEffect(() => {
    if (!sigmaRef.current) return;
    sigmaRef.current.setGraph(graph);
    sigmaRef.current.refresh({ skipIndexation: false });
  }, [graph]);

  // --- Update individual settings in-place when they change ---
  useEffect(() => {
    if (!sigmaRef.current) return;
    const s = sigmaRef.current;
    for (const [key, value] of Object.entries(settings)) {
      try {
        // Only update if value actually changed
        if (s.getSetting(key as keyof Settings) !== value) {
          s.setSetting(key as keyof Settings, value as never);
        }
      } catch {
        // Some settings may not be individually settable
      }
    }
    // After updating all settings, refresh once to apply program changes
    try { s.refresh(); } catch { /* instance may be killed */ }
  }, [settings]);

  // --- Kill sigma synchronously on unmount to prevent stale renders ---
  // useLayoutEffect cleanup runs BEFORE useEffect cleanup, closing the
  // window where graph-event handlers could schedule new rAFs after we
  // cancel the old ones but before kill() clears programs.
  useLayoutEffect(() => {
    return () => {
      if (!sigmaRef.current) return;
      try {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const s = sigmaRef.current as any;
        if (s.renderFrame) {
          cancelAnimationFrame(s.renderFrame);
          s.renderFrame = null;
        }
        if (s.renderHighlightedNodesFrame) {
          cancelAnimationFrame(s.renderHighlightedNodesFrame);
          s.renderHighlightedNodesFrame = null;
        }
        sigmaRef.current.kill();
      } catch {
        // Instance already killed
      }
    };
  }, []);

  const context = useMemo(
    () =>
      sigma && rootRef.current
        ? { sigma, container: rootRef.current }
        : null,
    [sigma],
  );

  const contents =
    context !== null ? (
      <SigmaProvider value={context}>{children}</SigmaProvider>
    ) : null;

  return (
    <div ref={rootRef} className={`react-sigma ${className ?? ""}`} style={style}>
      <div className="sigma-container" ref={sigmaContainerRef} />
      {contents}
    </div>
  );
}
