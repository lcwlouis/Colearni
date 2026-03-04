import type {
  LevelUpQuizSubmitResponse,
  QuizCreateResponse,
  QuizItemSummary,
  QuizSubmitAnswer,
} from "@/lib/api/types";

export type LevelUpPhase =
  | "idle"
  | "creating"
  | "ready"
  | "submitting"
  | "submitted"
  | "create_error"
  | "submit_error";

export interface LevelUpState {
  phase: LevelUpPhase;
  quiz: QuizCreateResponse | null;
  answers: Record<number, string>;
  result: LevelUpQuizSubmitResponse | null;
  error: string | null;
}

export type LevelUpAction =
  | { type: "create_start" }
  | { type: "create_success"; quiz: QuizCreateResponse }
  | { type: "create_error"; error: string }
  | { type: "answer"; item_id: number; answer: string }
  | { type: "submit_start" }
  | { type: "submit_success"; result: LevelUpQuizSubmitResponse }
  | { type: "submit_error"; error: string }
  | { type: "reset" }
  | { type: "restore"; state: LevelUpState };

export const initialLevelUpState: LevelUpState = {
  phase: "idle",
  quiz: null,
  answers: {},
  result: null,
  error: null,
};

export function levelUpReducer(state: LevelUpState, action: LevelUpAction): LevelUpState {
  if (action.type === "create_start") {
    return {
      ...state,
      phase: "creating",
      quiz: null,
      answers: {},
      result: null,
      error: null,
    };
  }

  if (action.type === "create_success") {
    return {
      ...state,
      phase: "ready",
      quiz: action.quiz,
      answers: {},
      result: null,
      error: null,
    };
  }

  if (action.type === "create_error") {
    return {
      ...state,
      phase: "create_error",
      quiz: null,
      answers: {},
      result: null,
      error: action.error,
    };
  }

  if (action.type === "answer") {
    if (state.phase !== "ready" && state.phase !== "submit_error") {
      return state;
    }
    return {
      ...state,
      answers: { ...state.answers, [action.item_id]: action.answer },
    };
  }

  if (action.type === "submit_start") {
    if (!canSubmitLevelUp(state)) {
      return state;
    }
    return {
      ...state,
      phase: "submitting",
      error: null,
    };
  }

  if (action.type === "submit_success") {
    return {
      ...state,
      phase: "submitted",
      result: action.result,
      error: null,
    };
  }

  if (action.type === "submit_error") {
    if (state.phase !== "submitting") {
      return state;
    }
    return {
      ...state,
      phase: "submit_error",
      error: action.error,
    };
  }

  if (action.type === "reset") {
    return initialLevelUpState;
  }

  if (action.type === "restore") {
    return action.state;
  }

  return state;
}

export function canSubmitLevelUp(state: LevelUpState): boolean {
  if (!state.quiz) {
    return false;
  }
  if (state.phase !== "ready" && state.phase !== "submit_error") {
    return false;
  }
  return state.quiz.items.every((item) => {
    const value = state.answers[item.item_id];
    return typeof value === "string" && value.trim().length > 0;
  });
}

export function toSubmitAnswers(
  items: QuizItemSummary[],
  answers: Record<number, string>,
): QuizSubmitAnswer[] {
  return items.map((item) => ({
    item_id: item.item_id,
    answer: (answers[item.item_id] ?? "").trim(),
  }));
}
