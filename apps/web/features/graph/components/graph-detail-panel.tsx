import { AsyncState } from "@/components/async-state";
import { StatefulFlashcardList } from "@/components/stateful-flashcard-list";
import { PracticeQuizCard } from "@/components/practice-quiz-card";
import type {
  JsonObject,
  StatefulFlashcard,
  FlashcardSelfRating,
} from "@/lib/api/types";
import type { GraphState } from "@/lib/graph/graph-state";
import type { PracticeState } from "@/lib/practice/practice-state";

interface GraphDetailPanelProps {
  state: GraphState;
  practiceState: PracticeState;
  practiceMode: "none" | "flashcards" | "quiz";
  luckyLoading: boolean;
  statefulCards: StatefulFlashcard[];
  statefulConceptName: string;
  statefulLoading: boolean;
  statefulError: string | null;
  ratingInFlight: boolean;
  lucky: (mode: "adjacent" | "wildcard") => void;
  selectConcept: (id: number) => void;
  loadStatefulFlashcards: () => void;
  handleRate: (flashcardId: string, rating: FlashcardSelfRating) => void;
  loadQuiz: () => void;
  submitQuiz: () => void;
  handleNextQuiz: () => void;
  dispatchPractice: React.Dispatch<import("@/lib/practice/practice-state").PracticeAction>;
  setPracticeMode: (mode: "none" | "flashcards" | "quiz") => void;
  setStatefulCards: (cards: StatefulFlashcard[]) => void;
}

export function GraphDetailPanel({
  state,
  practiceState,
  practiceMode,
  luckyLoading,
  statefulCards,
  statefulConceptName,
  statefulLoading,
  statefulError,
  ratingInFlight,
  lucky,
  selectConcept,
  loadStatefulFlashcards,
  handleRate,
  loadQuiz,
  submitQuiz,
  handleNextQuiz,
  dispatchPractice,
  setPracticeMode,
  setStatefulCards,
}: GraphDetailPanelProps) {
  const { phase, selectedDetail, luckyPick, error } = state;
  const pick = luckyPick?.pick as
    | (JsonObject & {
        concept_id?: number;
        canonical_name?: string;
        description?: string;
        hop_distance?: number | null;
      })
    | undefined;

  return (
    <section className="panel graph-detail-panel">
      <AsyncState
        loading={phase === "loading_detail"}
        error={phase === "error" && !!selectedDetail ? error : null}
        empty={!selectedDetail && phase !== "loading_detail"}
        emptyLabel="Select a concept to explore."
      />

      {selectedDetail ? (
        <>
          <h1>{selectedDetail.concept.canonical_name}</h1>
          <p>{selectedDetail.concept.description}</p>
          {selectedDetail.concept.aliases.length > 0 ? (
            <p className="field-label">
              Aliases: {selectedDetail.concept.aliases.join(", ")}
            </p>
          ) : null}
          <p className="field-label">
            Connections: {selectedDetail.concept.degree}
          </p>

          <div className="button-row">
            <button
              type="button"
              className="secondary"
              disabled={luckyLoading}
              onClick={() => lucky("adjacent")}
            >
              Adjacent suggestion
            </button>
            <button
              type="button"
              className="secondary"
              disabled={luckyLoading}
              onClick={() => lucky("wildcard")}
            >
              Wildcard suggestion
            </button>
          </div>

          {pick ? (
            <div className="lucky-pick panel stack">
              <h3>
                🎲 {luckyPick?.mode === "adjacent" ? "Adjacent" : "Wildcard"}{" "}
                suggestion
              </h3>
              <p>
                <strong>{String(pick.canonical_name ?? "")}</strong>
              </p>
              <p>{String(pick.description ?? "")}</p>
              {pick.hop_distance != null ? (
                <p className="field-label">
                  Hop distance: {pick.hop_distance}
                </p>
              ) : null}
              {typeof pick.concept_id === "number" ? (
                <button
                  type="button"
                  onClick={() => selectConcept(pick.concept_id as number)}
                >
                  Select →
                </button>
              ) : null}
            </div>
          ) : null}

          <div
            style={{
              borderTop: "1px solid var(--line)",
              paddingTop: "0.75rem",
              marginTop: "0.25rem",
            }}
          >
            <div className="button-row" style={{ marginBottom: "0.75rem" }}>
              <button
                type="button"
                className={practiceMode === "flashcards" ? "" : "secondary"}
                onClick={loadStatefulFlashcards}
                disabled={statefulLoading}
              >
                {statefulLoading ? "Generating..." : "Flashcards"}
              </button>
              <button
                type="button"
                className={practiceMode === "quiz" ? "" : "secondary"}
                onClick={loadQuiz}
                disabled={practiceState.phase === "loading_quiz"}
              >
                {practiceState.phase === "loading_quiz"
                  ? "Creating..."
                  : "Practice quiz"}
              </button>
              {practiceMode !== "none" && (
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    dispatchPractice({ type: "reset" });
                    setPracticeMode("none");
                    setStatefulCards([]);
                  }}
                  style={{ marginLeft: "auto" }}
                >
                  ✕
                </button>
              )}
            </div>

            {practiceMode === "flashcards" && statefulCards.length > 0 ? (
              <div className="stack" style={{ gap: "1rem" }}>
                <StatefulFlashcardList
                  flashcards={statefulCards}
                  conceptName={statefulConceptName}
                  onRate={handleRate}
                  ratingInFlight={ratingInFlight}
                />
                <div className="button-row">
                  <button
                    type="button"
                    className="secondary"
                    disabled={statefulLoading}
                    onClick={loadStatefulFlashcards}
                  >
                    Generate more
                  </button>
                </div>
              </div>
            ) : null}

            {practiceState.quiz ||
            practiceState.phase === "loading_quiz" ||
            (practiceState.phase === "error" && practiceMode === "quiz") ? (
              <PracticeQuizCard
                state={practiceState}
                onAnswerChange={(id, v) =>
                  dispatchPractice({ type: "answer", item_id: id, answer: v })
                }
                onSubmitQuiz={submitQuiz}
                onReset={() => dispatchPractice({ type: "reset" })}
                onNextQuiz={handleNextQuiz}
              />
            ) : null}

            {practiceMode === "flashcards" && statefulError ? (
              <p className="status error">{statefulError}</p>
            ) : null}
          </div>
        </>
      ) : null}
    </section>
  );
}
