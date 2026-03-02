import type Graph from "graphology";

const MAX_DEPTH = 5;

/** BFS from a node to find all nodes within N hops. */
export function expandFromNode(
  graph: Graph,
  nodeId: string,
  depth: number,
): Set<string> {
  const bounded = Math.min(depth, MAX_DEPTH);
  const visited = new Set<string>([nodeId]);
  let frontier = [nodeId];
  for (let d = 0; d < bounded && frontier.length > 0; d++) {
    const next: string[] = [];
    for (const node of frontier) {
      for (const neighbor of graph.neighbors(node)) {
        if (!visited.has(neighbor)) {
          visited.add(neighbor);
          next.push(neighbor);
        }
      }
    }
    frontier = next;
  }
  return visited;
}

/** Hide all nodes not in keepNodes set. */
export function pruneToSubgraph(
  graph: Graph,
  keepNodes: Set<string>,
): void {
  graph.forEachNode((node) => {
    graph.setNodeAttribute(node, "hidden", !keepNodes.has(node));
  });
  graph.forEachEdge((edge, _attrs, source, target) => {
    graph.setEdgeAttribute(
      edge,
      "hidden",
      !keepNodes.has(source) || !keepNodes.has(target),
    );
  });
}

/** Restore all nodes and edges (unhide). */
export function restoreFullGraph(graph: Graph): void {
  graph.forEachNode((node) => {
    graph.removeNodeAttribute(node, "hidden");
  });
  graph.forEachEdge((edge) => {
    graph.removeEdgeAttribute(edge, "hidden");
  });
}
