import MiniSearch from "minisearch";
import type { GraphSubgraphNode } from "@/lib/api/types";

export interface GraphSearchResult {
  nodeKey: string;
  conceptId: number;
  label: string;
  score: number;
}

export function buildSearchIndex(nodes: GraphSubgraphNode[]): MiniSearch {
  const engine = new MiniSearch({
    fields: ["label", "description"],
    storeFields: ["label", "nodeKey", "conceptId"],
    searchOptions: {
      prefix: true,
      fuzzy: 0.3,
      boost: { label: 2 },
    },
  });

  engine.addAll(
    nodes.map((n) => ({
      id: n.concept_id,
      label: n.canonical_name,
      description: n.description || "",
      nodeKey: String(n.concept_id),
      conceptId: n.concept_id,
    })),
  );

  return engine;
}

export function searchNodes(
  engine: MiniSearch,
  query: string,
): Set<string> {
  if (!query.trim()) return new Set();

  const results = engine.search(query);
  return new Set(results.map((r) => String(r.id)));
}
