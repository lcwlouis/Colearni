import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import BookmarksPage from "@/app/(app)/bookmarks/page";
import type { ArtifactRead, WorkedExampleEnvelope } from "@/lib/artifacts";
import type { FlashcardDeck, QuizAttempt, Trail } from "@/lib/types";

vi.mock("@/lib/workspace", () => ({
  ensureWorkspaceId: vi.fn().mockResolvedValue("workspace-1"),
}));

vi.mock("@/lib/api", () => ({
  listTrails: vi.fn(),
  listPins: vi.fn(),
  pinItem: vi.fn().mockResolvedValue(undefined),
  unpinItem: vi.fn().mockResolvedValue(undefined),
}));

import * as api from "@/lib/api";

const trail: Trail = {
  id: "trail-1",
  workspace_id: "workspace-1",
  title: "Networking Basics",
  topic: "Networking",
  goal: "Understand the OSI model",
  target_depth: "understand",
  prior_knowledge: null,
  created_at: "2026-05-30T10:00:00Z",
  node_count: 5,
  edge_count: 4,
};

function workedExampleEnvelope(): WorkedExampleEnvelope {
  return {
    artifact_version: 1,
    kind: "worked_example",
    title: "Solving 2x + 3 = 11",
    caption: null,
    text_fallback: "Step 1: subtract 3. Step 2: divide by 2. Answer: x = 4.",
    provenance: { source_ids: [], visibility: "local_only", citations: [] },
    data: {
      steps: [
        { label: "Isolate the term", detail: "Subtract 3 from both sides." },
      ],
      final_answer: "x = 4",
    },
  };
}

function artifactRow(): ArtifactRead {
  const payload = workedExampleEnvelope();
  return {
    id: "artifact-1",
    workspace_id: "workspace-1",
    trail_id: "trail-1",
    concept_id: "concept-1",
    artifact_type: payload.kind,
    title: payload.title,
    visibility: payload.provenance.visibility,
    payload,
    created_at: "2026-05-30T10:00:00Z",
  };
}

const attempt: QuizAttempt = {
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
  answers: [{ question_id: "q1", answer: "It handles end-to-end delivery." }],
  evaluator_feedback: "Good work.",
  passed: true,
  score: 0.9,
  created_at: "2026-05-30T11:00:00Z",
};

const flashcardDeck: FlashcardDeck = {
  id: "deck-1",
  workspace_id: "workspace-1",
  trail_id: "trail-1",
  concept_id: "concept-1",
  title: "OSI Model Flashcards",
  created_at: "2026-05-30T10:00:00Z",
  updated_at: "2026-05-30T10:00:00Z",
  cards: [
    {
      id: "card-1",
      deck_id: "deck-1",
      front: "What is Layer 1?",
      back: "Physical layer",
      hint: null,
      source_ref: null,
      card_type: "basic",
      box: 1,
      interval_days: 1,
      last_reviewed: null,
      due: null,
      reps: 0,
      lapses: 0,
      created_at: "2026-05-30T10:00:00Z",
    },
  ],
};

describe("BookmarksPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("aggregates pinned artifacts and attempts per trail from listPins", async () => {
    vi.mocked(api.listTrails).mockResolvedValue({ trails: [trail] });
    vi.mocked(api.listPins).mockResolvedValue({
      artifacts: [artifactRow()],
      quiz_attempts: [attempt],
      flashcards: [],
      concepts: [],
    });

    render(<BookmarksPage />);

    await waitFor(() => {
      expect(screen.getByText("Networking Basics")).toBeInTheDocument();
    });

    expect(api.listPins).toHaveBeenCalledWith("workspace-1", "trail-1");
    // Artifact rendered through the registry.
    expect(screen.getByTestId("artifact-worked-example")).toBeInTheDocument();
    expect(screen.getByText("Isolate the term")).toBeInTheDocument();
    // Pinned quiz attempt surfaced.
    expect(screen.getByText(/Level-up ·/)).toBeInTheDocument();
  });

  test("shows an empty state when nothing is pinned", async () => {
    vi.mocked(api.listTrails).mockResolvedValue({ trails: [trail] });
    vi.mocked(api.listPins).mockResolvedValue({
      artifacts: [],
      quiz_attempts: [],
      flashcards: [],
      concepts: [],
    });

    render(<BookmarksPage />);

    await waitFor(() => {
      expect(screen.getByText(/Nothing saved yet/)).toBeInTheDocument();
    });
  });

  test("renders pinned flashcard decks with card count", async () => {
    vi.mocked(api.listTrails).mockResolvedValue({ trails: [trail] });
    vi.mocked(api.listPins).mockResolvedValue({
      artifacts: [],
      quiz_attempts: [],
      flashcards: [flashcardDeck],
      concepts: [],
    });

    render(<BookmarksPage />);

    await waitFor(() => {
      expect(screen.getByText("OSI Model Flashcards")).toBeInTheDocument();
    });

    expect(screen.getByText("1 card")).toBeInTheDocument();
    expect(screen.getByText("Networking Basics")).toBeInTheDocument();
  });
});
