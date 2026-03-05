"use client";

import { useState, useEffect } from "react";
import type { StatefulFlashcard } from "@/lib/api/types";
import { apiClient } from "@/lib/api/client";

type Props = {
  workspaceId: string;
  conceptId: number;
  conceptName: string;
  onGenerateFlashcards?: () => void;
};

export function FlashcardStack({ workspaceId, conceptId, conceptName, onGenerateFlashcards }: Props) {
  const [cards, setCards] = useState<StatefulFlashcard[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [exhausted, setExhausted] = useState(false);
  const [exhaustedReason, setExhaustedReason] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  const generateMore = async () => {
    setGenerating(true);
    try {
      const res = await apiClient.generateStatefulFlashcards(workspaceId, { concept_id: conceptId });
      setCards(prev => {
        const seen = new Set(prev.map(c => c.flashcard_id));
        const newCards = res.flashcards.filter(c => !seen.has(c.flashcard_id));
        const merged = [...prev, ...newCards];
        // Navigate to first new card after render
        setTimeout(() => setCurrentIndex(prev.length), 0);
        return merged;
      });
      if (!res.has_more) {
        setExhausted(true);
        setExhaustedReason(res.exhausted_reason);
      }
      setFlipped(false);
    } catch (err) {
      console.error("Failed to generate more flashcards:", err);
    } finally {
      setGenerating(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    async function fetchAll() {
      setLoading(true);
      try {
        const runList = await apiClient.listFlashcardRuns(workspaceId, conceptId, 100);
        if (cancelled) return;

        const details = await Promise.all(
          runList.runs.map(r => apiClient.getFlashcardRun(workspaceId, r.run_id))
        );
        if (cancelled) return;

        // Merge all cards, dedup by flashcard_id
        const seen = new Set<string>();
        const merged: StatefulFlashcard[] = [];
        for (const detail of details) {
          for (const card of detail.flashcards) {
            if (!seen.has(card.flashcard_id)) {
              seen.add(card.flashcard_id);
              merged.push(card);
            }
          }
        }

        setCards(merged);
        setCurrentIndex(0);
        setFlipped(false);
        const latestRun = runList.runs[0];
        if (latestRun && !latestRun.has_more) {
          setExhausted(true);
        }
      } catch (err) {
        console.error("Failed to fetch flashcard runs:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchAll();
    return () => { cancelled = true; };
  }, [workspaceId, conceptId]);

  const prev = () => { setCurrentIndex(i => Math.max(0, i - 1)); setFlipped(false); };
  const next = () => { setCurrentIndex(i => Math.min(cards.length - 1, i + 1)); setFlipped(false); };

  if (loading) return <p style={{ color: "var(--muted)", padding: "1rem" }}>Loading flashcards…</p>;

  if (cards.length === 0) {
    return (
      <div style={{ padding: "1rem", textAlign: "center" }}>
        <p style={{ color: "var(--muted)", marginBottom: "0.5rem" }}>No flashcards yet</p>
        <button type="button" disabled={generating} onClick={() => { void generateMore(); onGenerateFlashcards?.(); }}>
          {generating ? "Generating…" : "Generate flashcards"}
        </button>
      </div>
    );
  }

  const card = cards[currentIndex];

  return (
    <div className="flashcard-stack">
      <div className="flashcard-stack__progress">
        {currentIndex + 1} / {cards.length}
      </div>

      <div className="flashcard-stack__stage">
        <div
          className={`flashcard-stack__card ${flipped ? "flashcard-stack__card--flipped" : ""}`}
          onClick={() => setFlipped(f => !f)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === " ") { e.preventDefault(); setFlipped(f => !f); } }}
        >
          <div className="flashcard-stack__card-inner">
            <div className="flashcard-stack__face flashcard-stack__front">
              <p className="flashcard-stack__front-text">{card.front}</p>
              <span className="flashcard-stack__tap-hint">Tap to flip</span>
            </div>
            <div className="flashcard-stack__face flashcard-stack__back">
              <p className="flashcard-stack__back-text">{card.back}</p>
              {card.hint && <p className="flashcard-stack__hint">💡 {card.hint}</p>}
            </div>
          </div>
        </div>
      </div>

      <div className="flashcard-stack__nav">
        <button type="button" onClick={prev} disabled={currentIndex === 0}>← Prev</button>
        <button type="button" onClick={next} disabled={currentIndex === cards.length - 1}>Next →</button>
      </div>

      {exhausted ? (
        <div className="flashcard-stack__exhausted">
          All content for this concept has been covered ✓
          {exhaustedReason && <div>{exhaustedReason}</div>}
        </div>
      ) : generating ? (
        <div className="flashcard-stack__generate">
          <span style={{ color: "var(--muted)" }}>Generating new flashcards…</span>
        </div>
      ) : (
        <div className="flashcard-stack__generate">
          <button type="button" onClick={generateMore}>Generate more</button>
        </div>
      )}
    </div>
  );
}
