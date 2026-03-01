"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
  type SimulationNodeDatum,
  type SimulationLinkDatum,
} from "d3-force";
import { zoom as d3Zoom, zoomIdentity, type ZoomBehavior } from "d3-zoom";
import { select } from "d3-selection";
import "d3-transition";
import type { GraphSubgraphNode, GraphSubgraphEdge } from "@/lib/api/types";

type Props = {
  nodes: GraphSubgraphNode[];
  edges: GraphSubgraphEdge[];
  selectedId?: number;
  onSelect: (conceptId: number) => void;
  onBackgroundClick?: () => void;
  width?: number;
  height?: number;
  focusNodeId?: number | null;
  searchHighlight?: string;
  onResetViewReady?: (resetFn: () => void) => void;
  filteredTiers?: ReadonlySet<string>;
};

interface GNode extends SimulationNodeDatum {
  id: number;
  label: string;
  hop: number;
  mastery: string | null;
  tier?: string | null;
}

interface GLink extends SimulationLinkDatum<GNode> {
  weight: number;
}

const MASTERY_COLORS: Record<string, string> = {
  learned: "#2ecc71",
  learning: "#f39c12",
  locked: "#95a5a6",
};

const TIER_COLORS: Record<string, string> = {
  umbrella: '#6366f1',
  topic: '#3b82f6',
  subtopic: '#14b8a6',
  granular: '#6b7280',
};

const TIER_RADIUS_DELTA: Record<string, number> = {
  umbrella: 6,
  topic: 3,
  subtopic: 0,
  granular: -2,
};

export function ConceptGraph({
  nodes,
  edges,
  selectedId,
  onSelect,
  onBackgroundClick,
  width: propWidth,
  height: propHeight,
  focusNodeId,
  searchHighlight,
  onResetViewReady,
  filteredTiers,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const simRef = useRef<ReturnType<typeof forceSimulation<GNode>> | null>(null);
  const zoomRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const onSelectRef = useRef(onSelect);
  const onBackgroundClickRef = useRef(onBackgroundClick);
  const nodeGroupsRef = useRef<{ node: GNode; g: SVGGElement; circle: SVGCircleElement }[]>([]);
  const [size, setSize] = useState({ w: propWidth ?? 600, h: propHeight ?? 380 });
  const [themeKey, setThemeKey] = useState(0);

  // Auto-size from container using ResizeObserver
  useEffect(() => {
    const container = containerRef.current;
    if (!container || (propWidth && propHeight)) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width: cw, height: ch } = entry.contentRect;
        if (cw > 0 && ch > 0) {
          setSize({ w: Math.round(cw), h: Math.round(ch) });
        }
      }
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, [propWidth, propHeight]);

  // Keep callback refs in sync without triggering draw
  useEffect(() => { onSelectRef.current = onSelect; }, [onSelect]);
  useEffect(() => { onBackgroundClickRef.current = onBackgroundClick; }, [onBackgroundClick]);

  // Theme change observer — redraw when data-theme changes
  useEffect(() => {
    const observer = new MutationObserver(() => setThemeKey((k) => k + 1));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);

  const width = propWidth ?? size.w;
  const height = propHeight ?? size.h;

  const draw = useCallback(() => {
    const svg = svgRef.current;
    if (!svg || nodes.length === 0) return;

    const isLargeGraph = nodes.length > 200;
    const isHugeGraph = nodes.length > 500;

    const gNodes: GNode[] = nodes.map((n) => ({
      id: n.concept_id,
      label: n.canonical_name,
      hop: n.hop_distance,
      mastery: n.mastery_status,
      tier: n.tier,
    }));

    const nodeById = new Map(gNodes.map((n) => [n.id, n]));
    const gLinks: GLink[] = edges
      .filter(
        (e) => nodeById.has(e.src_concept_id) && nodeById.has(e.tgt_concept_id),
      )
      .map((e) => ({
        source: nodeById.get(e.src_concept_id)!,
        target: nodeById.get(e.tgt_concept_id)!,
        weight: e.weight,
      }));

    if (simRef.current) simRef.current.stop();

    // Adaptive force parameters based on graph size
    const chargeStrength = isHugeGraph ? -60 : isLargeGraph ? -120 : -200;
    const linkDistance = isHugeGraph ? 40 : isLargeGraph ? 60 : 90;
    const collideRadius = isHugeGraph ? 12 : isLargeGraph ? 20 : 32;
    const alphaDecay = isLargeGraph ? 0.05 : 0.0228;

    const sim = forceSimulation<GNode>(gNodes)
      .alphaDecay(alphaDecay)
      .force(
        "link",
        forceLink<GNode, GLink>(gLinks)
          .id((d) => d.id)
          .distance(linkDistance),
      )
      .force("charge", forceManyBody().strength(chargeStrength))
      .force("center", forceCenter(width / 2, height / 2))
      .force("collide", forceCollide(collideRadius));

    simRef.current = sim;

    // Clear before creating shapes
    while (svg.lastChild) svg.removeChild(svg.lastChild);

    // Read CSS variables for theme-aware colors
    const cs = getComputedStyle(document.documentElement);
    const textColor = cs.getPropertyValue('--text').trim() || '#10243e';
    const lineColor = cs.getPropertyValue('--line').trim() || '#c8d8e9';
    const bgColor = cs.getPropertyValue('--bg').trim() || '#fff';

    // Create marker definition for edge arrows
    const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    const marker = document.createElementNS("http://www.w3.org/2000/svg", "marker");
    marker.setAttribute("id", "arrow");
    marker.setAttribute("viewBox", "0 -5 10 10");
    marker.setAttribute("refX", "8");
    marker.setAttribute("refY", "0");
    marker.setAttribute("markerWidth", "6");
    marker.setAttribute("markerHeight", "6");
    marker.setAttribute("orient", "auto");
    const markerPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
    markerPath.setAttribute("d", "M0,-5L10,0L0,5");
    markerPath.setAttribute("fill", lineColor);
    marker.appendChild(markerPath);
    defs.appendChild(marker);
    svg.appendChild(defs);

    // Create a top-level <g> for zoom/pan transforms
    const rootG = document.createElementNS("http://www.w3.org/2000/svg", "g");
    rootG.setAttribute("class", "graph-zoom-root");
    svg.appendChild(rootG);

    const edgeGroups = gLinks.map((link) => {
      const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
      const line = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "line",
      );
      line.setAttribute("stroke", lineColor);
      line.setAttribute("marker-end", "url(#arrow)");
      line.setAttribute(
        "stroke-width",
        String(Math.min(3, Math.max(1, link.weight * 0.5))),
      );

      let label: SVGTextElement | null = null;
      if (!isLargeGraph) {
        label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.setAttribute("fill", lineColor);
        label.setAttribute("font-size", "9");
        label.setAttribute("text-anchor", "middle");
        label.textContent = link.weight.toFixed(2);
        g.appendChild(label);
      }

      g.appendChild(line);
      rootG.appendChild(g);
      return { link, line, label };
    });

    // Use consistent radius — selection shown via stroke only (no jank)
    const nodeRadius = isHugeGraph ? 6 : isLargeGraph ? 10 : 14;
    const fontSize = isHugeGraph ? "7" : isLargeGraph ? "9" : "11";

    // Determine focused node set for focus mode
    const focusedSet = new Set<number>();
    if (focusNodeId != null) {
      focusedSet.add(focusNodeId);
      for (const e of edges) {
        if (e.src_concept_id === focusNodeId) focusedSet.add(e.tgt_concept_id);
        if (e.tgt_concept_id === focusNodeId) focusedSet.add(e.src_concept_id);
      }
    }
    const hasFocus = focusedSet.size > 0;

    const nodeGroups = gNodes.map((n) => {
      const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
      g.setAttribute("cursor", "grab");

      const tierDelta = n.tier != null ? (TIER_RADIUS_DELTA[n.tier] ?? 0) : 0;
      const effectiveRadius = nodeRadius + tierDelta;
      const masteryFill = MASTERY_COLORS[n.mastery ?? ""];
      const nodeFill = masteryFill ?? (n.tier != null ? (TIER_COLORS[n.tier] ?? "#0f5f9c") : "#0f5f9c");

      const circle = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "circle",
      );
      circle.setAttribute("r", String(effectiveRadius));
      circle.setAttribute("fill", nodeFill);
      circle.setAttribute("stroke", bgColor);
      circle.setAttribute("stroke-width", "2");

      // Dim non-focused nodes
      const isFocused = !hasFocus || focusedSet.has(n.id);
      if (hasFocus && !isFocused) {
        g.setAttribute("opacity", "0.2");
      }

      // Hide node labels for huge graphs
      let text: SVGTextElement | null = null;
      if (!isHugeGraph) {
        text = document.createElementNS(
          "http://www.w3.org/2000/svg",
          "text",
        );
        text.setAttribute("text-anchor", "middle");
        text.setAttribute("font-size", fontSize);
        text.setAttribute("fill", textColor);
        text.setAttribute("pointer-events", "none");
        const maxLen = isLargeGraph ? 12 : 16;
        const labelText = n.label.length > maxLen ? n.label.slice(0, maxLen - 2) + "…" : n.label;
        text.textContent = labelText;
        g.appendChild(text);
      }

      g.appendChild(circle);
      rootG.appendChild(g);

      // ── Drag behavior per node ──
      let dragStarted = false;
      let wasDragged = false;
      let dragStartX = 0;
      let dragStartY = 0;

      g.addEventListener("pointerdown", (ev) => {
        ev.stopPropagation();
        dragStarted = true;
        wasDragged = false;
        dragStartX = ev.clientX;
        dragStartY = ev.clientY;
        g.setAttribute("cursor", "grabbing");
        g.setPointerCapture(ev.pointerId);
        // Heat up the simulation for dragging
        sim.alphaTarget(0.3).restart();
        n.fx = n.x;
        n.fy = n.y;
      });

      g.addEventListener("pointermove", (ev) => {
        if (!dragStarted) return;
        const dx = ev.clientX - dragStartX;
        const dy = ev.clientY - dragStartY;
        if (Math.abs(dx) > 3 || Math.abs(dy) > 3) wasDragged = true;

        // Get current zoom transform to account for pan/zoom
        const rootTransform = rootG.getAttribute("transform");
        let scale = 1, tx = 0, ty = 0;
        if (rootTransform) {
          const m = rootTransform.match(/translate\(([-\d.]+)[, ]+([-\d.]+)\)\s*scale\(([-\d.]+)\)/);
          if (m) {
            tx = parseFloat(m[1]);
            ty = parseFloat(m[2]);
            scale = parseFloat(m[3]);
          }
        }
        const rect = svg.getBoundingClientRect();
        n.fx = (ev.clientX - rect.left - tx) / scale;
        n.fy = (ev.clientY - rect.top - ty) / scale;
      });

      const endDrag = (ev: PointerEvent) => {
        if (!dragStarted) return;
        dragStarted = false;
        g.setAttribute("cursor", "grab");
        g.releasePointerCapture(ev.pointerId);
        sim.alphaTarget(0);
        n.fx = null;
        n.fy = null;
        if (!wasDragged) {
          onSelectRef.current(n.id);
        }
      };

      g.addEventListener("pointerup", endDrag);
      g.addEventListener("pointercancel", endDrag);

      return { node: n, g, circle, text };
    });

    // Store node group refs for in-place search highlight updates
    nodeGroupsRef.current = nodeGroups.map(({ node, g, circle }) => ({ node, g, circle }));

    sim.on("tick", () => {
      for (const { node, circle, text } of nodeGroups) {
        // No hard clamping — zoom/pan handles viewport
        circle.setAttribute("cx", String(node.x ?? 0));
        circle.setAttribute("cy", String(node.y ?? 0));
        if (text) {
          text.setAttribute("x", String(node.x ?? 0));
          text.setAttribute("y", String((node.y ?? 0) + parseFloat(circle.getAttribute("r") ?? String(nodeRadius)) + 14));
        }
      }

      for (const { link, line, label } of edgeGroups) {
        const s = link.source as GNode;
        const t = link.target as GNode;

        const dx = (t.x ?? 0) - (s.x ?? 0);
        const dy = (t.y ?? 0) - (s.y ?? 0);
        const len = Math.sqrt(dx * dx + dy * dy) || 1;
        const offsetX = (dx * (nodeRadius + 4)) / len;
        const offsetY = (dy * (nodeRadius + 4)) / len;

        line.setAttribute("x1", String(s.x ?? 0));
        line.setAttribute("y1", String(s.y ?? 0));
        line.setAttribute("x2", String((t.x ?? 0) - offsetX));
        line.setAttribute("y2", String((t.y ?? 0) - offsetY));

        if (label) {
          label.setAttribute("x", String(((s.x ?? 0) + (t.x ?? 0)) / 2));
          label.setAttribute("y", String(((s.y ?? 0) + (t.y ?? 0)) / 2 - 4));
        }
      }
    });

    // ── Zoom / Pan behavior ──
    const svgSel = select<SVGSVGElement, unknown>(svg);
    const zoomBehavior = d3Zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.15, 5])
      .on("zoom", (event) => {
        const { x, y, k } = event.transform;
        rootG.setAttribute("transform", `translate(${x}, ${y}) scale(${k})`);
      });
    zoomRef.current = zoomBehavior;
    svgSel.call(zoomBehavior);
    // Reset to identity transform
    svgSel.call(zoomBehavior.transform, zoomIdentity);

    // Expose reset function to parent
    if (onResetViewReady) {
      onResetViewReady(() => {
        if (svgRef.current && zoomRef.current) {
          select<SVGSVGElement, unknown>(svgRef.current)
            .transition()
            .duration(300)
            .call(zoomRef.current.transform, zoomIdentity);
        }
      });
    }

    // Run simulation
    const simTimeout = isHugeGraph ? 1500 : isLargeGraph ? 2000 : 3000;
    sim.alpha(1).restart();
    setTimeout(() => sim.stop(), simTimeout);
  }, [nodes, edges, width, height, focusNodeId, themeKey]);

  useEffect(() => {
    draw();
    return () => {
      simRef.current?.stop();
      // Clean up zoom behavior
      if (svgRef.current) {
        select(svgRef.current).on(".zoom", null);
      }
    };
  }, [draw]);

  // ── In-place search highlight (no simulation rebuild) ──
  useEffect(() => {
    const groups = nodeGroupsRef.current;
    if (groups.length === 0) return;
    const searchLower = (searchHighlight ?? "").toLowerCase();

    for (const { node, g, circle } of groups) {
      // Remove any existing search ring
      const oldRing = g.querySelector("circle[data-search-ring]");
      if (oldRing) oldRing.remove();

      const isMatch = searchLower && node.label.toLowerCase().includes(searchLower);

      // Dim non-matching nodes when search is active
      if (searchLower && !isMatch) {
        g.setAttribute("opacity", "0.2");
      } else {
        g.removeAttribute("opacity");
      }

      // Add highlight ring to matching nodes
      if (isMatch) {
        const ring = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        ring.setAttribute("data-search-ring", "1");
        ring.setAttribute("cx", circle.getAttribute("cx") ?? "0");
        ring.setAttribute("cy", circle.getAttribute("cy") ?? "0");
        ring.setAttribute("r", String(parseFloat(circle.getAttribute("r") ?? "14") + 4));
        ring.setAttribute("fill", "none");
        ring.setAttribute("stroke", "#eab308");
        ring.setAttribute("stroke-width", "2.5");
        g.insertBefore(ring, g.firstChild);
      }
    }
  }, [searchHighlight]);

  // ── In-place selection highlight (no simulation rebuild) ──
  useEffect(() => {
    const groups = nodeGroupsRef.current;
    if (groups.length === 0) return;
    const cs = getComputedStyle(document.documentElement);
    const bgColor = cs.getPropertyValue('--bg').trim() || '#fff';
    for (const { node, circle } of groups) {
      circle.setAttribute("stroke", node.id === selectedId ? "#0f5f9c" : bgColor);
      circle.setAttribute("stroke-width", node.id === selectedId ? "3" : "2");
    }
  }, [selectedId]);

  // ── In-place tier filter dimming (no simulation rebuild) ──
  useEffect(() => {
    const groups = nodeGroupsRef.current;
    if (groups.length === 0) return;
    if (!filteredTiers || filteredTiers.size === 0) {
      for (const { g } of groups) g.removeAttribute("opacity");
      return;
    }
    for (const { node, g } of groups) {
      if (node.tier && filteredTiers.has(node.tier)) {
        g.removeAttribute("opacity");
      } else {
        g.setAttribute("opacity", "0.15");
      }
    }
  }, [filteredTiers]);

  if (nodes.length === 0) {
    return <p className="status empty">No graph data yet.</p>;
  }

  return (
    <div ref={containerRef} className="concept-graph-container" style={{ width: '100%', height: '100%', minHeight: 200 }}>
      <svg
        ref={svgRef}
        className="concept-graph-svg"
        width={width}
        height={height}
        style={{ cursor: "grab" }}
        onDoubleClick={(e) => {
          if (e.target === svgRef.current && onBackgroundClickRef.current) {
            onBackgroundClickRef.current();
          }
        }}
      />
    </div>
  );
}
