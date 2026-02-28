"use client";

import { useReducer, useEffect, useState, useCallback } from "react";
import { AsyncState } from "@/components/async-state";
import { ConceptGraph } from "@/components/concept-graph";
import { StatefulFlashcardList } from "@/components/stateful-flashcard-list";
import { PracticeQuizCard } from "@/components/practice-quiz-card";
import { ApiError, apiClient } from "@/lib/api/client";
import { graphReducer, initialGraphState } from "@/lib/graph/graph-state";
import { practiceReducer, initialPracticeState, toPracticeAnswers } from "@/lib/practice/practice-state";
import { useRequireAuth } from "@/lib/auth";
import { useDebounce } from "@/lib/hooks/use-debounce";
import type { LuckyMode, JsonObject, StatefulFlashcard, FlashcardSelfRating, GraphSubgraphNode, GraphSubgraphEdge } from "@/lib/api/types";

export default function GraphPage() {
  const auth = useRequireAuth();
  const wsId = auth.activeWorkspaceId ?? "";
  const [state, dispatch] = useReducer(graphReducer, initialGraphState);
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 300);
  const [luckyLoading, setLuckyLoading] = useState(false);

  // Practice state (inline)
  const [practiceState, dispatchPractice] = useReducer(practiceReducer, initialPracticeState);
  const [practiceMode, setPracticeMode] = useState<"none" | "flashcards" | "quiz">("none");

  // Stateful flashcards state
  const [statefulCards, setStatefulCards] = useState<StatefulFlashcard[]>([]);
  const [statefulConceptName, setStatefulConceptName] = useState("");
  const [statefulLoading, setStatefulLoading] = useState(false);
  const [statefulError, setStatefulError] = useState<string | null>(null);
  const [ratingInFlight, setRatingInFlight] = useState(false);

  // Full graph state
  const [fullGraph, setFullGraph] = useState<{ nodes: GraphSubgraphNode[], edges: GraphSubgraphEdge[], is_truncated?: boolean, total_concept_count?: number } | null>(null);

  // Graph controls
  const [maxNodes, setMaxNodes] = useState(100);
  const [maxEdges, setMaxEdges] = useState(300);
  const [maxHops, setMaxHops] = useState(2);
  const [graphSearch, setGraphSearch] = useState("");
  const debouncedGraphSearch = useDebounce(graphSearch, 200);
  const [focusNodeId, setFocusNodeId] = useState<number | null>(null);
  const [resetView, setResetView] = useState<(() => void) | null>(null);

  const handleResetViewReady = useCallback((fn: () => void) => {
    setResetView(() => fn);
  }, []);

  useEffect(() => {
    if (!wsId) return;
    dispatch({ type: "list_start" });
    apiClient.listConcepts(wsId, { q: debouncedQuery || undefined, limit: 50 })
      .then((r) => dispatch({ type: "list_success", concepts: r.concepts }))
      .catch((e) => dispatch({ type: "list_error", error: e instanceof ApiError ? e.message : "Failed to load concepts" }));
  }, [debouncedQuery, wsId]);

  useEffect(() => {
    if (!wsId || debouncedQuery.trim().length > 0 || state.selectedDetail) return;
    apiClient.getFullGraph(wsId, { max_nodes: maxNodes, max_edges: maxEdges })
      .then((res) => setFullGraph(res))
      .catch((e) => console.error("Failed to load full graph overview", e));
  }, [wsId, debouncedQuery, state.selectedDetail, maxNodes, maxEdges]);

  const selectConcept = useCallback((conceptId: number) => {
    dispatch({ type: "detail_start" });
    // Reset practice when switching concepts
    dispatchPractice({ type: "reset" });
    setPracticeMode("none");
    setStatefulCards([]);
    setStatefulError(null);
    Promise.all([
      apiClient.getConceptDetail(wsId, conceptId),
      apiClient.getConceptSubgraph(wsId, conceptId, { max_hops: maxHops, max_nodes: 40, max_edges: 80 }),
    ])
      .then(([detail, subgraph]) => dispatch({ type: "detail_success", detail, subgraph }))
      .catch((e) => dispatch({ type: "detail_error", error: e instanceof ApiError ? e.message : "Failed to load detail" }));
  }, [wsId, maxHops]);

  const lucky = useCallback((mode: LuckyMode) => {
    const conceptId = state.selectedDetail?.concept.concept_id;
    if (!conceptId) return;
    setLuckyLoading(true);
    dispatch({ type: "clear_lucky" });
    apiClient.getLuckyPick(wsId, { concept_id: conceptId, mode, k_hops: 2 })
      .then((pick) => dispatch({ type: "lucky_success", pick }))
      .catch((e) => dispatch({ type: "lucky_error", error: e instanceof ApiError ? e.message : "Lucky pick failed" }))
      .finally(() => setLuckyLoading(false));
  }, [state.selectedDetail]);

  // Practice actions
  const loadStatefulFlashcards = useCallback(() => {
    const conceptId = state.selectedDetail?.concept.concept_id;
    if (!conceptId) return;
    setPracticeMode("flashcards");
    setStatefulLoading(true);
    setStatefulError(null);
    apiClient.generateStatefulFlashcards(wsId, { concept_id: conceptId })
      .then((res) => {
        setStatefulCards(res.flashcards);
        setStatefulConceptName(res.concept_name);
      })
      .catch((e) => setStatefulError(e instanceof ApiError ? e.message : "Failed to generate flashcards"))
      .finally(() => setStatefulLoading(false));
  }, [state.selectedDetail, wsId]);

  const handleRate = useCallback((flashcardId: string, rating: FlashcardSelfRating) => {
    setRatingInFlight(true);
    apiClient.rateFlashcard(wsId, { flashcard_id: flashcardId, self_rating: rating })
      .then((res) => {
        setStatefulCards((prev) =>
          prev.map((c) => c.flashcard_id === res.flashcard_id
            ? { ...c, self_rating: res.self_rating, passed: res.passed }
            : c
          )
        );
      })
      .catch(() => { /* silently fail rating */ })
      .finally(() => setRatingInFlight(false));
  }, [wsId]);

  const loadQuiz = useCallback(() => {
    const conceptId = state.selectedDetail?.concept.concept_id;
    if (!conceptId) return;
    setPracticeMode("quiz");
    dispatchPractice({ type: "quiz_start" });
    apiClient.createPracticeQuiz(wsId, { concept_id: conceptId })
      .then((quiz) => dispatchPractice({ type: "quiz_success", quiz }))
      .catch((e) => dispatchPractice({ type: "quiz_error", error: e instanceof ApiError ? e.message : "Failed to create practice quiz" }));
  }, [state.selectedDetail, wsId]);

  const submitQuiz = useCallback(() => {
    if (!practiceState.quiz) return;
    dispatchPractice({ type: "submit_start" });
    apiClient.submitPracticeQuiz(wsId, practiceState.quiz.quiz_id, {
      answers: toPracticeAnswers(practiceState.quiz.items, practiceState.answers),
    })
      .then((result) => dispatchPractice({ type: "submit_success", result }))
      .catch((e) => dispatchPractice({ type: "submit_error", error: e instanceof ApiError ? e.message : "Failed to submit practice quiz" }));
  }, [practiceState.quiz, practiceState.answers]);

  const handleGraphSelect = useCallback((id: number) => {
    selectConcept(id);
    setFocusNodeId(id);
  }, [selectConcept]);

  const handleGraphBgClick = useCallback(() => {
    dispatch({ type: "clear_detail" });
    setFocusNodeId(null);
  }, []);

  if (auth.isLoading) return <p>Loading…</p>;

  const { phase, concepts, selectedDetail, subgraph, luckyPick, error } = state;
  const pick = luckyPick?.pick as (JsonObject & { concept_id?: number; canonical_name?: string; description?: string; hop_distance?: number | null }) | undefined;

  return (
    <div className="graph-explorer" style={{ display: "flex", height: "100%", width: "100%", background: "var(--bg)", overflow: "hidden", flexDirection: "column" }}>
      {/* Top search bar — native panel header, uncoupled from graph card */}
      <header className="graph-search-header">
        <h2 style={{ margin: 0 }}>Knowledge Graph</h2>
        <input
          className="concept-search"
          type="search"
          placeholder="Search concepts..."
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            if (selectedDetail) dispatch({ type: "clear_detail" });
          }}
        />
      </header>

      <div className="graph-panels">
      {/* Graph visualization — left */}
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
              style={{ fontSize: '0.8rem', padding: '0.25rem 0.5rem', borderRadius: '0.4rem', border: '1px solid var(--line)', background: 'var(--surface)', width: '10rem' }}
            />
            {focusNodeId != null && (
              <button type="button" className="secondary" style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }} onClick={() => { setFocusNodeId(null); dispatch({ type: "clear_detail" }); resetView?.(); }}>Clear focus</button>
            )}
            {resetView && (
              <button type="button" className="secondary" style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }} onClick={() => resetView()}>Reset view</button>
            )}
          </div>
        </div>
        <AsyncState loading={phase === "loading_list" || phase === "loading_detail"} error={phase === "error" && !selectedDetail ? error : null} empty={phase === "list_ready" && concepts.length === 0} emptyLabel="No concepts found." />

        {/* Mastery legend */}
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
                <span className="field-label">{c.description.slice(0, 80)}{c.description.length > 80 ? "…" : ""}</span>
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

      {/* Detail + Practice panel — right */}
      <section className="panel graph-detail-panel">
        <AsyncState loading={phase === "loading_detail"} error={phase === "error" && !!selectedDetail ? error : null} empty={!selectedDetail && phase !== "loading_detail"} emptyLabel="Select a concept to explore." />

        {selectedDetail ? (
          <>
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

            {/* Practice — inline */}
            <div style={{ borderTop: '1px solid var(--line)', paddingTop: '0.75rem', marginTop: '0.25rem' }}>
              <div className="button-row" style={{ marginBottom: '0.75rem' }}>
                <button
                  type="button"
                  className={practiceMode === "flashcards" ? "" : "secondary"}
                  onClick={loadStatefulFlashcards}
                  disabled={statefulLoading}
                >
                  {statefulLoading ? "Generating..." : "Flashcards"}
                </button>
                <button
                  type="button"
                  className={practiceMode === "quiz" ? "" : "secondary"}
                  onClick={loadQuiz}
                  disabled={practiceState.phase === "loading_quiz"}
                >
                  {practiceState.phase === "loading_quiz" ? "Creating..." : "Practice quiz"}
                </button>
                {practiceMode !== "none" && (
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => { dispatchPractice({ type: "reset" }); setPracticeMode("none"); setStatefulCards([]); }}
                    style={{ marginLeft: 'auto' }}
                  >
                    ✕
                  </button>
                )}
              </div>

              {/* Flashcard display */}
              {practiceMode === "flashcards" && statefulCards.length > 0 ? (
                <div className="stack" style={{ gap: "1rem" }}>
                  <StatefulFlashcardList
                    flashcards={statefulCards}
                    conceptName={statefulConceptName}
                    onRate={handleRate}
                    ratingInFlight={ratingInFlight}
                  />
                  <div className="button-row">
                    <button type="button" className="secondary" disabled={statefulLoading} onClick={loadStatefulFlashcards}>Generate more</button>
                  </div>
                </div>
              ) : null}

              {/* Quiz display */}
              {practiceState.quiz || practiceState.phase === "loading_quiz" || (practiceState.phase === "error" && practiceMode === "quiz") ? (
                <PracticeQuizCard
                  state={practiceState}
                  onAnswerChange={(id, v) => dispatchPractice({ type: "answer", item_id: id, answer: v })}
                  onSubmitQuiz={submitQuiz}
                  onReset={() => dispatchPractice({ type: "reset" })}
                  onNextQuiz={() => {
                    if (!wsId || !state.selectedDetail) return;
                    dispatchPractice({ type: "quiz_start" });
                    apiClient.createPracticeQuiz(wsId, { concept_id: state.selectedDetail.concept.concept_id })
                      .then((quiz) => dispatchPractice({ type: "quiz_success", quiz }))
                      .catch((e) => dispatchPractice({ type: "quiz_error", error: e instanceof ApiError ? e.message : "Failed to create practice quiz" }));
                  }}
                />
              ) : null}

              {/* Flashcard error */}
              {practiceMode === "flashcards" && statefulError ? (
                <p className="status error">{statefulError}</p>
              ) : null}
            </div>
          </>
        ) : null}
      </section>
      </div>
    </div>
  );
}
