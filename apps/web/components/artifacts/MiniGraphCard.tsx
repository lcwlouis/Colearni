"use client";

import mermaid from "mermaid";
import { useEffect, useMemo, useRef, useState } from "react";

import { ArtifactFrame } from "@/components/artifacts/ArtifactFrame";
import { ArtifactTextFallback } from "@/components/artifacts/ArtifactTextFallback";
import type {
  ArtifactEnvelope,
  MiniGraphEdge,
  MiniGraphNode,
} from "@/lib/artifacts";

// Read-only `mini_graph` template. It is DATA-ONLY: the validated nodes/edges
// are converted to a Mermaid `flowchart` definition and rendered by Mermaid in
// `securityLevel: "strict"` mode (no arbitrary JS/HTML). This reuses the same
// trusted renderer the tutor uses; the component itself never executes payload
// content. Any malformed data or async render failure degrades to the
// envelope's `text_fallback`.

mermaid.initialize({
  startOnLoad: false,
  securityLevel: "strict",
  theme: "neutral",
});

function isValidNode(value: unknown): value is MiniGraphNode {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const node = value as Record<string, unknown>;
  return typeof node.id === "string" && typeof node.label === "string";
}

function isValidEdge(value: unknown): value is MiniGraphEdge {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const edge = value as Record<string, unknown>;
  return typeof edge.source === "string" && typeof edge.target === "string";
}

// Mermaid label text is wrapped in quotes; strip characters that could break
// the flowchart definition string. (Strict mode already blocks HTML/JS.)
function sanitizeLabel(label: string): string {
  return label.replace(/["`\r\n]/g, " ").trim();
}

function buildFlowchart(nodes: MiniGraphNode[], edges: MiniGraphEdge[]): string {
  // Map arbitrary payload ids to safe synthetic Mermaid identifiers.
  const idMap = new Map<string, string>();
  nodes.forEach((node, index) => idMap.set(node.id, `n${index}`));

  const lines = ["flowchart TD"];
  for (const node of nodes) {
    const safeId = idMap.get(node.id)!;
    lines.push(`  ${safeId}["${sanitizeLabel(node.label) || node.id}"]`);
  }
  for (const edge of edges) {
    const source = idMap.get(edge.source);
    const target = idMap.get(edge.target);
    if (!source || !target) {
      continue;
    }
    const label =
      typeof edge.label === "string" ? sanitizeLabel(edge.label) : "";
    if (label.length > 0) {
      lines.push(`  ${source} -->|"${label}"| ${target}`);
    } else {
      lines.push(`  ${source} --> ${target}`);
    }
  }
  return lines.join("\n");
}

export function MiniGraphCard({ envelope }: { envelope: ArtifactEnvelope }) {
  const ref = useRef<HTMLPreElement>(null);
  const [hasError, setHasError] = useState(false);

  const data = envelope.data as unknown as
    | Record<string, unknown>
    | null
    | undefined;
  const rawNodes = data?.nodes;
  const rawEdges = data?.edges;

  const isValid =
    Array.isArray(rawNodes) &&
    rawNodes.length > 0 &&
    rawNodes.every(isValidNode) &&
    Array.isArray(rawEdges) &&
    rawEdges.every(isValidEdge);

  const definition = useMemo(() => {
    if (!isValid) {
      return null;
    }
    return buildFlowchart(rawNodes as MiniGraphNode[], rawEdges as MiniGraphEdge[]);
  }, [isValid, rawNodes, rawEdges]);

  useEffect(() => {
    if (!definition || !ref.current) {
      return;
    }

    let active = true;
    void mermaid
      .render(
        `artifact-mini-graph-${Math.random().toString(36).slice(2)}`,
        definition,
      )
      .then((result) => {
        if (!active || !ref.current) {
          return;
        }
        ref.current.innerHTML = result.svg;
        result.bindFunctions?.(ref.current);
      })
      .catch(() => {
        if (!active) {
          return;
        }
        // Async render failures cannot reach the React error boundary, so
        // degrade locally to the universal text_fallback target.
        setHasError(true);
      });

    return () => {
      active = false;
    };
  }, [definition]);

  if (!isValid || hasError) {
    return <ArtifactTextFallback text={envelope.text_fallback} />;
  }

  return (
    <ArtifactFrame
      title={envelope.title}
      caption={envelope.caption}
      testId="artifact-mini-graph"
    >
      <pre
        ref={ref}
        aria-label="Mini graph diagram"
        className="overflow-x-auto rounded-lg border border-slate-200 bg-white p-3 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900 [&_svg]:mx-auto [&_svg]:h-auto [&_svg]:max-w-full"
      >
        Drawing graph...
      </pre>
    </ArtifactFrame>
  );
}
