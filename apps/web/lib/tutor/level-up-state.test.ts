import { describe, expect, it } from "vitest";

import type { LevelUpQuizSubmitResponse, QuizCreateResponse } from "@/lib/api/types";
import {
  canSubmitLevelUp,
  initialLevelUpState,
  levelUpReducer,
  toSubmitAnswers,
} from "@/lib/tutor/level-up-state";

const quiz: QuizCreateResponse = {
  quiz_id: 11,
  workspace_id: 1,
  user_id: 2,
  concept_id: 3,
  status: "ready",
  items: [
    {
      item_id: 101,
      position: 1,
      item_type: "short_answer",
      prompt: "Explain the definition.",
      choices: null,
    },
    {
      item_id: 102,
      position: 2,
      item_type: "mcq",
      prompt: "Pick the best option.",
      choices: [
        { id: "a", text: "Correct" },
        { id: "b", text: "Incorrect" },
      ],
    },
  ],
};

function submitPayload(replayed = false): LevelUpQuizSubmitResponse {
  return {
    quiz_id: 11,
    attempt_id: 1001,
    score: 0.8,
    passed: true,
    critical_misconception: false,
    overall_feedback: "Good work.",
    items: [
      {
        item_id: 101,
        item_type: "short_answer",
        result: "partial",
        is_correct: false,
        critical_misconception: false,
        feedback: "More precision needed.",
        score: 0.6,
      },
      {
        item_id: 102,
        item_type: "mcq",
        result: "correct",
        is_correct: true,
        critical_misconception: false,
        feedback: "Correct.",
        score: 1,
      },
    ],
    replayed,
    retry_hint: replayed ? "create a new level-up quiz to retry" : null,
    mastery_status: "learned",
    mastery_score: 0.8,
  };
}

describe("levelUpReducer", () => {
  it("initializes mixed quiz item state", () => {
    const creating = levelUpReducer(initialLevelUpState, { type: "create_start" });
    const ready = levelUpReducer(creating, { type: "create_success", quiz });

    expect(ready.phase).toBe("ready");
    expect(ready.quiz?.items.map((item) => item.item_type)).toEqual(["short_answer", "mcq"]);
    expect(ready.answers).toEqual({});
  });

  it("blocks submit when answers are missing", () => {
    const ready = levelUpReducer(
      levelUpReducer(initialLevelUpState, { type: "create_start" }),
      { type: "create_success", quiz },
    );

    expect(canSubmitLevelUp(ready)).toBe(false);
    const unchanged = levelUpReducer(ready, { type: "submit_start" });
    expect(unchanged.phase).toBe("ready");
  });

  it("submits successfully and locks state", () => {
    let state = levelUpReducer(
      levelUpReducer(initialLevelUpState, { type: "create_start" }),
      { type: "create_success", quiz },
    );
    state = levelUpReducer(state, { type: "answer", item_id: 101, answer: "definition" });
    state = levelUpReducer(state, { type: "answer", item_id: 102, answer: "a" });

    expect(canSubmitLevelUp(state)).toBe(true);
    state = levelUpReducer(state, { type: "submit_start" });
    expect(state.phase).toBe("submitting");

    state = levelUpReducer(state, { type: "submit_success", result: submitPayload(false) });
    expect(state.phase).toBe("submitted");
    expect(state.result?.mastery_status).toBe("learned");

    const locked = levelUpReducer(state, { type: "answer", item_id: 101, answer: "changed" });
    expect(locked.answers[101]).toBe("definition");
  });

  it("handles submit error and allows retry", () => {
    let state = levelUpReducer(
      levelUpReducer(initialLevelUpState, { type: "create_start" }),
      { type: "create_success", quiz },
    );
    state = levelUpReducer(state, { type: "answer", item_id: 101, answer: "definition" });
    state = levelUpReducer(state, { type: "answer", item_id: 102, answer: "a" });
    state = levelUpReducer(state, { type: "submit_start" });
    state = levelUpReducer(state, { type: "submit_error", error: "Submit failed" });

    expect(state.phase).toBe("submit_error");
    expect(state.error).toBe("Submit failed");

    const retried = levelUpReducer(state, { type: "submit_start" });
    expect(retried.phase).toBe("submitting");
  });

  it("preserves replayed attempt payload for UI hints", () => {
    let state = levelUpReducer(
      levelUpReducer(initialLevelUpState, { type: "create_start" }),
      { type: "create_success", quiz },
    );
    state = levelUpReducer(state, { type: "answer", item_id: 101, answer: "definition" });
    state = levelUpReducer(state, { type: "answer", item_id: 102, answer: "a" });
    state = levelUpReducer(state, { type: "submit_start" });
    state = levelUpReducer(state, { type: "submit_success", result: submitPayload(true) });

    expect(state.phase).toBe("submitted");
    expect(state.result?.replayed).toBe(true);
    expect(state.result?.retry_hint).toBe("create a new level-up quiz to retry");
    expect(toSubmitAnswers(quiz.items, state.answers)).toEqual([
      { item_id: 101, answer: "definition" },
      { item_id: 102, answer: "a" },
    ]);
  });
});
