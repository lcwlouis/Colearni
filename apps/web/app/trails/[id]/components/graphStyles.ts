import type { CSSProperties } from "react";

import type { ConceptEdge, ConceptLevel, ConceptNode, MasteryStatus, RelationType } from "@/lib/types";

export interface FocusSet {
  selected: string | null;
  prerequisites: Set<string>;
  dependents: Set<string>;
  contained: Set<string>;
  containers: Set<string>;
  related: Set<string>;
}

export function buildFocusSet(
  edges: ConceptEdge[],
  selectedNodeId: string | null,
): FocusSet {
  const focusSet: FocusSet = {
    selected: selectedNodeId,
    prerequisites: new Set(),
    dependents: new Set(),
    contained: new Set(),
    containers: new Set(),
    related: new Set(),
  };
  if (!selectedNodeId) {
    return focusSet;
  }

  edges.forEach((edge) => {
    if (edge.relation_type === "prerequisite") {
      if (edge.target_node_id === selectedNodeId) {
        focusSet.prerequisites.add(edge.source_node_id);
      }
      if (edge.source_node_id === selectedNodeId) {
        focusSet.dependents.add(edge.target_node_id);
      }
    } else if (edge.relation_type === "contains") {
      if (edge.source_node_id === selectedNodeId) {
        focusSet.contained.add(edge.target_node_id);
      }
      if (edge.target_node_id === selectedNodeId) {
        focusSet.containers.add(edge.source_node_id);
      }
    } else if (edge.source_node_id === selectedNodeId) {
      focusSet.related.add(edge.target_node_id);
    } else if (edge.target_node_id === selectedNodeId) {
      focusSet.related.add(edge.source_node_id);
    }
  });

  return focusSet;
}

export function isFocusedNode(nodeId: string, focusSet: FocusSet): boolean {
  if (!focusSet.selected) {
    return true;
  }
  return (
    nodeId === focusSet.selected ||
    focusSet.prerequisites.has(nodeId) ||
    focusSet.dependents.has(nodeId) ||
    focusSet.contained.has(nodeId) ||
    focusSet.containers.has(nodeId) ||
    focusSet.related.has(nodeId)
  );
}

export function isFocusedEdge(edge: ConceptEdge, focusSet: FocusSet): boolean {
  if (!focusSet.selected) {
    return true;
  }
  return edge.source_node_id === focusSet.selected || edge.target_node_id === focusSet.selected;
}

export function nodeStyleFor({
  node,
  status,
  matchesSearch,
  focused,
  selected,
}: {
  node: ConceptNode;
  status: MasteryStatus;
  matchesSearch: boolean;
  focused: boolean;
  selected: boolean;
}): CSSProperties {
  const backgroundByStatus: Record<MasteryStatus, string> = {
    not_started: "#f8fafc",
    learning: "#dbeafe",
    needs_review: "#ffedd5",
    mastered: "#dcfce7",
  };
  const borderByLevel: Record<ConceptLevel, string> = {
    umbrella: "3px solid #0f172a",
    topic: "2px solid #334155",
    subtopic: "2px dashed #64748b",
    granular: "1px solid #94a3b8",
  };
  return {
    width: 220,
    minHeight: 92,
    borderRadius: 8,
    border: selected ? "3px solid #2563eb" : borderByLevel[node.concept_level],
    background: matchesSearch ? backgroundByStatus[status] : "#f1f5f9",
    opacity: focused && matchesSearch ? 1 : 0.24,
    boxShadow: selected
      ? "0 18px 38px rgba(37, 99, 235, 0.24)"
      : focused
        ? "0 10px 24px rgba(15, 23, 42, 0.10)"
        : "none",
  };
}

export function edgeStyleFor(edge: ConceptEdge, focused: boolean): CSSProperties {
  const style: CSSProperties = {
    stroke: edgeColor(edge.relation_type),
    strokeWidth: focused ? 2.4 : 1,
    opacity: focused ? 1 : 0.16,
  };
  if (edge.relation_type === "contains") {
    style.strokeDasharray = "7 5";
  }
  if (edge.relation_type === "application") {
    style.strokeDasharray = "2 4";
  }
  return style;
}

export function edgeColor(relationType: RelationType): string {
  if (relationType === "prerequisite") {
    return "#1d4ed8";
  }
  if (relationType === "contains") {
    return "#475569";
  }
  if (relationType === "application") {
    return "#ea580c";
  }
  return "#94a3b8";
}
