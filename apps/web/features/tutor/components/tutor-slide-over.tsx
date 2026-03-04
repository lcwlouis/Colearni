"use client";

import { useState } from "react";
import dynamic from "next/dynamic";

const SigmaGraph = dynamic(() => import("@/components/sigma-graph"), {
  ssr: false,
  loading: () => <p style={{ color: "var(--muted)" }}>Loading graph…</p>,
});
import { ConceptActivityPanel } from "@/components/concept-activity-panel";
import { LevelUpCard } from "@/components/level-up-card";
import { FlashcardStack } from "@/features/graph/components/flashcard-stack";
import { QuizHistory } from "@/features/graph/components/quiz-history";
import type {
  GraphConceptSummary,
  GraphSubgraphResponse,
  ConceptActivityResponse,
} from "@/lib/api/types";
import type { LevelUpState } from "@/lib/tutor/level-up-state";
import { masteryLabel } from "../types";

export type SlideOverTab = "graph" | "level-up" | "practice";

interface TutorSlideOverProps {
  closing: boolean;
  activeTab: SlideOverTab;
  onTabChange: (tab: SlideOverTab) => void;

  // Graph tab props
  currentConcept: GraphConceptSummary | null;
  graphViewConceptId: number | null;
  subgraph: GraphSubgraphResponse | null;
  conceptsLoading: boolean;
  conceptsError: string | null;
  loadSubgraph: (conceptId: number) => void;
  setGraphViewConceptId: (id: number | null) => void;
  tutorResetViewRef: React.MutableRefObject<(() => void) | null>;
  conceptActivity?: {
    activity: ConceptActivityResponse | null;
    loading: boolean;
    error: string | null;
    refetch: () => void;
  };

  // Level-up tab props
  levelUpState: LevelUpState;
  onStartQuiz: () => void;
  onAnswerChange: (itemId: number, value: string) => void;
  onSubmitQuiz: () => void;
  dispatchReset: () => void;

  // Practice tab props
  workspaceId?: string;
}

const TAB_LABELS: Record<SlideOverTab, string> = {
  graph: "Graph",
  "level-up": "Level-up",
  practice: "Practice",
};

export function TutorSlideOver({
  closing,
  activeTab,
  onTabChange,
  currentConcept,
  graphViewConceptId,
  subgraph,
  conceptsLoading,
  conceptsError,
  loadSubgraph,
  setGraphViewConceptId,
  tutorResetViewRef,
  conceptActivity,
  levelUpState,
  onStartQuiz,
  onAnswerChange,
  onSubmitQuiz,
  dispatchReset,
  workspaceId,
}: TutorSlideOverProps) {
  return (
    <aside className={`panel slide-over${closing ? " closing" : ""}`}>
      <nav className="slide-over__tabs" role="tablist">
        {(Object.keys(TAB_LABELS) as SlideOverTab[]).map((tab) => (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={activeTab === tab}
            className={`slide-over__tab${activeTab === tab ? " slide-over__tab--active" : ""}`}
            onClick={() => onTabChange(tab)}
          >
            {TAB_LABELS[tab]}
          </button>
        ))}
      </nav>

      <div className="slide-over__content">
        {activeTab === "graph" && (
          <GraphTabContent
            currentConcept={currentConcept}
            graphViewConceptId={graphViewConceptId}
            subgraph={subgraph}
            conceptsLoading={conceptsLoading}
            conceptsError={conceptsError}
            loadSubgraph={loadSubgraph}
            setGraphViewConceptId={setGraphViewConceptId}
            tutorResetViewRef={tutorResetViewRef}
            conceptActivity={conceptActivity}
          />
        )}
        {activeTab === "level-up" && (
          <LevelUpCard
            state={levelUpState}
            onStartQuiz={onStartQuiz}
            onAnswerChange={onAnswerChange}
            onSubmitQuiz={onSubmitQuiz}
            onRetryCreate={onStartQuiz}
            onRetrySubmit={onSubmitQuiz}
            onStartNew={() => {
              dispatchReset();
              setTimeout(() => onStartQuiz(), 0);
            }}
          />
        )}
        {activeTab === "practice" && (
          <PracticeTabContent
            workspaceId={workspaceId}
            conceptId={currentConcept?.concept_id ?? null}
            conceptName={currentConcept?.canonical_name ?? ""}
          />
        )}
      </div>
    </aside>
  );
}

/* ---------- Graph tab (migrated from TutorGraphDrawer) ---------- */

function GraphTabContent({
  currentConcept,
  graphViewConceptId,
  subgraph,
  conceptsLoading,
  conceptsError,
  loadSubgraph,
  setGraphViewConceptId,
  tutorResetViewRef,
  conceptActivity,
}: Pick<
  TutorSlideOverProps,
  | "currentConcept"
  | "graphViewConceptId"
  | "subgraph"
  | "conceptsLoading"
  | "conceptsError"
  | "loadSubgraph"
  | "setGraphViewConceptId"
  | "tutorResetViewRef"
  | "conceptActivity"
>) {
  return (
    <>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.5rem" }}>
        <h2 style={{ margin: 0 }}>Concept graph</h2>
        {currentConcept && graphViewConceptId != null && graphViewConceptId !== currentConcept.concept_id ? (
          <button
            type="button"
            className="secondary"
            style={{ fontSize: "0.7rem", padding: "0.15rem 0.5rem", whiteSpace: "nowrap" }}
            onClick={() => {
              void loadSubgraph(currentConcept.concept_id);
              setGraphViewConceptId(currentConcept.concept_id);
              tutorResetViewRef.current?.();
            }}
          >
            ← Back to topic
          </button>
        ) : null}
      </div>
      {conceptsLoading ? <p className="status loading">Loading concepts...</p> : null}
      {conceptsError ? <p className="status error">{conceptsError}</p> : null}
      {subgraph ? (
        <SigmaGraph
          nodes={subgraph.nodes}
          edges={subgraph.edges}
          selectedId={currentConcept?.concept_id}
          onSelect={(id) => {
            setGraphViewConceptId(id);
            void loadSubgraph(id);
          }}
          onResetViewReady={(fn) => {
            tutorResetViewRef.current = fn;
          }}
          width={320}
          height={350}
          compact
        />
      ) : !conceptsLoading ? (
        <p className="status empty">Select a concept to view its graph.</p>
      ) : null}
      {currentConcept ? (
        <div className="graph-legend">
          <p>
            <strong>{currentConcept.canonical_name}</strong>
          </p>
          <span className="field-label">
            {masteryLabel(currentConcept.mastery_status, currentConcept.mastery_score)}
          </span>
          {currentConcept.description ? (
            <p style={{ fontSize: "0.85rem", color: "var(--muted)", marginTop: "0.35rem", lineHeight: 1.5 }}>
              {currentConcept.description.length > 200
                ? currentConcept.description.slice(0, 200) + "…"
                : currentConcept.description}
            </p>
          ) : null}
        </div>
      ) : null}
      {conceptActivity ? (
        <div style={{ borderTop: "1px solid var(--line)", paddingTop: "0.5rem", marginTop: "0.5rem" }}>
          <ConceptActivityPanel
            activity={conceptActivity.activity}
            loading={conceptActivity.loading}
            error={conceptActivity.error}
            onRefresh={conceptActivity.refetch}
          />
        </div>
      ) : null}
    </>
  );
}

/* ---------- Practice tab ---------- */

function PracticeTabContent({
  workspaceId,
  conceptId,
  conceptName,
}: {
  workspaceId?: string;
  conceptId: number | null;
  conceptName: string;
}) {
  const [section, setSection] = useState<"flashcards" | "quizzes">("flashcards");

  if (!workspaceId || conceptId == null) {
    return <p style={{ color: "var(--muted)", padding: "1rem" }}>Select a concept to view practice material.</p>;
  }

  return (
    <>
      <nav className="slide-over__tabs slide-over__tabs--sub" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={section === "flashcards"}
          className={`slide-over__tab${section === "flashcards" ? " slide-over__tab--active" : ""}`}
          onClick={() => setSection("flashcards")}
        >
          Flashcards
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={section === "quizzes"}
          className={`slide-over__tab${section === "quizzes" ? " slide-over__tab--active" : ""}`}
          onClick={() => setSection("quizzes")}
        >
          Quizzes
        </button>
      </nav>

      {section === "flashcards" ? (
        <FlashcardStack workspaceId={workspaceId} conceptId={conceptId} conceptName={conceptName} />
      ) : (
        <QuizHistory workspaceId={workspaceId} conceptId={conceptId} />
      )}
    </>
  );
}
