import type { HierarchyNode } from "@/lib/api/types";

interface HierarchyBreadcrumbProps {
  path: HierarchyNode[];
}

export function HierarchyBreadcrumb({ path }: HierarchyBreadcrumbProps) {
  if (path.length <= 1) return null;

  return (
    <nav
      aria-label="Concept hierarchy"
      style={{
        fontSize: "0.75rem",
        color: "var(--muted)",
        padding: "0.35rem 0.75rem",
        lineHeight: 1.6,
      }}
    >
      {path.map((node, i) => (
        <span key={node.concept_id}>
          {i > 0 && <span style={{ margin: "0 0.3rem" }}>›</span>}
          {node.name}
        </span>
      ))}
    </nav>
  );
}
