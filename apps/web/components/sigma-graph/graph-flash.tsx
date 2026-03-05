"use client";

import { useEffect } from "react";
import { useSigma } from "@react-sigma/core";

type Props = {
  active: boolean;
  intervalMs?: number;
  flashRef: React.MutableRefObject<boolean>;
};

/**
 * Renderless component that toggles a flash ref on an interval and
 * triggers sigma.refresh() so the node reducer can read the current
 * flash state.  Must be rendered inside a <SigmaContainer>.
 */
export function GraphFlash({ active, intervalMs = 800, flashRef }: Props) {
  const sigma = useSigma();

  useEffect(() => {
    if (!active) {
      flashRef.current = false;
      return;
    }
    const id = setInterval(() => {
      flashRef.current = !flashRef.current;
      try {
        sigma.refresh();
      } catch {
        /* instance killed */
      }
    }, intervalMs);
    return () => clearInterval(id);
  }, [sigma, active, intervalMs, flashRef]);

  return null;
}
