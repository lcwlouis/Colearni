"use client";

import { useState } from "react";
import type { PracticeFlashcard } from "@/lib/api/types";

type Props = { flashcards: PracticeFlashcard[]; conceptName: string };

export function FlashcardList({ flashcards, conceptName }: Props) {
    const [showAnswer, setShowAnswer] = useState<Record<number, boolean>>({});
    const [showHint, setShowHint] = useState<Record<number, boolean>>({});

    const toggleAnswer = (i: number) => setShowAnswer((r) => ({ ...r, [i]: !r[i] }));
    const toggleHint = (i: number) => setShowHint((r) => ({ ...r, [i]: !r[i] }));

    return (
        <div className="stack">
            <h3>Flashcards — {conceptName}</h3>
            <ul className="flashcard-grid">
                {flashcards.map((card, i) => (
                    <li key={i} className={`flashcard${showAnswer[i] ? " revealed" : ""}`}>
                        <button type="button" className="flashcard-toggle" onClick={() => toggleAnswer(i)}>
                            <p className="flashcard-front">{card.front}</p>
                            {showAnswer[i] ? (
                                <div className="flashcard-back">
                                    <p>{card.back}</p>
                                </div>
                            ) : (
                                <p className="field-label">Tap to reveal answer</p>
                            )}
                        </button>
                        {showAnswer[i] && card.hint ? (
                            <div className="flashcard-hint-area">
                                {showHint[i] ? (
                                    <p className="flashcard-hint">{card.hint}</p>
                                ) : (
                                    <button type="button" className="secondary flashcard-hint-btn" onClick={() => toggleHint(i)}>
                                        Show hint
                                    </button>
                                )}
                            </div>
                        ) : null}
                    </li>
                ))}
            </ul>
        </div>
    );
}
