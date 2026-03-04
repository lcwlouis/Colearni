import { describe, expect, it } from "vitest";
import { practiceReducer, initialPracticeState, canSubmitPractice, toPracticeAnswers } from "./practice-state";
import type { PracticeFlashcardsResponse, QuizCreateResponse, PracticeQuizSubmitResponse, QuizItemSummary } from "@/lib/api/types";

const flashcards: PracticeFlashcardsResponse = { workspace_id: 1, concept_id: 1, concept_name: "Linear Map", flashcards: [{ front: "Q?", back: "A.", hint: "H" }] };
const quiz: QuizCreateResponse = { quiz_id: 201, workspace_id: 1, user_id: 1, concept_id: 1, status: "ready", items: [{ item_id: 2001, position: 1, item_type: "short_answer", prompt: "Explain.", choices: null }, { item_id: 2002, position: 2, item_type: "mcq", prompt: "Pick one.", choices: [{ id: "a", text: "A" }, { id: "b", text: "B" }] }] };
const result: PracticeQuizSubmitResponse = { quiz_id: 201, attempt_id: 6001, score: 0.75, passed: true, critical_misconception: false, overall_feedback: "Good.", items: [{ item_id: 2001, item_type: "short_answer", result: "partial", is_correct: false, critical_misconception: false, feedback: "OK.", score: 0.5 }], replayed: false, retry_hint: null };

describe("practiceReducer", () => {
    it("starts in idle", () => {
        expect(initialPracticeState.phase).toBe("idle");
    });

    it("flashcards_start resets to loading", () => {
        const s = practiceReducer(initialPracticeState, { type: "flashcards_start" });
        expect(s.phase).toBe("loading_flashcards");
    });

    it("flashcards_success populates data", () => {
        const s = practiceReducer(initialPracticeState, { type: "flashcards_success", data: flashcards });
        expect(s.phase).toBe("flashcards_ready");
        expect(s.flashcards?.flashcards).toHaveLength(1);
    });

    it("quiz_start resets to loading", () => {
        const s = practiceReducer(initialPracticeState, { type: "quiz_start" });
        expect(s.phase).toBe("loading_quiz");
    });

    it("quiz_success populates quiz", () => {
        const s = practiceReducer(initialPracticeState, { type: "quiz_success", quiz });
        expect(s.phase).toBe("quiz_ready");
        expect(s.quiz?.items).toHaveLength(2);
    });

    it("answer updates answers map in quiz_ready", () => {
        let s = practiceReducer(initialPracticeState, { type: "quiz_success", quiz });
        s = practiceReducer(s, { type: "answer", item_id: 2001, answer: "my answer" });
        expect(s.answers[2001]).toBe("my answer");
    });

    it("answer is ignored in idle phase", () => {
        const s = practiceReducer(initialPracticeState, { type: "answer", item_id: 1, answer: "x" });
        expect(s.answers).toEqual({});
    });

    it("submit_success sets result without mastery fields", () => {
        let s = practiceReducer(initialPracticeState, { type: "quiz_success", quiz });
        s = practiceReducer(s, { type: "answer", item_id: 2001, answer: "a" });
        s = practiceReducer(s, { type: "answer", item_id: 2002, answer: "a" });
        s = practiceReducer(s, { type: "submit_start" });
        s = practiceReducer(s, { type: "submit_success", result });
        expect(s.phase).toBe("quiz_submitted");
        expect(s.result?.score).toBe(0.75);
        // Confirm no mastery fields
        expect("mastery_status" in (s.result ?? {})).toBe(false);
        expect("mastery_score" in (s.result ?? {})).toBe(false);
    });

    it("error actions set error", () => {
        const s = practiceReducer(initialPracticeState, { type: "flashcards_error", error: "fail" });
        expect(s.phase).toBe("error");
        expect(s.error).toBe("fail");
    });

    it("reset returns initial state", () => {
        const prev = practiceReducer(initialPracticeState, { type: "flashcards_success", data: flashcards });
        expect(practiceReducer(prev, { type: "reset" })).toEqual(initialPracticeState);
    });
});

describe("canSubmitPractice", () => {
    it("returns false when no quiz", () => {
        expect(canSubmitPractice(initialPracticeState)).toBe(false);
    });

    it("returns false when not all items answered", () => {
        let s = practiceReducer(initialPracticeState, { type: "quiz_success", quiz });
        s = practiceReducer(s, { type: "answer", item_id: 2001, answer: "x" });
        expect(canSubmitPractice(s)).toBe(false);
    });

    it("returns true when all items answered", () => {
        let s = practiceReducer(initialPracticeState, { type: "quiz_success", quiz });
        s = practiceReducer(s, { type: "answer", item_id: 2001, answer: "x" });
        s = practiceReducer(s, { type: "answer", item_id: 2002, answer: "a" });
        expect(canSubmitPractice(s)).toBe(true);
    });
});

describe("toPracticeAnswers", () => {
    it("maps items to submit format", () => {
        const items: QuizItemSummary[] = quiz.items;
        const answers = { 2001: " my answer ", 2002: "a" };
        const result = toPracticeAnswers(items, answers);
        expect(result).toEqual([
            { item_id: 2001, answer: "my answer" },
            { item_id: 2002, answer: "a" },
        ]);
    });
});
