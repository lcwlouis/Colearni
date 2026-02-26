"use client";

import { useReducer, useEffect, useState, useCallback } from "react";
import { AsyncState } from "@/components/async-state";
import { ConceptGraph } from "@/components/concept-graph";
import { ApiError, apiClient } from "@/lib/api/client";
import { graphReducer, initialGraphState } from "@/lib/graph/graph-state";
import type { LuckyMode, JsonObject } from "@/lib/api/types";

const WS_ID = 1; // default workspace; could be lifted to context/param later

export default function GraphPage() {
  const [state, dispatch] = useReducer(graphReducer, initialGraphState);
  const [query, setQuery] = useState("");
  const [luckyLoading, setLuckyLoading] = useState(false);

  // Load concept list on mount (bounded, limit=50)
  useEffect(() => {
    dispatch({ type: "list_start" });
    apiClient.listConcepts({ workspace_id: WS_ID, q: query || undefined, limit: 50 })
      .then((r) => dispatch({ type: "list_success", concepts: r.concepts }))
      .catch((e) => dispatch({ type: "list_error", error: e instanceof ApiError ? e.message : "Failed to load concepts" }));
  }, [query]);

  const selectConcept = useCallback((conceptId: number) => {
    dispatch({ type: "detail_start" });
    Promise.all([
      apiClient.getConceptDetail({ workspace_id: WS_ID, concept_id: conceptId }),
      apiClient.getConceptSubgraph({ workspace_id: WS_ID, concept_id: conceptId, max_hops: 2, max_nodes: 40, max_edges: 80 }),
    ])
      .then(([detail, subgraph]) => dispatch({ type: "detail_success", detail, subgraph }))
      .catch((e) => dispatch({ type: "detail_error", error: e instanceof ApiError ? e.message : "Failed to load detail" }));
  }, []);

  const lucky = useCallback((mode: LuckyMode) => {
    const conceptId = state.selectedDetail?.concept.concept_id;
    if (!conceptId) return;
    setLuckyLoading(true);
    dispatch({ type: "clear_lucky" });
    apiClient.getLuckyPick({ workspace_id: WS_ID, concept_id: conceptId, mode, k_hops: 2 })
      .then((pick) => dispatch({ type: "lucky_success", pick }))
      .catch((e) => dispatch({ type: "lucky_error", error: e instanceof ApiError ? e.message : "Lucky pick failed" }))
      .finally(() => setLuckyLoading(false));
  }, [state.selectedDetail]);

  const { phase, concepts, selectedDetail, subgraph, luckyPick, error } = state;
  const pick = luckyPick?.pick as (JsonObject & { concept_id?: number; canonical_name?: string; description?: string; hop_distance?: number | null }) | undefined;

  return (
    <div className="graph-explorer">
      {/* Graph visualization */}
      <section className="panel graph-viz-panel">
        <div className="graph-viz-header">
          <h2>Concept Graph</h2>
          <input
            className="concept-search"
            type="search"
            placeholder="Filter concepts..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <AsyncState loading={phase === "loading_list" || phase === "loading_detail"} error={phase === "error" && !selectedDetail ? error : null} empty={phase === "list_ready" && concepts.length === 0} emptyLabel="No concepts found." />
        {subgraph ? (
          <ConceptGraph
            nodes={subgraph.nodes}
            edges={subgraph.edges}
            selectedId={selectedDetail?.concept.concept_id}
            onSelect={selectConcept}
            width={600}
            height={400}
          />
        ) : concepts.length > 0 && !selectedDetail ? (
          <div className="concept-list">
            {concepts.map((c) => (
              <button
                key={c.concept_id}
                type="button"
                className="concept-item"
                onClick={() => selectConcept(c.concept_id)}
              >
                <strong>{c.canonical_name}</strong>
                <span className="field-label">{c.description.slice(0, 80)}{c.description.length > 80 ? "…" : ""}</span>
              </button>
            ))}
          </div>
        ) : null}
      </section>

      {/* Detail panel */}
      <section className="panel stack">
        <AsyncState loading={phase === "loading_detail"} error={phase === "error" && !!selectedDetail ? error : null} empty={!selectedDetail && phase !== "loading_detail"} emptyLabel="Select a concept to explore." />

        {selectedDetail ? (
          <div className="stack">
            <h1>{selectedDetail.concept.canonical_name}</h1>
            <p>{selectedDetail.concept.description}</p>
            {selectedDetail.concept.aliases.length > 0 ? (
              <p className="field-label">Aliases: {selectedDetail.concept.aliases.join(", ")}</p>
            ) : null}
            <p className="field-label">Connections: {selectedDetail.concept.degree}</p>

            {/* Lucky buttons */}
            <div className="button-row">
              <button type="button" className="secondary" disabled={luckyLoading} onClick={() => lucky("adjacent")}>Adjacent suggestion</button>
              <button type="button" className="secondary" disabled={luckyLoading} onClick={() => lucky("wildcard")}>Wildcard suggestion</button>
            </div>

            {/* Lucky pick display */}
            {pick ? (
              <div className="lucky-pick panel stack">
                <h3>🎲 {luckyPick?.mode === "adjacent" ? "Adjacent" : "Wildcard"} suggestion</h3>
                <p><strong>{String(pick.canonical_name ?? "")}</strong></p>
                <p>{String(pick.description ?? "")}</p>
                {pick.hop_distance != null ? <p className="field-label">Hop distance: {pick.hop_distance}</p> : null}
                {typeof pick.concept_id === "number" ? (
                  <button type="button" onClick={() => selectConcept(pick.concept_id as number)}>Select →</button>
                ) : null}
              </div>
            ) : null}

            {/* Practice entry */}
            <div className="button-row">
              <a href={`/practice?workspace_id=${WS_ID}&concept_id=${selectedDetail.concept.concept_id}`}>
                <button type="button">Generate flashcards</button>
              </a>
              <a href={`/practice?workspace_id=${WS_ID}&concept_id=${selectedDetail.concept.concept_id}&mode=quiz`}>
                <button type="button" className="secondary">Practice quiz</button>
              </a>
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}
