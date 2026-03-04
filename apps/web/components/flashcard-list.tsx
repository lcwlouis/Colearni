"use client";

import { useState } from "react";
import type { PracticeFlashcard } from "@/lib/api/types";

type Props = { flashcards: PracticeFlashcard[]; conceptName: string };

export function FlashcardList({ flashcards, conceptName }: Props) {
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

    return (
        <div className="flashcard-stack-container">
            <div className="flashcard-stack-header">
                <h3>Flashcards — {conceptName}</h3>
                <span className="flashcard-counter">
                    {currentIndex + 1} of {flashcards.length}
                </span>
            </div>

            <div className="flashcard-stage" key={currentIndex}>
                <div className={`flashcard${showAnswer ? " revealed" : ""}`}>
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
                    {/* Hint: show BEFORE revealing answer as a thinking aid */}
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
                    {/* When answer is revealed and there's a hint, always show it inline */}
                    {showAnswer && card.hint ? (
                        <div className="flashcard-hint-area">
                            <p className="flashcard-hint">{card.hint}</p>
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
