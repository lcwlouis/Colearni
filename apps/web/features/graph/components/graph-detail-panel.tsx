import { useState, useMemo } from "react";
import { AsyncState } from "@/components/async-state";
import { FlashcardStack } from "./flashcard-stack";
import { QuizHistory } from "./quiz-history";
import { ConceptChatLinks } from "./concept-chat-links";

const TIER_BADGE_STYLES: Record<string, React.CSSProperties> = {
  umbrella: { background: '#e0e7ff', color: '#4338ca', borderRadius: '9999px', padding: '0.1rem 0.55rem', fontSize: '0.7rem', fontWeight: 600, letterSpacing: '0.05em', display: 'inline-block', verticalAlign: 'middle' },
  topic:    { background: '#dbeafe', color: '#1d4ed8', borderRadius: '9999px', padding: '0.1rem 0.55rem', fontSize: '0.7rem', fontWeight: 600, letterSpacing: '0.05em', display: 'inline-block', verticalAlign: 'middle' },
  subtopic: { background: '#ccfbf1', color: '#0f766e', borderRadius: '9999px', padding: '0.1rem 0.55rem', fontSize: '0.7rem', fontWeight: 600, letterSpacing: '0.05em', display: 'inline-block', verticalAlign: 'middle' },
  granular: { background: '#f3f4f6', color: '#374151', borderRadius: '9999px', padding: '0.1rem 0.55rem', fontSize: '0.7rem', fontWeight: 600, letterSpacing: '0.05em', display: 'inline-block', verticalAlign: 'middle' },
};
import { StatefulFlashcardList } from "@/components/stateful-flashcard-list";
import { PracticeQuizCard } from "@/components/practice-quiz-card";
import { ConceptActivityPanel } from "@/components/concept-activity-panel";
import type {
  JsonObject,
  StatefulFlashcard,
  FlashcardSelfRating,
  ConceptActivityResponse,
} from "@/lib/api/types";
import type { GraphState } from "@/lib/graph/graph-state";
import type { PracticeState } from "@/lib/practice/practice-state";

interface GraphDetailPanelProps {
  wsId: string;
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
  conceptActivity?: {
    activity: ConceptActivityResponse | null;
    loading: boolean;
    error: string | null;
    refetch: () => void;
  };
  onOpenQuiz?: (quizId: number) => void;
  onRetryQuiz?: (quizId: number) => void;
  onOpenFlashcardRun?: (runId: string) => void;
  allNodes?: Array<{ concept_id: number; canonical_name: string; tier?: string | null; description?: string }>;
  filteredTiers?: ReadonlySet<string>;
}

export function GraphDetailPanel({
  wsId,
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
  conceptActivity,
  onOpenQuiz,
  onRetryQuiz,
  onOpenFlashcardRun,
  allNodes,
  filteredTiers,
}: GraphDetailPanelProps) {
  const filteredNodes = useMemo(() => {
    if (!allNodes) return [];
    if (!filteredTiers || filteredTiers.size >= 4) return allNodes;
    return allNodes.filter(n => filteredTiers.has(n.tier ?? ''));
  }, [allNodes, filteredTiers]);
  const [activeTab, setActiveTab] = useState<"flashcards" | "quizzes" | "chat">("flashcards");
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
        empty={false}
        emptyLabel=""
      />

      {!selectedDetail && phase !== "loading_detail" && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', flex: 1, minHeight: 0 }}>
          <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--muted)', padding: '0 0 0.5rem' }}>
            {filteredNodes.length > 0
              ? `${filteredNodes.length} concepts — select one to explore`
              : "Select a concept to explore."}
          </p>
          {filteredNodes.length > 0 && (
            <div style={{ overflowY: 'auto', flex: 1 }}>
              {filteredNodes.map((node) => (
                <button
                  key={node.concept_id}
                  type="button"
                  onClick={() => selectConcept(node.concept_id)}
                  style={{
                    display: 'block',
                    width: '100%',
                    textAlign: 'left',
                    background: 'none',
                    border: 'none',
                    borderBottom: '1px solid var(--line)',
                    padding: '0.5rem 0.25rem',
                    cursor: 'pointer',
                    fontSize: '0.85rem',
                    color: 'inherit',
                  }}
                >
                  <span style={{ fontWeight: 500 }}>{node.canonical_name}</span>
                  {node.tier && (
                    <span style={{
                      ...(TIER_BADGE_STYLES[node.tier] ?? {}),
                      marginLeft: '0.4rem',
                    }}>
                      {node.tier.toUpperCase()}
                    </span>
                  )}
                  {node.description && (
                    <span style={{ display: 'block', color: 'var(--muted)', fontSize: '0.8rem', marginTop: '0.15rem' }}>
                      {node.description.slice(0, 100)}{node.description.length > 100 ? '…' : ''}
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {selectedDetail ? (
        <>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
            {selectedDetail.concept.canonical_name}
            {selectedDetail.concept.tier != null && (
              <span style={TIER_BADGE_STYLES[selectedDetail.concept.tier]}>
                {selectedDetail.concept.tier.toUpperCase()}
              </span>
            )}
          </h1>
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
            <div className="lucky-pick panel stack" style={{ opacity: luckyLoading ? 0.5 : 1, transition: 'opacity 0.15s' }}>
              <h3>
                🎲{" "}{luckyPick?.mode === "adjacent" ? "Adjacent" : "Wildcard"}{" "}
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
          ) : luckyLoading ? (
            <div className="lucky-pick panel stack">
              <h3>🎲 Loading suggestion…</h3>
            </div>
          ) : null}

          <div
            style={{
              borderTop: "1px solid var(--line)",
              paddingTop: "0.75rem",
              marginTop: "0.25rem",
            }}
          >
            {selectedDetail && wsId ? (
              <>
                <div style={{ display: "flex", borderBottom: "2px solid var(--line)", marginBottom: "0.75rem" }}>
                  {(["flashcards", "quizzes", "chat"] as const).map((tab) => (
                    <button
                      key={tab}
                      type="button"
                      onClick={() => setActiveTab(tab)}
                      style={{
                        background: "none",
                        border: "none",
                        borderBottom: activeTab === tab ? "2px solid var(--accent, #4338ca)" : "2px solid transparent",
                        padding: "0.5rem 1rem",
                        fontWeight: activeTab === tab ? 600 : 400,
                        cursor: "pointer",
                        fontSize: "0.9rem",
                        color: activeTab === tab ? "var(--accent, #4338ca)" : "inherit",
                        marginBottom: "-2px",
                      }}
                    >
                      {tab === "flashcards" ? "Flashcards" : tab === "quizzes" ? "Quizzes" : "Chat"}
                    </button>
                  ))}
                </div>

                {activeTab === "flashcards" && (
                  <FlashcardStack
                    workspaceId={wsId}
                    conceptId={selectedDetail.concept.concept_id}
                    conceptName={selectedDetail.concept.canonical_name}
                    onGenerateFlashcards={loadStatefulFlashcards}
                  />
                )}

                {activeTab === "quizzes" && (
                  <QuizHistory
                    workspaceId={wsId}
                    conceptId={selectedDetail.concept.concept_id}
                    onCreateQuiz={loadQuiz}
                  />
                )}

                {activeTab === "chat" && (
                  <ConceptChatLinks
                    conceptName={selectedDetail.concept.canonical_name}
                    conceptId={selectedDetail.concept.concept_id}
                    workspaceId={wsId}
                  />
                )}
              </>
            ) : null}

            {conceptActivity ? (
              <div style={{ borderTop: "1px solid var(--line)", paddingTop: "0.75rem", marginTop: "0.5rem" }}>
                <ConceptActivityPanel
                  activity={conceptActivity.activity}
                  loading={conceptActivity.loading}
                  error={conceptActivity.error}
                  onRefresh={conceptActivity.refetch}
                  onOpenQuiz={onOpenQuiz}
                  onRetryQuiz={onRetryQuiz}
                  onOpenFlashcardRun={onOpenFlashcardRun}
                />
              </div>
            ) : null}
          </div>
        </>
      ) : null}
    </section>
  );
}
