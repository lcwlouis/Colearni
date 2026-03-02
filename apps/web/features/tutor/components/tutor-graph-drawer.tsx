import dynamic from "next/dynamic";

const SigmaGraph = dynamic(() => import("@/components/sigma-graph"), {
  ssr: false,
  loading: () => <p style={{ color: "var(--muted)" }}>Loading graph…</p>,
});
import { ConceptActivityPanel } from "@/components/concept-activity-panel";
import type { GraphConceptSummary, GraphSubgraphResponse, ConceptActivityResponse } from "@/lib/api/types";
import { masteryLabel } from "../types";

interface TutorGraphDrawerProps {
  closingDrawer: "graph" | "quiz" | null;
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
}

export function TutorGraphDrawer({
  closingDrawer,
  currentConcept,
  graphViewConceptId,
  subgraph,
  conceptsLoading,
  conceptsError,
  loadSubgraph,
  setGraphViewConceptId,
  tutorResetViewRef,
  conceptActivity,
}: TutorGraphDrawerProps) {
  return (
    <aside className={`panel graph-drawer${closingDrawer === "graph" ? " closing" : ""}`}>
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
    </aside>
  );
}
