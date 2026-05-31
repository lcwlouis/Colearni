import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";

import { FlashcardsPanel } from "@/app/(app)/trails/[id]/components/FlashcardsPanel";
import type {
  Flashcard,
  FlashcardDeck,
  FlashcardGenerateResponse,
} from "@/lib/types";

vi.mock("@/lib/api", () => ({
  getFlashcards: vi.fn(),
  streamGenerateFlashcards: vi.fn(),
  reviewFlashcard: vi.fn(),
  flashcardsExportUrl: vi.fn(
    (workspaceId: string, trailId: string, conceptId: string, format: string) =>
      `http://api/${workspaceId}/${trailId}/${conceptId}/export?format=${format}`,
  ),
  // PinToggle (rendered when cards exist) imports these; provide no-op stubs.
  pinItem: vi.fn(),
  unpinItem: vi.fn(),
}));

import * as api from "@/lib/api";

function card(id: string, overrides: Partial<Flashcard> = {}): Flashcard {
  return {
    id,
    deck_id: "deck-1",
    front: `Front of ${id}`,
    back: `Back of ${id}`,
    hint: null,
    source_ref: "rev-1",
    card_type: "basic",
    box: 1,
    interval_days: 0,
    last_reviewed: null,
    due: null,
    reps: 0,
    lapses: 0,
    created_at: "2026-05-30T10:00:00Z",
    ...overrides,
  };
}

function deck(cards: Flashcard[]): FlashcardDeck {
  return {
    id: "deck-1",
    workspace_id: "workspace-1",
    trail_id: "trail-1",
    concept_id: "concept-1",
    title: "Vectors deck",
    created_at: "2026-05-30T10:00:00Z",
    updated_at: "2026-05-30T10:00:00Z",
    cards,
  };
}

function generateResponse(
  cards: Flashcard[],
  overrides: Partial<FlashcardGenerateResponse> = {},
): FlashcardGenerateResponse {
  return {
    deck: deck(cards),
    exhausted: false,
    reason: "",
    ...overrides,
  };
}

function mockStreamGenerateFlashcards(response: FlashcardGenerateResponse) {
  vi.mocked(api.streamGenerateFlashcards).mockImplementation(
    async (_workspaceId, _trailId, _conceptId, _options, callbacks) => {
      callbacks.onDone(response);
    },
  );
}

function mockStreamGenerateFlashcardsError(error: Error) {
  vi.mocked(api.streamGenerateFlashcards).mockImplementation(
    async (_workspaceId, _trailId, _conceptId, _options, callbacks) => {
      callbacks.onError?.(error.message);
    },
  );
}

function renderPanel(onBack = vi.fn()) {
  return render(
    <FlashcardsPanel
      workspaceId="workspace-1"
      trailId="trail-1"
      conceptId="concept-1"
      onBack={onBack}
    />,
  );
}

describe("FlashcardsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.flashcardsExportUrl).mockImplementation(
      (workspaceId, trailId, conceptId, format) =>
        `http://api/${workspaceId}/${trailId}/${conceptId}/export?format=${format}`,
    );
    // Default: an empty deck (no cards yet).
    vi.mocked(api.getFlashcards).mockResolvedValue(deck([]));
  });

  test("empty state shows the Generate CTA; clicking it generates and renders cards", async () => {
    mockStreamGenerateFlashcards(generateResponse([card("c1"), card("c2")]));

    renderPanel();

    await waitFor(() => {
      expect(screen.getByText(/No flashcards yet/)).toBeInTheDocument();
    });

    await userEvent.click(
      screen.getByRole("button", { name: "Generate flashcards" }),
    );

    expect(api.streamGenerateFlashcards).toHaveBeenCalledWith(
      "workspace-1",
      "trail-1",
      "concept-1",
      {},
      expect.objectContaining({
        onDone: expect.any(Function),
        onError: expect.any(Function),
      }),
    );

    await waitFor(() => {
      expect(screen.getByText("Front of c1")).toBeInTheDocument();
    });
    // Recall-first: the answer is hidden until requested.
    expect(screen.queryByText("Back of c1")).not.toBeInTheDocument();
    expect(screen.getByText("1 / 2")).toBeInTheDocument();
  });

  test("recall-first flow: reveal then grade calls reviewFlashcard and advances", async () => {
    vi.mocked(api.getFlashcards).mockResolvedValue(
      deck([card("c1"), card("c2")]),
    );
    vi.mocked(api.reviewFlashcard).mockImplementation(
      async (_ws, _trail, _concept, cardId) =>
        card(cardId, { reps: 1, box: 2 }),
    );

    renderPanel();

    await waitFor(() => {
      expect(screen.getByText("Front of c1")).toBeInTheDocument();
    });

    // Answer hidden until the card is clicked/tapped.
    expect(screen.queryByText("Back of c1")).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Reveal flashcard answer" }),
    );
    expect(screen.getByText("Back of c1")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Got it" }));

    expect(api.reviewFlashcard).toHaveBeenCalledWith(
      "workspace-1",
      "trail-1",
      "concept-1",
      "c1",
      true,
    );

    // Advanced to the second card, answer hidden again.
    await waitFor(() => {
      expect(screen.getByText("Front of c2")).toBeInTheDocument();
    });
    expect(screen.getByText("2 / 2")).toBeInTheDocument();
    expect(screen.queryByText("Back of c2")).not.toBeInTheDocument();

    // "Missed it" submits recalled=false.
    await userEvent.click(
      screen.getByRole("button", { name: "Reveal flashcard answer" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Missed it" }));
    expect(api.reviewFlashcard).toHaveBeenLastCalledWith(
      "workspace-1",
      "trail-1",
      "concept-1",
      "c2",
      false,
    );

    await waitFor(() => {
      expect(screen.getByText(/Reviewed all 2 cards/)).toBeInTheDocument();
    });
  });

  test("renders cloze flashcard fronts as blanks instead of raw template markers", async () => {
    vi.mocked(api.getFlashcards).mockResolvedValue(
      deck([
        card("c1", {
          card_type: "cloze",
          front: "The core theme is {{c1::unity}}.",
          back: "unity",
        }),
      ]),
    );

    renderPanel();

    await waitFor(() => {
      expect(screen.getByText("The core theme is _____.")).toBeInTheDocument();
    });
    expect(screen.queryByText(/\{\{c1::unity\}\}/)).not.toBeInTheDocument();
  });

  test("exhausted with no new cards shows the friendly decline message", async () => {
    mockStreamGenerateFlashcards(
      generateResponse([], {
        exhausted: true,
        reason: "No more useful facts to turn into cards.",
      }),
    );

    renderPanel();

    await waitFor(() => {
      expect(screen.getByText(/No flashcards yet/)).toBeInTheDocument();
    });

    await userEvent.click(
      screen.getByRole("button", { name: "Generate flashcards" }),
    );

    await waitFor(() => {
      expect(
        screen.getByText("No more useful facts to turn into cards."),
      ).toBeInTheDocument();
    });
  });

  test("treats a 404 'no deck' as an empty state, not a red error", async () => {
    vi.mocked(api.getFlashcards).mockRejectedValue(
      new Error(
        "No flashcard deck for concept 53a342bd-1111-2222-3333-444455556666",
      ),
    );

    renderPanel();

    await waitFor(() => {
      expect(
        screen.getByText(/No flashcards yet for this concept/),
      ).toBeInTheDocument();
    });
    // Friendly empty state, not the scary error/Retry affordance, and no UUID.
    expect(
      screen.queryByRole("button", { name: "Retry" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/53a342bd/)).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Generate flashcards" }),
    ).toBeInTheDocument();
  });

  test("declined generation about missing sources shows a calm hint, not an error", async () => {
    mockStreamGenerateFlashcards(
      generateResponse([], {
        exhausted: true,
        reason: "No linked source material to ground flashcards.",
      }),
    );

    renderPanel();

    await waitFor(() => {
      expect(screen.getByText(/No flashcards yet/)).toBeInTheDocument();
    });

    await userEvent.click(
      screen.getByRole("button", { name: "Generate flashcards" }),
    );

    await waitFor(() => {
      expect(
        screen.getByText("No linked source material to ground flashcards."),
      ).toBeInTheDocument();
    });
    // Source-related declines get an actionable hint, in calm (non-error) styling.
    expect(screen.getByText(/add a source first/i)).toBeInTheDocument();
  });

  test("shows an error state (not a crash) when loading fails", async () => {
    vi.mocked(api.getFlashcards).mockRejectedValue(new Error("boom"));

    renderPanel();

    await waitFor(() => {
      expect(screen.getByText("boom")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  test("shows an error when generation fails", async () => {
    mockStreamGenerateFlashcardsError(new Error("model unavailable"));

    renderPanel();

    await waitFor(() => {
      expect(screen.getByText(/No flashcards yet/)).toBeInTheDocument();
    });

    await userEvent.click(
      screen.getByRole("button", { name: "Generate flashcards" }),
    );

    await waitFor(() => {
      expect(screen.getByText("model unavailable")).toBeInTheDocument();
    });
  });

  test("renders an existing deck and exposes export links", async () => {
    vi.mocked(api.getFlashcards).mockResolvedValue(deck([card("c1")]));

    renderPanel();

    await waitFor(() => {
      expect(screen.getByText("Front of c1")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "Export" }));

    expect(screen.getByRole("link", { name: "CSV" })).toHaveAttribute(
      "href",
      expect.stringContaining("format=csv"),
    );
    expect(screen.getByRole("link", { name: "JSON" })).toHaveAttribute(
      "href",
      expect.stringContaining("format=json"),
    );
  });

  test("back button calls onBack", async () => {
    const onBack = vi.fn();
    renderPanel(onBack);

    await userEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });
});
