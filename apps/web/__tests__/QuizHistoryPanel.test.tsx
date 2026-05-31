import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { QuizHistoryPanel } from "@/app/(app)/trails/[id]/components/QuizHistoryPanel";
import type { QuizAttempt } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  listQuizAttempts: vi.fn(),
  generateLevelUpQuiz: vi.fn(),
  generatePracticeQuiz: vi.fn(),
}));

import * as api from "@/lib/api";

const levelUpAttempt: QuizAttempt = {
  id: "attempt-1",
  concept_id: "concept-1",
  quiz_type: "level_up",
  questions: [
    {
      id: "q1",
      type: "short_answer",
      prompt: "What does the Transport layer do?",
      mastery_label: "functions",
      difficulty: "standard",
    },
  ],
  answers: [{ question_id: "q1", answer: "End-to-end delivery." }],
  evaluator_feedback: "Good. You captured the core idea.",
  passed: true,
  score: 0.9,
  created_at: "2026-05-30T10:00:00Z",
};

const practiceAttempt: QuizAttempt = {
  ...levelUpAttempt,
  id: "attempt-2",
  quiz_type: "practice",
  questions: [
    {
      id: "q1",
      type: "short_answer",
      prompt: "Name a practice-only concept.",
      mastery_label: "functions",
      difficulty: "standard",
    },
  ],
  answers: [{ question_id: "q1", answer: "Practice answer text." }],
  evaluator_feedback: "Practice feedback for a different attempt.",
  passed: false,
  score: 0.4,
};

function renderPanel(onBack = vi.fn()) {
  return render(
    <QuizHistoryPanel
      workspaceId="workspace-1"
      trailId="trail-1"
      conceptId="concept-1"
      onBack={onBack}
    />,
  );
}

describe("QuizHistoryPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listQuizAttempts).mockResolvedValue({
      attempts: [levelUpAttempt, practiceAttempt],
    });
  });

  test("loads attempts without generating a quiz", async () => {
    renderPanel();

    await waitFor(() => {
      expect(screen.getAllByText(/Level-up ·/)[0]).toBeInTheDocument();
    });

    expect(api.listQuizAttempts).toHaveBeenCalledWith(
      "workspace-1",
      "trail-1",
      "concept-1",
      { limit: 25 },
    );
    expect(api.generateLevelUpQuiz).not.toHaveBeenCalled();
    expect(api.generatePracticeQuiz).not.toHaveBeenCalled();
  });

  test("expands an attempt to reveal questions, answers, and feedback", async () => {
    renderPanel();

    await waitFor(() => {
      expect(screen.getByText(/Level-up ·/)).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText(/Level-up ·/));

    expect(
      screen.getByText("Good. You captured the core idea."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/What does the Transport layer do/),
    ).toBeInTheDocument();
    expect(screen.getByText("End-to-end delivery.")).toBeInTheDocument();
  });

  test("filters attempts by quiz type", async () => {
    renderPanel();

    await waitFor(() => {
      expect(screen.getByText(/Level-up ·/)).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "Practice" }));

    expect(screen.queryByText(/Level-up ·/)).not.toBeInTheDocument();
    expect(screen.getByText(/Practice ·/)).toBeInTheDocument();
  });

  test("shows an empty state when there are no attempts", async () => {
    vi.mocked(api.listQuizAttempts).mockResolvedValue({ attempts: [] });
    renderPanel();

    await waitFor(() => {
      expect(screen.getByText(/No attempts yet/)).toBeInTheDocument();
    });
  });

  test("back button calls onBack", async () => {
    const onBack = vi.fn();
    renderPanel(onBack);

    await userEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });
});
