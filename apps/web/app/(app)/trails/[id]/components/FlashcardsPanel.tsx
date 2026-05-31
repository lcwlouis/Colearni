"use client";

import { useCallback, useEffect, useState } from "react";

import { PinToggle } from "@/components/PinToggle";
import {
  flashcardsExportUrl,
  getFlashcards,
  reviewFlashcard,
  streamGenerateFlashcards,
} from "@/lib/api";
import type {
  Flashcard,
  FlashcardDeck,
  FlashcardGenerateResponse,
} from "@/lib/types";

import { QuizMarkdown } from "./QuizMarkdown";

interface FlashcardsPanelProps {
  workspaceId: string;
  trailId: string;
  conceptId: string;
  onBack: () => void;
}

// Order the session queue so genuinely due cards come first (new cards — never
// reviewed, `due` null — lead, then earliest due dates). Recall-first review
// walks the whole queue but surfaces the most-owed cards up front.
function buildQueue(cards: Flashcard[]): Flashcard[] {
  const now = Date.now();
  const dueTime = (card: Flashcard): number =>
    card.due === null ? -1 : new Date(card.due).getTime() - now;
  return [...cards].sort((a, b) => dueTime(a) - dueTime(b));
}

const UUID_RE =
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;

// Backend messages sometimes embed raw concept/deck UUIDs (e.g. "No flashcard
// deck for concept 53a342bd-..."). Those are noise to a learner, so strip them.
function sanitize(message: string): string {
  return message
    .replace(UUID_RE, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}

// A concept with no deck yet returns a 404 "not found" from getFlashcards. That
// is a normal empty state, not a real error — distinguish it from network/500s.
function looksLikeMissingDeck(message: string): boolean {
  return /not found|no flashcard deck|404/i.test(message);
}

// A declined-generation reason about missing sources gets an actionable hint.
function mentionsSources(message: string): boolean {
  return /source/i.test(message);
}

const CLOZE_PATTERN = /\{\{c\d+::(.*?)(?:::[^}]*)?\}\}/g;

function renderPromptFront(card: Flashcard): string {
  if (card.card_type !== "cloze") {
    return card.front;
  }
  // Render cloze prompts as learner-facing blanks rather than template markup.
  return card.front.replace(CLOZE_PATTERN, "_____");
}

export function FlashcardsPanel({
  workspaceId,
  trailId,
  conceptId,
  onBack,
}: FlashcardsPanelProps) {
  const [deck, setDeck] = useState<FlashcardDeck | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Session review state. `queue` is the ordered set of cards reviewed this
  // session; `index` walks through it; `revealed` gates the answer (recall-first).
  const [queue, setQueue] = useState<Flashcard[]>([]);
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [reviewError, setReviewError] = useState("");

  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState("");
  // Set when the generator honestly declined to add more useful cards.
  const [exhaustedMessage, setExhaustedMessage] = useState<string | null>(null);

  useEffect(() => {
    // The panel is concept-keyed (remounts per concept), so state starts fresh
    // on every mount; no synchronous reset needed.
    let cancelled = false;

    getFlashcards(workspaceId, trailId, conceptId)
      .then((loaded) => {
        if (cancelled) return;
        setDeck(loaded);
        setQueue(buildQueue(loaded.cards));
        setIndex(0);
        setRevealed(false);
        setLoading(false);
      })
      .catch((exc) => {
        if (cancelled) return;
        const message =
          exc instanceof Error ? exc.message : "Could not load flashcards";
        // No deck yet is a normal empty state, not an error.
        if (looksLikeMissingDeck(message)) {
          setDeck(null);
          setLoading(false);
          return;
        }
        setError(sanitize(message));
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [workspaceId, trailId, conceptId]);

  const handleGenerate = useCallback(
    async (mode: "new" | "extend") => {
      if (generating) return;
      const prevCount = deck?.cards.length ?? 0;
      setGenerating(true);
      setGenerateError("");
      setExhaustedMessage(null);
      try {
        const generated = await new Promise<FlashcardGenerateResponse>(
          (resolve, reject) => {
            streamGenerateFlashcards(
              workspaceId,
              trailId,
              conceptId,
              mode === "extend" ? { extend: true } : {},
              {
                onStatus: () => undefined,
                onDone: resolve,
                onError: (message) => reject(new Error(message)),
              },
            ).catch(reject);
          },
        );
        const nextDeck = generated.deck;
        setDeck(nextDeck);
        if (mode === "extend") {
          // Append only brand-new cards to the running session; keep progress.
          setQueue((current) => {
            const seen = new Set(current.map((card) => card.id));
            const added = buildQueue(
              nextDeck.cards.filter((card) => !seen.has(card.id)),
            );
            return [...current, ...added];
          });
        } else {
          setQueue(buildQueue(nextDeck.cards));
          setIndex(0);
          setRevealed(false);
        }
        if (generated.exhausted && nextDeck.cards.length <= prevCount) {
          setExhaustedMessage(
            sanitize(generated.reason) ||
              "No more useful cards to add right now.",
          );
        }
      } catch (exc) {
        setGenerateError(
          sanitize(
            exc instanceof Error
              ? exc.message
              : "Could not generate flashcards",
          ),
        );
      } finally {
        setGenerating(false);
      }
    },
    [conceptId, deck, generating, trailId, workspaceId],
  );

  const currentCard: Flashcard | null =
    index < queue.length ? queue[index] : null;

  const handleReview = useCallback(
    async (recalled: boolean) => {
      if (!currentCard || reviewing) return;
      setReviewing(true);
      setReviewError("");
      try {
        const updated = await reviewFlashcard(
          workspaceId,
          trailId,
          conceptId,
          currentCard.id,
          recalled,
        );
        setDeck((current) =>
          current
            ? {
                ...current,
                cards: current.cards.map((card) =>
                  card.id === updated.id ? updated : card,
                ),
              }
            : current,
        );
        setQueue((current) =>
          current.map((card) => (card.id === updated.id ? updated : card)),
        );
        setIndex((current) => current + 1);
        setRevealed(false);
      } catch (exc) {
        setReviewError(
          exc instanceof Error ? exc.message : "Could not save your review",
        );
      } finally {
        setReviewing(false);
      }
    },
    [conceptId, currentCard, reviewing, trailId, workspaceId],
  );

  // Keyboard shortcuts: space reveals the answer, y/n grade it. Skipped while a
  // review call is in flight so a double-tap never double-submits.
  useEffect(() => {
    if (!currentCard) return;
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }
      if (!revealed) {
        if (event.key === " " || event.key === "Enter") {
          event.preventDefault();
          setRevealed(true);
        }
        return;
      }
      if (reviewing) return;
      if (event.key === "y" || event.key === "Y") {
        event.preventDefault();
        void handleReview(true);
      } else if (event.key === "n" || event.key === "N") {
        event.preventDefault();
        void handleReview(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [currentCard, revealed, reviewing, handleReview]);

  const hasCards = (deck?.cards.length ?? 0) > 0;
  const sessionComplete = hasCards && index >= queue.length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-900">Flashcards</h3>
        <button
          type="button"
          onClick={onBack}
          className="text-xs text-slate-500 hover:text-slate-800"
        >
          Back
        </button>
      </div>

      {loading ? (
        <p className="py-8 text-center text-sm text-slate-500">
          Loading flashcards...
        </p>
      ) : error ? (
        <ErrorWithRetry
          message={error}
          onRetry={() => {
            setError("");
            setLoading(true);
            getFlashcards(workspaceId, trailId, conceptId)
              .then((loaded) => {
                setDeck(loaded);
                setQueue(buildQueue(loaded.cards));
                setIndex(0);
                setRevealed(false);
                setLoading(false);
              })
              .catch((exc) => {
                const message =
                  exc instanceof Error
                    ? exc.message
                    : "Could not load flashcards";
                if (looksLikeMissingDeck(message)) {
                  setDeck(null);
                  setLoading(false);
                  return;
                }
                setError(sanitize(message));
                setLoading(false);
              });
          }}
        />
      ) : (
        <>
          <p className="text-xs text-slate-500">
            Recall-first review: read the prompt, recall the answer, then reveal
            it and grade yourself. Cards are scheduled with spaced repetition.
          </p>

          {generating ? <GenerationStatus /> : null}

          {generateError ? (
            <ErrorWithRetry
              message={generateError}
              onRetry={() => handleGenerate(hasCards ? "extend" : "new")}
            />
          ) : null}

          {exhaustedMessage ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              <p>{exhaustedMessage}</p>
              {mentionsSources(exhaustedMessage) ? (
                <p className="mt-1 text-amber-700">
                  Flashcards are built from this concept&rsquo;s linked sources
                  &mdash; add a source first.
                </p>
              ) : null}
            </div>
          ) : null}

          {!hasCards && !generating ? (
            <div className="rounded-md border border-dashed border-slate-300 bg-slate-50 p-6 text-center">
              <p className="text-sm text-slate-600">
                No flashcards yet for this concept. Generate a source-grounded
                deck to start reviewing.
              </p>
              <button
                type="button"
                onClick={() => handleGenerate("new")}
                disabled={generating}
                className="mt-3 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Generate flashcards
              </button>
            </div>
          ) : null}

          {hasCards && deck ? (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <PinToggle
                  workspaceId={workspaceId}
                  trailId={trailId}
                  itemType="flashcard"
                  itemId={deck.id}
                />
                <FlashcardActions
                  workspaceId={workspaceId}
                  trailId={trailId}
                  conceptId={conceptId}
                  generating={generating}
                  onGenerateMore={() => handleGenerate("extend")}
                />
              </div>

              {reviewError ? (
                <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                  {reviewError}
                </div>
              ) : null}

              {sessionComplete ? (
                <ReviewComplete
                  total={queue.length}
                  onReviewAgain={() => {
                    setQueue(buildQueue(deck.cards));
                    setIndex(0);
                    setRevealed(false);
                  }}
                />
              ) : currentCard ? (
                <ReviewCard
                  card={currentCard}
                  position={index + 1}
                  total={queue.length}
                  revealed={revealed}
                  reviewing={reviewing}
                  onReveal={() => setRevealed(true)}
                  onGotIt={() => handleReview(true)}
                  onMissed={() => handleReview(false)}
                />
              ) : null}
            </>
          ) : null}
        </>
      )}
    </div>
  );
}

function FlashcardActions({
  workspaceId,
  trailId,
  conceptId,
  generating,
  onGenerateMore,
}: {
  workspaceId: string;
  trailId: string;
  conceptId: string;
  generating: boolean;
  onGenerateMore: () => void;
}) {
  const [exportOpen, setExportOpen] = useState(false);
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={onGenerateMore}
        disabled={generating}
        className="rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
      >
        Generate more
      </button>
      <div className="relative">
        <button
          type="button"
          onClick={() => setExportOpen((open) => !open)}
          className="rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
          aria-expanded={exportOpen}
        >
          Export
        </button>
        {exportOpen ? (
          <div className="absolute right-0 z-20 mt-1 w-32 rounded-lg border border-slate-200 bg-white p-1 text-xs shadow-lg">
            <a
              href={flashcardsExportUrl(workspaceId, trailId, conceptId, "csv")}
              target="_blank"
              rel="noreferrer"
              className="block rounded px-2 py-1.5 text-slate-700 hover:bg-slate-50"
            >
              CSV
            </a>
            <a
              href={flashcardsExportUrl(
                workspaceId,
                trailId,
                conceptId,
                "json",
              )}
              target="_blank"
              rel="noreferrer"
              className="block rounded px-2 py-1.5 text-slate-700 hover:bg-slate-50"
            >
              JSON
            </a>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function ReviewCard({
  card,
  position,
  total,
  revealed,
  reviewing,
  onReveal,
  onGotIt,
  onMissed,
}: {
  card: Flashcard;
  position: number;
  total: number;
  revealed: boolean;
  reviewing: boolean;
  onReveal: () => void;
  onGotIt: () => void;
  onMissed: () => void;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>
          {position} / {total}
        </span>
        <span>
          Box {card.box} · {card.reps} review{card.reps === 1 ? "" : "s"}
          {card.lapses > 0 ? ` · ${card.lapses} lapse` : ""}
          {card.lapses > 1 ? "s" : ""}
        </span>
      </div>

      <button
        type="button"
        onClick={() => {
          if (!revealed) {
            onReveal();
          }
        }}
        disabled={revealed}
        className="w-full rounded-xl border border-slate-200 bg-white p-5 text-left shadow-sm transition hover:border-blue-200 hover:shadow-md disabled:cursor-default disabled:hover:border-slate-200 disabled:hover:shadow-sm"
        aria-label={
          revealed ? "Flashcard answer shown" : "Reveal flashcard answer"
        }
      >
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Prompt
        </p>
        <QuizMarkdown
          text={renderPromptFront(card)}
          className="mt-2 text-base leading-7 text-slate-900"
        />
        {!revealed ? (
          <p className="mt-4 text-xs font-medium text-slate-400">
            Click or tap the card to reveal the answer.
          </p>
        ) : null}

        {revealed ? (
          <div className="mt-4 border-t border-slate-100 pt-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Answer
            </p>
            <QuizMarkdown
              text={card.back}
              className="mt-2 text-base leading-7 text-slate-800"
            />
            {card.hint ? (
              <p className="mt-3 rounded-md bg-slate-50 p-2 text-sm text-slate-600">
                <span className="font-semibold text-slate-700">Hint: </span>
                {card.hint}
              </p>
            ) : null}
          </div>
        ) : null}
      </button>

      {revealed ? (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onMissed}
            disabled={reviewing}
            className="h-10 flex-1 rounded-md border border-red-200 bg-red-50 text-sm font-medium text-red-700 hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Missed it
          </button>
          <button
            type="button"
            onClick={onGotIt}
            disabled={reviewing}
            className="h-10 flex-1 rounded-md border border-green-200 bg-green-50 text-sm font-medium text-green-700 hover:bg-green-100 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Got it
          </button>
        </div>
      ) : null}
    </div>
  );
}

function ReviewComplete({
  total,
  onReviewAgain,
}: {
  total: number;
  onReviewAgain: () => void;
}) {
  return (
    <div className="rounded-xl border border-green-200 bg-green-50 p-6 text-center">
      <p className="text-sm font-semibold text-green-800">
        Reviewed all {total} card{total === 1 ? "" : "s"}.
      </p>
      <p className="mt-1 text-sm text-green-700">
        Come back later to keep them fresh, or add more cards.
      </p>
      <button
        type="button"
        onClick={onReviewAgain}
        className="mt-3 rounded-md border border-green-300 bg-white px-4 py-2 text-sm font-medium text-green-700 hover:bg-green-100"
      >
        Review again
      </button>
    </div>
  );
}

function GenerationStatus() {
  return (
    <div
      className="rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm text-blue-900"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 h-3 w-3 animate-pulse rounded-full bg-blue-500" />
        <div>
          <p className="font-semibold">Writing your flashcards...</p>
          <p className="mt-1 text-blue-800">
            Pulling source-grounded facts and dropping duplicates.
          </p>
        </div>
      </div>
    </div>
  );
}

function ErrorWithRetry({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
      <p>{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-2 rounded-md border border-red-300 bg-white px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-100"
      >
        Retry
      </button>
    </div>
  );
}
