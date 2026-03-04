import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { ConceptActivityPanel } from "./concept-activity-panel";
import type { ConceptActivityResponse } from "@/lib/api/types";

function makeActivity(
  overrides: Partial<ConceptActivityResponse> = {},
): ConceptActivityResponse {
  return {
    workspace_id: 1,
    user_id: 1,
    concept_id: 42,
    practice_quizzes: { count: 0, average_score: null, quizzes: [] },
    level_up_quizzes: { count: 0, passed_count: 0, quizzes: [] },
    flashcard_runs: { count: 0, total_cards_generated: 0, runs: [] },
    affordances: {
      can_generate_flashcards: true,
      can_create_practice_quiz: true,
      can_create_level_up_quiz: false,
      has_prior_flashcards: false,
      has_prior_practice: false,
      has_prior_level_up: false,
    },
    ...overrides,
  };
}

describe("ConceptActivityPanel", () => {
  it("shows loading state when no activity yet", () => {
    const html = renderToString(
      <ConceptActivityPanel
        activity={null}
        loading={true}
        error={null}
        onRefresh={() => {}}
      />,
    );
    expect(html).toContain("Loading activity");
  });

  it("shows error when no activity and error present", () => {
    const html = renderToString(
      <ConceptActivityPanel
        activity={null}
        loading={false}
        error="Server error"
        onRefresh={() => {}}
      />,
    );
    expect(html).toContain("Server error");
  });

  it("shows empty message when activity has no items", () => {
    const html = renderToString(
      <ConceptActivityPanel
        activity={makeActivity()}
        loading={false}
        error={null}
        onRefresh={() => {}}
      />,
    );
    expect(html).toContain("No activity yet");
  });

  it("renders practice quizzes with open and retry buttons", () => {
    const activity = makeActivity({
      practice_quizzes: {
        count: 1,
        average_score: 0.85,
        quizzes: [
          {
            quiz_id: 10,
            title: "Quiz #1",
            latest_score: 0.6,
            passed: false,
            graded_at: "2025-01-15T00:00:00Z",
            can_retry: true,
          },
        ],
      },
    });
    const html = renderToString(
      <ConceptActivityPanel
        activity={activity}
        loading={false}
        error={null}
        onRefresh={() => {}}
        onOpenQuiz={() => {}}
        onRetryQuiz={() => {}}
      />,
    );
    expect(html).toContain("Practice quizzes (");
    expect(html).toContain("avg ");
    expect(html).toContain("85");
    expect(html).toContain("Quiz #1");
    expect(html).toContain("60%");
    expect(html).toContain("Open");
    expect(html).toContain("Retry");
  });

  it("does not render retry button when can_retry is false", () => {
    const activity = makeActivity({
      practice_quizzes: {
        count: 1,
        average_score: 1.0,
        quizzes: [
          {
            quiz_id: 10,
            title: "Quiz #1",
            latest_score: 1.0,
            passed: true,
            graded_at: "2025-01-15T00:00:00Z",
            can_retry: false,
          },
        ],
      },
    });
    const html = renderToString(
      <ConceptActivityPanel
        activity={activity}
        loading={false}
        error={null}
        onRefresh={() => {}}
        onOpenQuiz={() => {}}
        onRetryQuiz={() => {}}
      />,
    );
    expect(html).toContain("Open");
    expect(html).not.toContain("Retry");
  });

  it("renders level-up quizzes section", () => {
    const activity = makeActivity({
      level_up_quizzes: {
        count: 2,
        passed_count: 1,
        quizzes: [
          {
            quiz_id: 20,
            title: "Level-up #1",
            latest_score: 1.0,
            passed: true,
            graded_at: "2025-01-10T00:00:00Z",
            can_retry: false,
            can_promote: true,
          },
          {
            quiz_id: 21,
            title: "Level-up #2",
            latest_score: 0.5,
            passed: false,
            graded_at: "2025-01-12T00:00:00Z",
            can_retry: true,
          },
        ],
      },
    });
    const html = renderToString(
      <ConceptActivityPanel
        activity={activity}
        loading={false}
        error={null}
        onRefresh={() => {}}
        onOpenQuiz={() => {}}
        onRetryQuiz={() => {}}
      />,
    );
    expect(html).toContain("Level-up quizzes (");
    expect(html).toContain("passed");
  });

  it("renders flashcard runs with open button", () => {
    const activity = makeActivity({
      flashcard_runs: {
        count: 1,
        total_cards_generated: 5,
        runs: [
          {
            run_id: "run-abc",
            item_count: 5,
            has_more: true,
            exhausted: false,
            created_at: "2025-01-14T00:00:00Z",
            can_open: true,
          },
        ],
      },
    });
    const html = renderToString(
      <ConceptActivityPanel
        activity={activity}
        loading={false}
        error={null}
        onRefresh={() => {}}
        onOpenFlashcardRun={() => {}}
      />,
    );
    expect(html).toContain("Flashcard runs (");
    expect(html).toContain("cards total");
    expect(html).toContain("cards");
    expect(html).toContain("more available");
    expect(html).toContain("Open");
  });

  it("returns null when no activity and not loading", () => {
    const html = renderToString(
      <ConceptActivityPanel
        activity={null}
        loading={false}
        error={null}
        onRefresh={() => {}}
      />,
    );
    expect(html).toBe("");
  });
});
