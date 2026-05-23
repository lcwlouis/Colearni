import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi, beforeEach } from "vitest";

import { QuizPanel } from "@/app/trails/[id]/components/QuizPanel";
import type { GradeResult, LevelUpCard } from "@/lib/types";

const mockLevelUpCard: LevelUpCard = {
  concept_id: "concept-1",
  quiz_type: "level_up",
  questions: [
    {
      id: "q1",
      type: "multiple_choice",
      prompt: "Explain what a vector is in your own words.",
      mastery_label: "explain_vectors",
      difficulty: "light",
      options: ["Magnitude and direction", "Only a number", "Only a unit"],
    },
    {
      id: "q2",
      type: "long_answer",
      prompt: "Apply vectors to compute a dot product.",
      mastery_label: "apply_dot_product",
      difficulty: "challenge",
    },
  ],
};

const mockPracticeCard: LevelUpCard = {
  ...mockLevelUpCard,
  quiz_type: "practice",
};

const mockPassedResult: GradeResult = {
  passed: true,
  score: 0.85,
  feedback: "Great work! Your explanation was clear and the example was correct.",
  mastery_status: "mastered",
  attempt_id: "attempt-1",
};

const mockFailedResult: GradeResult = {
  passed: false,
  score: 0.45,
  feedback: "You need to revisit the application of vectors to real problems.",
  mastery_status: "needs_review",
  attempt_id: "attempt-2",
};

vi.mock("@/lib/api", () => ({
  generateLevelUpQuiz: vi.fn(),
  generatePracticeQuiz: vi.fn(),
  gradeLevelUpQuiz: vi.fn(),
  gradePracticeQuiz: vi.fn(),
}));

import * as api from "@/lib/api";

function renderLevelUpPanel(onMasteryUpdated = vi.fn(), onBack = vi.fn()) {
  return render(
    <QuizPanel
      workspaceId="workspace-1"
      trailId="trail-1"
      conceptId="concept-1"
      mode="level_up"
      onBack={onBack}
      onMasteryUpdated={onMasteryUpdated}
    />,
  );
}

function renderPracticePanel(onMasteryUpdated = vi.fn(), onBack = vi.fn()) {
  return render(
    <QuizPanel
      workspaceId="workspace-1"
      trailId="trail-1"
      conceptId="concept-1"
      mode="practice"
      onBack={onBack}
      onMasteryUpdated={onMasteryUpdated}
    />,
  );
}

describe("QuizPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.generateLevelUpQuiz).mockResolvedValue(mockLevelUpCard);
    vi.mocked(api.generatePracticeQuiz).mockResolvedValue(mockPracticeCard);
    vi.mocked(api.gradeLevelUpQuiz).mockResolvedValue(mockPassedResult);
    vi.mocked(api.gradePracticeQuiz).mockResolvedValue(mockPassedResult);
  });

  test("shows loading state initially", () => {
    renderLevelUpPanel();
    expect(screen.getByText("Generating quiz...")).toBeInTheDocument();
  });

  test("renders questions correctly from a LevelUpCard", async () => {
    renderLevelUpPanel();

    await waitFor(() => {
      expect(screen.getByText(/Explain what a vector is in your own words/)).toBeInTheDocument();
    });

    expect(screen.getByText(/Apply vectors to compute a dot product/)).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Magnitude and direction" })).toBeInTheDocument();
    expect(screen.getAllByPlaceholderText("Type your answer...")).toHaveLength(1);
  });

  test("dedupes duplicate generation requests for the same quiz open", async () => {
    let resolveQuiz: (card: LevelUpCard) => void = () => undefined;
    vi.mocked(api.generateLevelUpQuiz).mockReturnValue(
      new Promise((resolve) => {
        resolveQuiz = resolve;
      }),
    );

    const first = renderLevelUpPanel();
    const second = renderLevelUpPanel();

    expect(api.generateLevelUpQuiz).toHaveBeenCalledTimes(1);
    resolveQuiz(mockLevelUpCard);

    await waitFor(() => {
      expect(screen.getAllByText(/Explain what a vector is in your own words/)).toHaveLength(2);
    });

    first.unmount();
    second.unmount();
  });

  test("renders level-up quiz heading", async () => {
    renderLevelUpPanel();
    await waitFor(() => {
      expect(screen.getByText("Level-Up Quiz")).toBeInTheDocument();
    });
  });

  test("renders practice quiz heading", async () => {
    renderPracticePanel();
    await waitFor(() => {
      expect(screen.getByText("Practice Quiz")).toBeInTheDocument();
    });
  });

  test("disables submit when all answers are empty", async () => {
    renderLevelUpPanel();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Submit" })).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
  });

  test("disables submit when some answers are empty", async () => {
    renderLevelUpPanel();

    await waitFor(() => {
      expect(screen.getAllByPlaceholderText("Type your answer...")[0]).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("radio", { name: "Magnitude and direction" }));

    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
  });

  test("enables submit only when all answers are non-empty", async () => {
    renderLevelUpPanel();

    await waitFor(() => {
      expect(screen.getAllByPlaceholderText("Type your answer...")[0]).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("radio", { name: "Magnitude and direction" }));
    const textareas = screen.getAllByPlaceholderText("Type your answer...");
    await userEvent.type(textareas[0], "The dot product is computed by summing element-wise products.");

    expect(screen.getByRole("button", { name: "Submit" })).toBeEnabled();
  });

  test("calls gradeLevelUpQuiz with correct payload on submit", async () => {
    renderLevelUpPanel();

    await waitFor(() => {
      expect(screen.getAllByPlaceholderText("Type your answer...")[0]).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("radio", { name: "Magnitude and direction" }));
    const textareas = screen.getAllByPlaceholderText("Type your answer...");
    await userEvent.type(textareas[0], "Dot product sums element-wise products.");

    await userEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => {
      expect(api.gradeLevelUpQuiz).toHaveBeenCalledWith(
        "workspace-1",
        "trail-1",
        "concept-1",
        mockLevelUpCard.questions,
        [
          { question_id: "q1", answer: "Magnitude and direction" },
          { question_id: "q2", answer: "Dot product sums element-wise products." },
        ],
      );
    });
  });

  test("calls gradePracticeQuiz when mode is practice", async () => {
    renderPracticePanel();

    await waitFor(() => {
      expect(screen.getAllByPlaceholderText("Type your answer...")[0]).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("radio", { name: "Magnitude and direction" }));
    const textareas = screen.getAllByPlaceholderText("Type your answer...");
    await userEvent.type(textareas[0], "Dot product sums element-wise products.");

    await userEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => {
      expect(api.gradePracticeQuiz).toHaveBeenCalledWith(
        "workspace-1",
        "trail-1",
        "concept-1",
        mockPracticeCard.questions,
        expect.any(Array),
      );
    });
  });

  test("passed grade result displays Passed and score", async () => {
    vi.mocked(api.gradeLevelUpQuiz).mockResolvedValue(mockPassedResult);
    renderLevelUpPanel();

    await waitFor(() => {
      expect(screen.getAllByPlaceholderText("Type your answer...")[0]).toBeInTheDocument();
    });

    await answerAllQuestions();
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => {
      expect(screen.getByText("Passed")).toBeInTheDocument();
    });

    expect(screen.getByText("Score: 85%")).toBeInTheDocument();
    expect(screen.getByText(mockPassedResult.feedback)).toBeInTheDocument();
  });

  test("failed grade result displays Failed and feedback", async () => {
    vi.mocked(api.gradeLevelUpQuiz).mockResolvedValue(mockFailedResult);
    renderLevelUpPanel();

    await waitFor(() => {
      expect(screen.getAllByPlaceholderText("Type your answer...")[0]).toBeInTheDocument();
    });

    await answerAllQuestions();
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => {
      expect(screen.getByText("Failed")).toBeInTheDocument();
    });

    expect(screen.getByText("Score: 45%")).toBeInTheDocument();
    expect(screen.getByText(mockFailedResult.feedback)).toBeInTheDocument();
  });

  test("retry button generates a new quiz and shows fresh questions", async () => {
    const newCard: LevelUpCard = {
      concept_id: "concept-1",
      quiz_type: "level_up",
      questions: [
        {
          id: "q3",
          type: "short_answer",
          prompt: "Compare vectors and scalars.",
          mastery_label: "compare_vectors_scalars",
        },
      ],
    };

    vi.mocked(api.gradeLevelUpQuiz).mockResolvedValue(mockPassedResult);
    renderLevelUpPanel();

    await waitFor(() => {
      expect(screen.getAllByPlaceholderText("Type your answer...")[0]).toBeInTheDocument();
    });

    await answerAllQuestions();
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => {
      expect(screen.getByText("Passed")).toBeInTheDocument();
    });

    // Set up the new quiz for retry
    vi.mocked(api.generateLevelUpQuiz).mockResolvedValue(newCard);
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => {
      expect(screen.getByText(/Compare vectors and scalars/)).toBeInTheDocument();
    });

    expect(api.generateLevelUpQuiz).toHaveBeenCalledTimes(2);
  });

  test("practice retry reuses existing card without re-fetching", async () => {
    vi.mocked(api.gradePracticeQuiz).mockResolvedValue(mockPassedResult);
    renderPracticePanel();

    await waitFor(() => {
      expect(screen.getAllByPlaceholderText("Type your answer...")[0]).toBeInTheDocument();
    });

    await answerAllQuestions();
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "Retry" }));

    // Should be back in answering state with the same questions — no second generate call.
    await waitFor(() => {
      expect(screen.getAllByPlaceholderText("Type your answer...")).toHaveLength(1);
    });

    expect(api.generatePracticeQuiz).toHaveBeenCalledTimes(1);
  });

  test("practice grade does NOT call onMasteryUpdated", async () => {
    const onMasteryUpdated = vi.fn();
    vi.mocked(api.gradePracticeQuiz).mockResolvedValue(mockPassedResult);
    renderPracticePanel(onMasteryUpdated);

    await waitFor(() => {
      expect(screen.getAllByPlaceholderText("Type your answer...")[0]).toBeInTheDocument();
    });

    await answerAllQuestions();
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => {
      expect(screen.getByText("Passed")).toBeInTheDocument();
    });

    expect(onMasteryUpdated).not.toHaveBeenCalled();
  });

  test("level-up grade calls onMasteryUpdated with correct concept_id and mastery_status", async () => {
    const onMasteryUpdated = vi.fn();
    vi.mocked(api.gradeLevelUpQuiz).mockResolvedValue(mockPassedResult);
    renderLevelUpPanel(onMasteryUpdated);

    await waitFor(() => {
      expect(screen.getAllByPlaceholderText("Type your answer...")[0]).toBeInTheDocument();
    });

    await answerAllQuestions();
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => {
      expect(screen.getByText("Passed")).toBeInTheDocument();
    });

    expect(onMasteryUpdated).toHaveBeenCalledTimes(1);
    expect(onMasteryUpdated).toHaveBeenCalledWith("concept-1", { status: "mastered", score: 0.85 });
  });

  test("level-up failed grade calls onMasteryUpdated with needs_review", async () => {
    const onMasteryUpdated = vi.fn();
    vi.mocked(api.gradeLevelUpQuiz).mockResolvedValue(mockFailedResult);
    renderLevelUpPanel(onMasteryUpdated);

    await waitFor(() => {
      expect(screen.getAllByPlaceholderText("Type your answer...")[0]).toBeInTheDocument();
    });

    await answerAllQuestions();
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => {
      expect(screen.getByText("Failed")).toBeInTheDocument();
    });

    expect(onMasteryUpdated).toHaveBeenCalledWith("concept-1", { status: "needs_review", score: 0.45 });
  });

  test("back button on question screen calls onBack", async () => {
    const onBack = vi.fn();
    renderLevelUpPanel(vi.fn(), onBack);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Back" })).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  test("back button on result screen calls onBack", async () => {
    const onBack = vi.fn();
    vi.mocked(api.gradeLevelUpQuiz).mockResolvedValue(mockPassedResult);
    renderLevelUpPanel(vi.fn(), onBack);

    await waitFor(() => {
      expect(screen.getAllByPlaceholderText("Type your answer...")[0]).toBeInTheDocument();
    });

    await answerAllQuestions();
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => {
      expect(screen.getByText("Passed")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  test("shows generation error and retry on API failure", async () => {
    vi.mocked(api.generateLevelUpQuiz).mockRejectedValue(new Error("Network error"));
    renderLevelUpPanel();

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Back" })).toBeInTheDocument();
  });

  test("shows grading error and allows retry on grade API failure", async () => {
    vi.mocked(api.gradeLevelUpQuiz).mockRejectedValue(new Error("Grading failed"));
    renderLevelUpPanel();

    await waitFor(() => {
      expect(screen.getAllByPlaceholderText("Type your answer...")[0]).toBeInTheDocument();
    });

    await answerAllQuestions();
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() => {
      expect(screen.getByText("Grading failed")).toBeInTheDocument();
    });

    // Should be back in answering state with questions still visible
    expect(screen.getAllByPlaceholderText("Type your answer...")).toHaveLength(1);
  });
});

async function answerAllQuestions() {
  await userEvent.click(screen.getByRole("radio", { name: "Magnitude and direction" }));
  await userEvent.type(screen.getAllByPlaceholderText("Type your answer...")[0], "Answer two.");
}
