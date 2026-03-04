import type {
    PracticeFlashcardsResponse,
    PracticeQuizSubmitResponse,
    QuizCreateResponse,
    QuizItemSummary,
    QuizSubmitAnswer,
} from "@/lib/api/types";

export type PracticePhase =
    | "idle"
    | "loading_flashcards"
    | "flashcards_ready"
    | "loading_quiz"
    | "quiz_ready"
    | "submitting_quiz"
    | "quiz_submitted"
    | "error";

export interface PracticeState {
    phase: PracticePhase;
    flashcards: PracticeFlashcardsResponse | null;
    quiz: QuizCreateResponse | null;
    answers: Record<number, string>;
    result: PracticeQuizSubmitResponse | null;
    error: string | null;
}

export type PracticeAction =
    | { type: "flashcards_start" }
    | { type: "flashcards_success"; data: PracticeFlashcardsResponse }
    | { type: "flashcards_error"; error: string }
    | { type: "quiz_start" }
    | { type: "quiz_success"; quiz: QuizCreateResponse }
    | { type: "quiz_error"; error: string }
    | { type: "answer"; item_id: number; answer: string }
    | { type: "submit_start" }
    | { type: "submit_success"; result: PracticeQuizSubmitResponse }
    | { type: "submit_error"; error: string }
    | { type: "reset" };

export const initialPracticeState: PracticeState = {
    phase: "idle",
    flashcards: null,
    quiz: null,
    answers: {},
    result: null,
    error: null,
};

export function practiceReducer(state: PracticeState, action: PracticeAction): PracticeState {
    if (action.type === "flashcards_start") {
        return { ...initialPracticeState, phase: "loading_flashcards" };
    }
    if (action.type === "flashcards_success") {
        return { ...state, phase: "flashcards_ready", flashcards: action.data, error: null };
    }
    if (action.type === "flashcards_error") {
        return { ...state, phase: "error", error: action.error };
    }
    if (action.type === "quiz_start") {
        return { ...initialPracticeState, phase: "loading_quiz" };
    }
    if (action.type === "quiz_success") {
        return { ...state, phase: "quiz_ready", quiz: action.quiz, answers: {}, error: null };
    }
    if (action.type === "quiz_error") {
        return { ...state, phase: "error", error: action.error };
    }
    if (action.type === "answer") {
        if (state.phase !== "quiz_ready" && state.phase !== "error") return state;
        return { ...state, answers: { ...state.answers, [action.item_id]: action.answer } };
    }
    if (action.type === "submit_start") {
        if (!canSubmitPractice(state)) return state;
        return { ...state, phase: "submitting_quiz", error: null };
    }
    if (action.type === "submit_success") {
        return { ...state, phase: "quiz_submitted", result: action.result, error: null };
    }
    if (action.type === "submit_error") {
        if (state.phase !== "submitting_quiz") return state;
        return { ...state, phase: "error", error: action.error };
    }
    if (action.type === "reset") {
        return initialPracticeState;
    }
    return state;
}

export function canSubmitPractice(state: PracticeState): boolean {
    if (!state.quiz) return false;
    if (state.phase !== "quiz_ready" && state.phase !== "error") return false;
    return state.quiz.items.every((item) => {
        const v = state.answers[item.item_id];
        return typeof v === "string" && v.trim().length > 0;
    });
}

export function toPracticeAnswers(
    items: QuizItemSummary[],
    answers: Record<number, string>,
): QuizSubmitAnswer[] {
    return items.map((item) => ({
        item_id: item.item_id,
        answer: (answers[item.item_id] ?? "").trim(),
    }));
}
