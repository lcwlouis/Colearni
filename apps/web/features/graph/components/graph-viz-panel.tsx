import { AsyncState } from "@/components/async-state";
import dynamic from "next/dynamic";

const SigmaGraph = dynamic(() => import("@/components/sigma-graph"), {
  ssr: false,
  loading: () => <p style={{ color: "var(--muted)" }}>Loading graph…</p>,
});
import { useState, useCallback } from "react";
import { apiClient } from "@/lib/api/client";
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
  wsId: string;
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
  filteredTiers: ReadonlySet<string>;
  toggleTierFilter: (tier: string) => void;
  clearTierFilter: () => void;
  onGardenerSuccess?: () => void;
}

export function GraphVizPanel({
  state,
  dispatch,
  debouncedQuery,
  wsId,
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
  filteredTiers,
  toggleTierFilter,
  clearTierFilter,
  onGardenerSuccess,
}: GraphVizPanelProps) {
  const { phase, concepts, selectedDetail, subgraph, error } = state;

  const [gardenerLoading, setGardenerLoading] = useState(false);
  const [gardenerMessage, setGardenerMessage] = useState<string | null>(null);

  const handleRunGardener = useCallback(async () => {
    if (!wsId) return;
    setGardenerLoading(true);
    setGardenerMessage(null);
    try {
      const result = await apiClient.runGardener(wsId, { fullScan: true });
      const merged = result.merges_applied;
      const linked = result.links_created ?? 0;
      const pruned = result.pruned_concepts;
      if (merged === 0 && linked === 0 && pruned === 0) {
        setGardenerMessage("No changes needed — graph is clean");
      } else {
        const parts: string[] = [];
        if (merged > 0) parts.push(`Merged ${merged} concept${merged !== 1 ? "s" : ""}`);
        if (linked > 0) parts.push(`linked ${linked} concept${linked !== 1 ? "s" : ""}`);
        if (pruned > 0) parts.push(`pruned ${pruned} orphan${pruned !== 1 ? "s" : ""}`);
        setGardenerMessage(parts.join(", "));
      }
      onGardenerSuccess?.();
      setTimeout(() => setGardenerMessage(null), 4000);
    } catch {
      setGardenerMessage("Gardener failed");
      setTimeout(() => setGardenerMessage(null), 3000);
    } finally {
      setGardenerLoading(false);
    }
  }, [wsId, onGardenerSuccess]);

  // Derive available tiers from fullGraph nodes (deduplicated, sorted)
  const availableTiers = Array.from(
    new Set(
      (fullGraph?.nodes ?? [])
        .map((n) => n.tier)
        .filter((t): t is NonNullable<typeof t> => t != null)
    )
  ).sort() as Array<'umbrella' | 'topic' | 'subtopic' | 'granular'>;

  const TIER_CHIP_STYLES: Record<string, { base: React.CSSProperties; active: React.CSSProperties }> = {
    umbrella: { base: { background: '#f0f0ff', color: '#4338ca', border: '1px solid #c7d2fe' }, active: { background: '#c7d2fe', color: '#3730a3', border: '1px solid #6366f1' } },
    topic:    { base: { background: '#eff6ff', color: '#1d4ed8', border: '1px solid #bfdbfe' }, active: { background: '#bfdbfe', color: '#1e3a8a', border: '1px solid #3b82f6' } },
    subtopic: { base: { background: '#f0fdfa', color: '#0f766e', border: '1px solid #99f6e4' }, active: { background: '#99f6e4', color: '#134e4a', border: '1px solid #14b8a6' } },
    granular: { base: { background: '#f9fafb', color: '#374151', border: '1px solid #d1d5db' }, active: { background: '#d1d5db', color: '#111827', border: '1px solid #6b7280' } },
  };

  const chipBase: React.CSSProperties = {
    display: 'inline-block', padding: '0.15rem 0.6rem', borderRadius: '9999px',
    fontSize: '0.72rem', fontWeight: 600, cursor: 'pointer', userSelect: 'none',
    letterSpacing: '0.03em', transition: 'background 0.15s',
  };

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
          <button
            type="button"
            className="secondary"
            style={{ fontSize: "0.75rem", padding: "0.2rem 0.5rem" }}
            onClick={handleRunGardener}
            disabled={gardenerLoading}
            title="Merge duplicate concepts in the graph"
          >
            {gardenerLoading ? "Running…" : "🌱 Run Gardener"}
          </button>
          {gardenerMessage && (
            <span style={{ fontSize: "0.75rem", color: "var(--text)", alignSelf: "center" }}>
              {gardenerMessage}
            </span>
          )}
        </div>
      </div>

      {availableTiers.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', padding: '0.4rem 0.75rem 0.1rem' }}>
          <button
            type="button"
            onClick={clearTierFilter}
            style={{
              ...chipBase,
              background: filteredTiers.size >= 4 ? 'var(--accent, #4338ca)' : 'var(--surface)',
              color: filteredTiers.size >= 4 ? '#fff' : 'var(--text)',
              border: filteredTiers.size >= 4 ? '1px solid var(--accent, #4338ca)' : '1px solid var(--line)',
              fontWeight: filteredTiers.size >= 4 ? 600 : 400,
            }}
          >
            All
          </button>
          {availableTiers.map((tier) => {
            const isActive = filteredTiers.has(tier);
            const styles = TIER_CHIP_STYLES[tier] ?? TIER_CHIP_STYLES.granular;
            return (
              <button
                key={tier}
                type="button"
                onClick={() => toggleTierFilter(tier)}
                style={{ ...chipBase, ...(isActive ? styles.active : styles.base) }}
              >
                {tier.charAt(0).toUpperCase() + tier.slice(1)}
              </button>
            );
          })}
        </div>
      )}

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
      ) : fullGraph && fullGraph.nodes.length > 0 ? (
        <SigmaGraph
          nodes={fullGraph.nodes}
          edges={fullGraph.edges}
          selectedId={selectedDetail?.concept.concept_id}
          onSelect={handleGraphSelect}
          onBackgroundClick={handleGraphBgClick}
          focusNodeId={focusNodeId}
          searchHighlight={debouncedGraphSearch}
          onResetViewReady={handleResetViewReady}
          filteredTiers={filteredTiers}
          isLoading={phase === "loading_list" || phase === "loading_detail"}
        />
      ) : (
        <SigmaGraph
          nodes={[]}
          edges={[]}
          onSelect={handleGraphSelect}
          onBackgroundClick={handleGraphBgClick}
          isLoading={phase === "loading_list" || phase === "loading_detail"}
        />
      )}
    </section>
  );
}
