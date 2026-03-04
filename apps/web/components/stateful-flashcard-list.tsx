"use client";

import { useState } from "react";
import type { StatefulFlashcard, FlashcardSelfRating } from "@/lib/api/types";

const RATING_BUTTONS: { rating: FlashcardSelfRating; label: string; color: string }[] = [
  { rating: "again", label: "Again", color: "#e74c3c" },
  { rating: "hard", label: "Hard", color: "#e67e22" },
  { rating: "good", label: "Good", color: "#27ae60" },
  { rating: "easy", label: "Easy", color: "#2980b9" },
];

type Props = {
  flashcards: StatefulFlashcard[];
  conceptName: string;
  onRate?: (flashcardId: string, rating: FlashcardSelfRating) => void;
  ratingInFlight?: boolean;
};

export function StatefulFlashcardList({ flashcards, conceptName, onRate, ratingInFlight }: Props) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [showAnswer, setShowAnswer] = useState(false);
  const [showHint, setShowHint] = useState(false);

  const card = flashcards[currentIndex];
  if (!card) return null;

  const goTo = (index: number) => {
    setCurrentIndex(index);
    setShowAnswer(false);
    setShowHint(false);
  };

  const handleRate = (rating: FlashcardSelfRating) => {
    if (onRate) {
      onRate(card.flashcard_id, rating);
    }
    // Auto-advance on rate
    if (currentIndex < flashcards.length - 1) {
      goTo(currentIndex + 1);
    }
  };

  const ratedCount = flashcards.filter((f) => f.self_rating !== null).length;

  return (
    <div className="flashcard-stack-container">
      <div className="flashcard-stack-header">
        <h3>Flashcards — {conceptName}</h3>
        <span className="flashcard-counter">
          {currentIndex + 1} of {flashcards.length} · {ratedCount} rated
        </span>
      </div>

      <div className="flashcard-stage" key={currentIndex}>
        <div className={`flashcard${showAnswer ? " revealed" : ""}${card.self_rating ? " rated" : ""}`}>
          <button
            type="button"
            className="flashcard-toggle"
            onClick={() => setShowAnswer((prev) => !prev)}
          >
            <p className="flashcard-front">{card.front}</p>
            {showAnswer ? (
              <div className="flashcard-back">
                <p>{card.back}</p>
              </div>
            ) : (
              <p className="flashcard-tap-label">Tap to reveal answer</p>
            )}
          </button>

          {/* Hint */}
          {!showAnswer && card.hint ? (
            <div className="flashcard-hint-area">
              {showHint ? (
                <p className="flashcard-hint">{card.hint}</p>
              ) : (
                <button
                  type="button"
                  className="secondary flashcard-hint-btn"
                  onClick={() => setShowHint(true)}
                >
                  Show hint
                </button>
              )}
            </div>
          ) : null}
          {showAnswer && card.hint ? (
            <div className="flashcard-hint-area">
              <p className="flashcard-hint">{card.hint}</p>
            </div>
          ) : null}

          {/* Self-rating buttons — show when answer is revealed */}
          {showAnswer && onRate ? (
            <div className="flashcard-rating-row" style={{ display: "flex", gap: "0.5rem", justifyContent: "center", marginTop: "0.75rem", paddingBottom: "0.5rem" }}>
              {card.self_rating ? (
                <span style={{ fontSize: "0.85rem", color: "var(--foreground-muted, #888)" }}>
                  Rated: <strong>{card.self_rating}</strong>
                </span>
              ) : (
                RATING_BUTTONS.map(({ rating, label, color }) => (
                  <button
                    key={rating}
                    type="button"
                    disabled={ratingInFlight}
                    onClick={() => handleRate(rating)}
                    style={{
                      padding: "4px 12px",
                      borderRadius: "6px",
                      border: `1px solid ${color}`,
                      color,
                      background: "transparent",
                      fontSize: "0.85rem",
                      fontWeight: 600,
                      cursor: ratingInFlight ? "not-allowed" : "pointer",
                      opacity: ratingInFlight ? 0.5 : 1,
                    }}
                  >
                    {label}
                  </button>
                ))
              )}
            </div>
          ) : null}
        </div>
      </div>

      <div className="flashcard-nav">
        <button
          type="button"
          className="secondary flashcard-nav-btn"
          disabled={currentIndex === 0}
          onClick={() => goTo(currentIndex - 1)}
        >
          ← Previous
        </button>
        <button
          type="button"
          className="secondary flashcard-nav-btn"
          disabled={currentIndex === flashcards.length - 1}
          onClick={() => goTo(currentIndex + 1)}
        >
          Next →
        </button>
      </div>
    </div>
  );
}
