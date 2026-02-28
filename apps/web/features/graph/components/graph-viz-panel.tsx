import { AsyncState } from "@/components/async-state";
import { ConceptGraph } from "@/components/concept-graph";
import type {
  GraphSubgraphNode,
  GraphSubgraphEdge,
  GraphConceptSummary,
  GraphSubgraphResponse,
} from "@/lib/api/types";
import type { GraphState } from "@/lib/graph/graph-state";

interface GraphVizPanelProps {
  state: GraphState;
  dispatch: React.Dispatch<import("@/lib/graph/graph-state").GraphAction>;
  debouncedQuery: string;
  fullGraph: {
    nodes: GraphSubgraphNode[];
    edges: GraphSubgraphEdge[];
    is_truncated?: boolean;
    total_concept_count?: number;
  } | null;
  maxNodes: number;
  setMaxNodes: (n: number) => void;
  maxEdges: number;
  setMaxEdges: (n: number) => void;
  maxHops: number;
  setMaxHops: (n: number) => void;
  graphSearch: string;
  setGraphSearch: (s: string) => void;
  debouncedGraphSearch: string;
  focusNodeId: number | null;
  setFocusNodeId: (id: number | null) => void;
  resetView: (() => void) | null;
  handleResetViewReady: (fn: () => void) => void;
  handleGraphSelect: (id: number) => void;
  handleGraphBgClick: () => void;
  selectConcept: (id: number) => void;
  setQuery: (q: string) => void;
}

export function GraphVizPanel({
  state,
  dispatch,
  debouncedQuery,
  fullGraph,
  maxNodes,
  setMaxNodes,
  maxEdges,
  setMaxEdges,
  maxHops,
  setMaxHops,
  graphSearch,
  setGraphSearch,
  debouncedGraphSearch,
  focusNodeId,
  setFocusNodeId,
  resetView,
  handleResetViewReady,
  handleGraphSelect,
  handleGraphBgClick,
  selectConcept,
  setQuery,
}: GraphVizPanelProps) {
  const { phase, concepts, selectedDetail, subgraph, error } = state;

  return (
    <section className="panel graph-viz-panel">
      <div className="graph-viz-header">
        <div className="graph-controls">
          <label className="graph-control-label">
            Nodes
            <select value={maxNodes} onChange={(e) => setMaxNodes(Number(e.target.value))}>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
              <option value={500}>500</option>
            </select>
          </label>
          <label className="graph-control-label">
            Edges
            <select value={maxEdges} onChange={(e) => setMaxEdges(Number(e.target.value))}>
              <option value={100}>100</option>
              <option value={300}>300</option>
              <option value={600}>600</option>
              <option value={1000}>1000</option>
            </select>
          </label>
          <label className="graph-control-label">
            Depth
            <select value={maxHops} onChange={(e) => setMaxHops(Number(e.target.value))}>
              <option value={1}>1 hop</option>
              <option value={2}>2 hops</option>
              <option value={3}>3 hops</option>
            </select>
          </label>
        </div>
        {fullGraph?.is_truncated && (
          <p className="graph-truncation-banner">
            Showing {fullGraph.nodes.length} of {fullGraph.total_concept_count ?? "?"} concepts (graph truncated)
          </p>
        )}
        <div className="graph-search-inline">
          <input
            type="search"
            placeholder="Highlight node..."
            value={graphSearch}
            onChange={(e) => setGraphSearch(e.target.value)}
            style={{
              fontSize: "0.8rem",
              padding: "0.25rem 0.5rem",
              borderRadius: "0.4rem",
              border: "1px solid var(--line)",
              background: "var(--surface)",
              width: "10rem",
            }}
          />
          {focusNodeId != null && (
            <button
              type="button"
              className="secondary"
              style={{ fontSize: "0.75rem", padding: "0.2rem 0.5rem" }}
              onClick={() => {
                setFocusNodeId(null);
                dispatch({ type: "clear_detail" });
                resetView?.();
              }}
            >
              Clear focus
            </button>
          )}
          {resetView && (
            <button
              type="button"
              className="secondary"
              style={{ fontSize: "0.75rem", padding: "0.2rem 0.5rem" }}
              onClick={() => resetView()}
            >
              Reset view
            </button>
          )}
        </div>
      </div>
      <AsyncState
        loading={phase === "loading_list" || phase === "loading_detail"}
        error={phase === "error" && !selectedDetail ? error : null}
        empty={phase === "list_ready" && concepts.length === 0}
        emptyLabel="No concepts found."
      />

      <div className="graph-legend-bar">
        <span className="graph-legend-dot" style={{ background: "#2ecc71" }} /> Learned
        <span className="graph-legend-dot" style={{ background: "#f39c12" }} /> Learning
        <span className="graph-legend-dot" style={{ background: "#95a5a6" }} /> Locked
        <span className="graph-legend-dot" style={{ background: "#0f5f9c" }} /> Unseen
      </div>
      {concepts.length > 0 && debouncedQuery.trim().length > 0 && !selectedDetail ? (
        <div className="concept-list">
          {concepts.map((c) => (
            <button
              key={c.concept_id}
              type="button"
              className="concept-item"
              onClick={() => {
                setQuery("");
                selectConcept(c.concept_id);
              }}
            >
              <strong>{c.canonical_name}</strong>
              <span className="field-label">
                {c.description.slice(0, 80)}
                {c.description.length > 80 ? "…" : ""}
              </span>
            </button>
          ))}
        </div>
      ) : subgraph ? (
        <ConceptGraph
          nodes={subgraph.nodes}
          edges={subgraph.edges}
          selectedId={selectedDetail?.concept.concept_id}
          onSelect={handleGraphSelect}
          onBackgroundClick={handleGraphBgClick}
          focusNodeId={focusNodeId}
          searchHighlight={debouncedGraphSearch}
          onResetViewReady={handleResetViewReady}
        />
      ) : fullGraph && fullGraph.nodes.length > 0 ? (
        <ConceptGraph
          nodes={fullGraph.nodes}
          edges={fullGraph.edges}
          onSelect={handleGraphSelect}
          onBackgroundClick={handleGraphBgClick}
          focusNodeId={focusNodeId}
          searchHighlight={debouncedGraphSearch}
          onResetViewReady={handleResetViewReady}
        />
      ) : null}
    </section>
  );
}
