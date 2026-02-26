"use client";

import { useReducer, useEffect, useState, useCallback } from "react";
import { AsyncState } from "@/components/async-state";
import { ConceptGraph } from "@/components/concept-graph";
import { FlashcardList } from "@/components/flashcard-list";
import { PracticeQuizCard } from "@/components/practice-quiz-card";
import { ApiError, apiClient } from "@/lib/api/client";
import { graphReducer, initialGraphState } from "@/lib/graph/graph-state";
import { practiceReducer, initialPracticeState, toPracticeAnswers } from "@/lib/practice/practice-state";
import type { LuckyMode, JsonObject } from "@/lib/api/types";

const WS_ID = 1;

export default function GraphPage() {
  const [state, dispatch] = useReducer(graphReducer, initialGraphState);
  const [query, setQuery] = useState("");
  const [luckyLoading, setLuckyLoading] = useState(false);

  // Practice state (inline)
  const [practiceState, dispatchPractice] = useReducer(practiceReducer, initialPracticeState);
  const [practiceMode, setPracticeMode] = useState<"none" | "flashcards" | "quiz">("none");

  useEffect(() => {
    dispatch({ type: "list_start" });
    apiClient.listConcepts({ workspace_id: WS_ID, q: query || undefined, limit: 50 })
      .then((r) => dispatch({ type: "list_success", concepts: r.concepts }))
      .catch((e) => dispatch({ type: "list_error", error: e instanceof ApiError ? e.message : "Failed to load concepts" }));
  }, [query]);

  const selectConcept = useCallback((conceptId: number) => {
    dispatch({ type: "detail_start" });
    // Reset practice when switching concepts
    dispatchPractice({ type: "reset" });
    setPracticeMode("none");
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

  // Practice actions
  const loadFlashcards = useCallback(() => {
    const conceptId = state.selectedDetail?.concept.concept_id;
    if (!conceptId) return;
    setPracticeMode("flashcards");
    dispatchPractice({ type: "flashcards_start" });
    apiClient.generatePracticeFlashcards({ workspace_id: WS_ID, concept_id: conceptId })
      .then((data) => dispatchPractice({ type: "flashcards_success", data }))
      .catch((e) => dispatchPractice({ type: "flashcards_error", error: e instanceof ApiError ? e.message : "Failed to generate flashcards" }));
  }, [state.selectedDetail]);

  const loadQuiz = useCallback(() => {
    const conceptId = state.selectedDetail?.concept.concept_id;
    if (!conceptId) return;
    setPracticeMode("quiz");
    dispatchPractice({ type: "quiz_start" });
    apiClient.createPracticeQuiz({ workspace_id: WS_ID, user_id: 1, concept_id: conceptId })
      .then((quiz) => dispatchPractice({ type: "quiz_success", quiz }))
      .catch((e) => dispatchPractice({ type: "quiz_error", error: e instanceof ApiError ? e.message : "Failed to create practice quiz" }));
  }, [state.selectedDetail]);

  const submitQuiz = useCallback(() => {
    if (!practiceState.quiz) return;
    dispatchPractice({ type: "submit_start" });
    apiClient.submitPracticeQuiz(practiceState.quiz.quiz_id, {
      workspace_id: WS_ID,
      user_id: 1,
      answers: toPracticeAnswers(practiceState.quiz.items, practiceState.answers),
    })
      .then((result) => dispatchPractice({ type: "submit_success", result }))
      .catch((e) => dispatchPractice({ type: "submit_error", error: e instanceof ApiError ? e.message : "Failed to submit practice quiz" }));
  }, [practiceState.quiz, practiceState.answers]);

  const { phase, concepts, selectedDetail, subgraph, luckyPick, error } = state;
  const pick = luckyPick?.pick as (JsonObject & { concept_id?: number; canonical_name?: string; description?: string; hop_distance?: number | null }) | undefined;

  return (
    <div className="graph-explorer">
      {/* Graph visualization — left */}
      <section className="panel graph-viz-panel">
        <div className="graph-viz-header">
          <h2>Knowledge Graph</h2>
          <input
            className="concept-search"
            type="search"
            placeholder="Search concepts..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ maxWidth: '16rem' }}
          />
        </div>
        <AsyncState loading={phase === "loading_list" || phase === "loading_detail"} error={phase === "error" && !selectedDetail ? error : null} empty={phase === "list_ready" && concepts.length === 0} emptyLabel="No concepts found." />
        {concepts.length > 0 && (!selectedDetail || query.trim().length > 0) ? (
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
                  onClick={loadFlashcards}
                  disabled={practiceState.phase === "loading_flashcards"}
                >
                  {practiceState.phase === "loading_flashcards" ? "Generating..." : "Flashcards"}
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
                    onClick={() => { dispatchPractice({ type: "reset" }); setPracticeMode("none"); }}
                    style={{ marginLeft: 'auto' }}
                  >
                    ✕
                  </button>
                )}
              </div>

              {/* Flashcard display */}
              {practiceState.flashcards ? (
                <FlashcardList flashcards={practiceState.flashcards.flashcards} conceptName={practiceState.flashcards.concept_name} />
              ) : null}

              {/* Quiz display */}
              {practiceState.quiz || practiceState.phase === "loading_quiz" || (practiceState.phase === "error" && practiceMode === "quiz") ? (
                <PracticeQuizCard
                  state={practiceState}
                  onAnswerChange={(id, val) => dispatchPractice({ type: "answer", item_id: id, answer: val })}
                  onSubmitQuiz={submitQuiz}
                  onReset={() => { dispatchPractice({ type: "reset" }); setPracticeMode("none"); }}
                />
              ) : null}

              {/* Flashcard error */}
              {practiceState.phase === "error" && practiceMode === "flashcards" && !practiceState.flashcards ? (
                <p className="status error">{practiceState.error}</p>
              ) : null}
            </div>
          </>
        ) : null}
      </section>
    </div>
  );
}
