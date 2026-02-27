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
import type { LuckyMode, JsonObject, StatefulFlashcard, FlashcardSelfRating, GraphSubgraphNode, GraphSubgraphEdge } from "@/lib/api/types";

export default function GraphPage() {
  const auth = useRequireAuth();
  const wsId = auth.activeWorkspaceId ?? "";
  const [state, dispatch] = useReducer(graphReducer, initialGraphState);
  const [query, setQuery] = useState("");
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
  const [fullGraph, setFullGraph] = useState<{ nodes: GraphSubgraphNode[], edges: GraphSubgraphEdge[] } | null>(null);

  useEffect(() => {
    if (!wsId) return;
    dispatch({ type: "list_start" });
    apiClient.listConcepts(wsId, { q: query || undefined, limit: 50 })
      .then((r) => dispatch({ type: "list_success", concepts: r.concepts }))
      .catch((e) => dispatch({ type: "list_error", error: e instanceof ApiError ? e.message : "Failed to load concepts" }));
  }, [query, wsId]);

  useEffect(() => {
    if (!wsId || query.trim().length > 0 || state.selectedDetail) return;
    apiClient.getFullGraph(wsId, { max_nodes: 100, max_edges: 300 })
      .then((res) => setFullGraph(res))
      .catch((e) => console.error("Failed to load full graph overview", e));
  }, [wsId, query, state.selectedDetail]);

  const selectConcept = useCallback((conceptId: number) => {
    dispatch({ type: "detail_start" });
    // Reset practice when switching concepts
    dispatchPractice({ type: "reset" });
    setPracticeMode("none");
    setStatefulCards([]);
    setStatefulError(null);
    Promise.all([
      apiClient.getConceptDetail(wsId, conceptId),
      apiClient.getConceptSubgraph(wsId, conceptId, { max_hops: 2, max_nodes: 40, max_edges: 80 }),
    ])
      .then(([detail, subgraph]) => dispatch({ type: "detail_success", detail, subgraph }))
      .catch((e) => dispatch({ type: "detail_error", error: e instanceof ApiError ? e.message : "Failed to load detail" }));
  }, [wsId]);

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

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
      {/* Graph visualization — left */}
      <section className="panel graph-viz-panel">
        <div className="graph-viz-header">
        </div>
        <AsyncState loading={phase === "loading_list" || phase === "loading_detail"} error={phase === "error" && !selectedDetail ? error : null} empty={phase === "list_ready" && concepts.length === 0} emptyLabel="No concepts found." />
        {concepts.length > 0 && query.trim().length > 0 && !selectedDetail ? (
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
            onSelect={selectConcept}
            onBackgroundClick={() => dispatch({ type: "clear_detail" })}
            width={700}
            height={500}
          />
        ) : fullGraph && fullGraph.nodes.length > 0 ? (
          <ConceptGraph
            nodes={fullGraph.nodes}
            edges={fullGraph.edges}
            onSelect={selectConcept}
            onBackgroundClick={() => dispatch({ type: "clear_detail" })}
            width={700}
            height={500}
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
