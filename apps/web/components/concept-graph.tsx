"use client";

import { useEffect, useRef, useCallback } from "react";
import {
    forceSimulation,
    forceLink,
    forceManyBody,
    forceCenter,
    forceCollide,
    type SimulationNodeDatum,
    type SimulationLinkDatum,
} from "d3-force";
import type { GraphSubgraphNode, GraphSubgraphEdge } from "@/lib/api/types";

type Props = {
    nodes: GraphSubgraphNode[];
    edges: GraphSubgraphEdge[];
    selectedId?: number;
    onSelect: (conceptId: number) => void;
    width?: number;
    height?: number;
};

interface GNode extends SimulationNodeDatum {
    id: number;
    label: string;
    hop: number;
    mastery: string | null;
}

interface GLink extends SimulationLinkDatum<GNode> {
    weight: number;
}

const MASTERY_COLORS: Record<string, string> = {
    learned: "#2ecc71",
    learning: "#f39c12",
    locked: "#95a5a6",
};

export function ConceptGraph({ nodes, edges, selectedId, onSelect, width = 600, height = 380 }: Props) {
    const svgRef = useRef<SVGSVGElement>(null);
    const simRef = useRef<ReturnType<typeof forceSimulation<GNode>> | null>(null);

    const draw = useCallback(() => {
        const svg = svgRef.current;
        if (!svg || nodes.length === 0) return;

        const gNodes: GNode[] = nodes.map((n) => ({
            id: n.concept_id,
            label: n.canonical_name,
            hop: n.hop_distance,
            mastery: n.mastery_status,
        }));

        const nodeById = new Map(gNodes.map((n) => [n.id, n]));
        const gLinks: GLink[] = edges
            .filter((e) => nodeById.has(e.src_concept_id) && nodeById.has(e.tgt_concept_id))
            .map((e) => ({
                source: nodeById.get(e.src_concept_id)!,
                target: nodeById.get(e.tgt_concept_id)!,
                weight: e.weight,
            }));

        if (simRef.current) simRef.current.stop();

        const sim = forceSimulation<GNode>(gNodes)
            .force("link", forceLink<GNode, GLink>(gLinks).id((d) => d.id).distance(90))
            .force("charge", forceManyBody().strength(-200))
            .force("center", forceCenter(width / 2, height / 2))
            .force("collide", forceCollide(32));

        simRef.current = sim;

        sim.on("tick", () => {
            // Clamp positions
            for (const n of gNodes) {
                n.x = Math.max(30, Math.min(width - 30, n.x ?? width / 2));
                n.y = Math.max(30, Math.min(height - 30, n.y ?? height / 2));
            }

            // Clear and redraw
            while (svg.lastChild) svg.removeChild(svg.lastChild);

            // Edges
            for (const link of gLinks) {
                const s = link.source as GNode;
                const t = link.target as GNode;
                const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
                line.setAttribute("x1", String(s.x ?? 0));
                line.setAttribute("y1", String(s.y ?? 0));
                line.setAttribute("x2", String(t.x ?? 0));
                line.setAttribute("y2", String(t.y ?? 0));
                line.setAttribute("stroke", "#c8d8e9");
                line.setAttribute("stroke-width", String(Math.min(3, Math.max(1, link.weight * 0.5))));
                svg.appendChild(line);
            }

            // Nodes
            for (const n of gNodes) {
                const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
                g.setAttribute("cursor", "pointer");
                g.addEventListener("click", () => onSelect(n.id));

                const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
                circle.setAttribute("cx", String(n.x ?? 0));
                circle.setAttribute("cy", String(n.y ?? 0));
                const r = n.id === selectedId ? 18 : 14;
                circle.setAttribute("r", String(r));
                circle.setAttribute("fill", MASTERY_COLORS[n.mastery ?? ""] ?? "#0f5f9c");
                circle.setAttribute("stroke", n.id === selectedId ? "#0f5f9c" : "#fff");
                circle.setAttribute("stroke-width", n.id === selectedId ? "3" : "2");

                const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
                text.setAttribute("x", String(n.x ?? 0));
                text.setAttribute("y", String((n.y ?? 0) + r + 14));
                text.setAttribute("text-anchor", "middle");
                text.setAttribute("font-size", "11");
                text.setAttribute("fill", "#10243e");
                const label = n.label.length > 16 ? n.label.slice(0, 14) + "…" : n.label;
                text.textContent = label;

                g.appendChild(circle);
                g.appendChild(text);
                svg.appendChild(g);
            }
        });

        // Run for ~120 ticks then stop (bounded)
        sim.alpha(1).restart();
        setTimeout(() => sim.stop(), 3000);
    }, [nodes, edges, selectedId, onSelect, width, height]);

    useEffect(() => {
        draw();
        return () => { simRef.current?.stop(); };
    }, [draw]);

    if (nodes.length === 0) {
        return <p className="status empty">No graph data yet.</p>;
    }

    return (
        <svg
            ref={svgRef}
            className="concept-graph-svg"
            width={width}
            height={height}
            viewBox={`0 0 ${width} ${height}`}
        />
    );
}
