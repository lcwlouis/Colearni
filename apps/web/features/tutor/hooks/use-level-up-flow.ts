import { useEffect, useReducer } from "react";
import { apiClient } from "@/lib/api/client";
import type { GraphConceptSummary } from "@/lib/api/types";
import {
  initialLevelUpState,
  levelUpReducer,
  toSubmitAnswers,
} from "@/lib/tutor/level-up-state";
import { errorText } from "../types";

export function useLevelUpFlow(
  wsId: string | undefined,
  currentConcept: GraphConceptSummary | null,
  ensureSession: () => Promise<string | null>,
) {
  const [levelUpState, dispatchLevelUp] = useReducer(levelUpReducer, initialLevelUpState);

  // Restore from localStorage keyed to concept
  useEffect(() => {
    if (!wsId || !currentConcept) return;
    const key = `colearni_levelup_${wsId}_concept_${currentConcept.concept_id}`;
    try {
      const saved = localStorage.getItem(key);
      if (saved) {
        dispatchLevelUp({ type: "restore", state: JSON.parse(saved) });
      } else {
        dispatchLevelUp({ type: "reset" });
      }
    } catch {
      dispatchLevelUp({ type: "reset" });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wsId, currentConcept?.concept_id]);

  // Persist to localStorage
  useEffect(() => {
    if (!wsId || !currentConcept) return;
    const key = `colearni_levelup_${wsId}_concept_${currentConcept.concept_id}`;
    if (levelUpState.phase === "idle") {
      localStorage.removeItem(key);
    } else {
      localStorage.setItem(key, JSON.stringify(levelUpState));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wsId, currentConcept?.concept_id, levelUpState]);

  async function startLevelUp() {
    if (!wsId || !currentConcept) {
      dispatchLevelUp({ type: "create_error", error: "Pick a concept from the graph first." });
      return;
    }
    if (currentConcept.mastery_score != null && currentConcept.mastery_score >= 0.9) {
      dispatchLevelUp({
        type: "create_error",
        error: `You've already mastered "${currentConcept.canonical_name}" (${Math.round(currentConcept.mastery_score * 100)}%). Try a different concept!`,
      });
      return;
    }
    const sessionId = await ensureSession();
    if (!sessionId) {
      dispatchLevelUp({ type: "create_error", error: "Session is required." });
      return;
    }

    dispatchLevelUp({ type: "create_start" });
    try {
      const quiz = await apiClient.createLevelUpQuiz(wsId, {
        concept_id: currentConcept.concept_id,
        session_id: sessionId,
      });
      dispatchLevelUp({ type: "create_success", quiz });
    } catch (error: unknown) {
      dispatchLevelUp({ type: "create_error", error: errorText(error, "Create failed") });
    }
  }

  async function submitLevelUp() {
    if (!wsId || !levelUpState.quiz) return;

    dispatchLevelUp({ type: "submit_start" });
    try {
      const result = await apiClient.submitLevelUpQuiz(wsId, levelUpState.quiz.quiz_id, {
        answers: toSubmitAnswers(levelUpState.quiz.items, levelUpState.answers),
      });
      dispatchLevelUp({ type: "submit_success", result });
    } catch (error: unknown) {
      dispatchLevelUp({ type: "submit_error", error: errorText(error, "Submit failed") });
    }
  }

  return { levelUpState, dispatchLevelUp, startLevelUp, submitLevelUp };
}
