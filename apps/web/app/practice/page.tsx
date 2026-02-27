"use client";

import { useReducer, useCallback, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AsyncState } from "@/components/async-state";
import { FlashcardList } from "@/components/flashcard-list";
import { StatefulFlashcardList } from "@/components/stateful-flashcard-list";
import { PracticeQuizCard } from "@/components/practice-quiz-card";
import { ApiError, apiClient } from "@/lib/api/client";
import { practiceReducer, initialPracticeState, toPracticeAnswers } from "@/lib/practice/practice-state";
import { useRequireAuth } from "@/lib/auth";
import type { StatefulFlashcard, FlashcardSelfRating } from "@/lib/api/types";

export default function PracticePage() {
  const auth = useRequireAuth();
  const params = useSearchParams();
  const wsId = auth.activeWorkspaceId ?? params.get("workspace_id") ?? "";
  const conceptId = Number(params.get("concept_id") || "1");

  const [state, dispatch] = useReducer(practiceReducer, initialPracticeState);

  // Stateful flashcard state
  const [statefulCards, setStatefulCards] = useState<StatefulFlashcard[]>([]);
  const [statefulConceptName, setStatefulConceptName] = useState("");
  const [statefulLoading, setStatefulLoading] = useState(false);
  const [statefulError, setStatefulError] = useState<string | null>(null);
  const [ratingInFlight, setRatingInFlight] = useState(false);
  const [showStateful, setShowStateful] = useState(false);

  const loadStatefulFlashcards = useCallback(() => {
    setShowStateful(true);
    setStatefulLoading(true);
    setStatefulError(null);
    apiClient.generateStatefulFlashcards(wsId, { concept_id: conceptId })
      .then((res) => {
        setStatefulCards(res.flashcards);
        setStatefulConceptName(res.concept_name);
      })
      .catch((e) => setStatefulError(e instanceof ApiError ? e.message : "Failed to generate flashcards"))
      .finally(() => setStatefulLoading(false));
  }, [wsId, conceptId]);

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
  }, []);

  const loadFlashcards = useCallback(() => {
    setShowStateful(false);
    dispatch({ type: "flashcards_start" });
    apiClient.generatePracticeFlashcards(wsId, { concept_id: conceptId })
      .then((data) => dispatch({ type: "flashcards_success", data }))
      .catch((e) => dispatch({ type: "flashcards_error", error: e instanceof ApiError ? e.message : "Failed to generate flashcards" }));
  }, [wsId, conceptId]);

  const loadQuiz = useCallback(() => {
    setShowStateful(false);
    dispatch({ type: "quiz_start" });
    apiClient.createPracticeQuiz(wsId, { concept_id: conceptId })
      .then((quiz) => dispatch({ type: "quiz_success", quiz }))
      .catch((e) => dispatch({ type: "quiz_error", error: e instanceof ApiError ? e.message : "Failed to create practice quiz" }));
  }, [wsId, conceptId]);

  const submitQuiz = useCallback(() => {
    if (!state.quiz) return;
    dispatch({ type: "submit_start" });
    apiClient.submitPracticeQuiz(wsId, state.quiz.quiz_id, {
      answers: toPracticeAnswers(state.quiz.items, state.answers),
    })
      .then((result) => dispatch({ type: "submit_success", result }))
      .catch((e) => dispatch({ type: "submit_error", error: e instanceof ApiError ? e.message : "Failed to submit practice quiz" }));
  }, [wsId, state.quiz, state.answers]);

  const resetAll = () => {
    dispatch({ type: "reset" });
    setShowStateful(false);
    setStatefulCards([]);
    setStatefulError(null);
  };

  if (auth.isLoading) return <p>Loading…</p>;

  const { phase, flashcards, quiz } = state;
  const idle = phase === "idle" && !showStateful;

  return (
    <section className="panel stack">
      <h1>Practice</h1>
      <p className="field-label">Workspace {wsId ? wsId.slice(0, 8) : "–"} · Concept {conceptId}</p>

      {idle ? (
        <div className="button-row">
          <button type="button" onClick={loadStatefulFlashcards}>Flashcards (with rating)</button>
          <button type="button" className="secondary" onClick={loadFlashcards}>Quick flashcards</button>
          <button type="button" className="secondary" onClick={loadQuiz}>Practice quiz</button>
        </div>
      ) : null}

      {/* Stateful flashcard states */}
      {showStateful && statefulLoading ? <AsyncState loading error={null} empty={false} /> : null}
      {showStateful && statefulError ? (
        <div className="stack">
          <p className="status error">Error: {statefulError}</p>
          <div className="button-row">
            <button type="button" className="secondary" onClick={resetAll}>Back</button>
          </div>
        </div>
      ) : null}
      {showStateful && statefulCards.length > 0 ? (
        <>
          <StatefulFlashcardList
            flashcards={statefulCards}
            conceptName={statefulConceptName}
            onRate={handleRate}
            ratingInFlight={ratingInFlight}
          />
          <div className="button-row">
            <button type="button" className="secondary" onClick={resetAll}>Back</button>
            <button type="button" className="secondary" onClick={loadStatefulFlashcards}>Generate more</button>
          </div>
        </>
      ) : null}

      {/* Old flashcard states */}
      {phase === "loading_flashcards" ? <AsyncState loading error={null} empty={false} /> : null}
      {flashcards ? <FlashcardList flashcards={flashcards.flashcards} conceptName={flashcards.concept_name} /> : null}
      {(phase === "flashcards_ready" || flashcards) && !showStateful ? (
        <div className="button-row">
          <button type="button" className="secondary" onClick={resetAll}>Back</button>
        </div>
      ) : null}

      {/* Practice quiz states */}
      {quiz || phase === "loading_quiz" || (phase === "error" && !flashcards && !showStateful) ? (
        <PracticeQuizCard
          state={state}
          onAnswerChange={(id, val) => dispatch({ type: "answer", item_id: id, answer: val })}
          onSubmitQuiz={submitQuiz}
          onReset={resetAll}
        />
      ) : null}

      {/* Error on flashcard load */}
      {phase === "error" && !quiz && !flashcards && !showStateful ? (
        <div className="stack">
          <p className="status error">Error: {state.error}</p>
          <div className="button-row">
            <button type="button" className="secondary" onClick={resetAll}>Back</button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
