"use client";

import { useReducer, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { AsyncState } from "@/components/async-state";
import { FlashcardList } from "@/components/flashcard-list";
import { PracticeQuizCard } from "@/components/practice-quiz-card";
import { ApiError, apiClient } from "@/lib/api/client";
import { practiceReducer, initialPracticeState, toPracticeAnswers } from "@/lib/practice/practice-state";

export default function PracticePage() {
  const params = useSearchParams();
  const workspaceId = Number(params.get("workspace_id") || "1");
  const conceptId = Number(params.get("concept_id") || "1");
  const initialMode = params.get("mode"); // "quiz" or null (flashcards)

  const [state, dispatch] = useReducer(practiceReducer, initialPracticeState);

  const loadFlashcards = useCallback(() => {
    dispatch({ type: "flashcards_start" });
    apiClient.generatePracticeFlashcards({ workspace_id: workspaceId, concept_id: conceptId })
      .then((data) => dispatch({ type: "flashcards_success", data }))
      .catch((e) => dispatch({ type: "flashcards_error", error: e instanceof ApiError ? e.message : "Failed to generate flashcards" }));
  }, [workspaceId, conceptId]);

  const loadQuiz = useCallback(() => {
    dispatch({ type: "quiz_start" });
    apiClient.createPracticeQuiz({ workspace_id: workspaceId, user_id: 1, concept_id: conceptId })
      .then((quiz) => dispatch({ type: "quiz_success", quiz }))
      .catch((e) => dispatch({ type: "quiz_error", error: e instanceof ApiError ? e.message : "Failed to create practice quiz" }));
  }, [workspaceId, conceptId]);

  const submitQuiz = useCallback(() => {
    if (!state.quiz) return;
    dispatch({ type: "submit_start" });
    apiClient.submitPracticeQuiz(state.quiz.quiz_id, {
      workspace_id: workspaceId,
      user_id: 1,
      answers: toPracticeAnswers(state.quiz.items, state.answers),
    })
      .then((result) => dispatch({ type: "submit_success", result }))
      .catch((e) => dispatch({ type: "submit_error", error: e instanceof ApiError ? e.message : "Failed to submit practice quiz" }));
  }, [workspaceId, state.quiz, state.answers]);

  const { phase, flashcards, quiz } = state;

  return (
    <section className="panel stack">
      <h1>Practice</h1>
      <p className="field-label">Workspace {workspaceId} · Concept {conceptId}</p>
      <span className="practice-badge">Practice only — does not affect mastery</span>

      {phase === "idle" ? (
        <div className="button-row">
          <button type="button" onClick={loadFlashcards}>Generate flashcards</button>
          <button type="button" className="secondary" onClick={loadQuiz}>Practice quiz</button>
        </div>
      ) : null}

      {/* Flashcard states */}
      {phase === "loading_flashcards" ? <AsyncState loading error={null} empty={false} /> : null}
      {flashcards ? <FlashcardList flashcards={flashcards.flashcards} conceptName={flashcards.concept_name} /> : null}
      {phase === "flashcards_ready" || flashcards ? (
        <div className="button-row">
          <button type="button" className="secondary" onClick={() => dispatch({ type: "reset" })}>Back</button>
        </div>
      ) : null}

      {/* Practice quiz states */}
      {quiz || phase === "loading_quiz" || (phase === "error" && !flashcards) ? (
        <PracticeQuizCard
          state={state}
          onAnswerChange={(id, val) => dispatch({ type: "answer", item_id: id, answer: val })}
          onSubmitQuiz={submitQuiz}
          onReset={() => dispatch({ type: "reset" })}
        />
      ) : null}

      {/* Error on flashcard load */}
      {phase === "error" && !quiz && !flashcards ? (
        <div className="stack">
          <p className="status error">Error: {state.error}</p>
          <div className="button-row">
            <button type="button" className="secondary" onClick={() => dispatch({ type: "reset" })}>Back</button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
