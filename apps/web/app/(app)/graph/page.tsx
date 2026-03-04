"use client";

import { useGraphPage } from "@/features/graph/hooks/use-graph-page";
import { GraphVizPanel } from "@/features/graph/components/graph-viz-panel";
import { GraphDetailPanel } from "@/features/graph/components/graph-detail-panel";

export default function GraphPage() {
  const g = useGraphPage();

  if (g.auth.isLoading) return <p>Loading…</p>;

  return (
    <div className="graph-explorer" style={{ display: "flex", height: "100%", width: "100%", background: "var(--bg)", overflow: "hidden", flexDirection: "column" }}>
      <header className="graph-search-header">
        <h2 style={{ margin: 0 }}>Knowledge Graph</h2>
        <input
          className="concept-search"
          type="search"
          placeholder="Search concepts..."
          value={g.query}
          onChange={(e) => {
            g.setQuery(e.target.value);
            if (g.state.selectedDetail) g.dispatch({ type: "clear_detail" });
          }}
        />
      </header>

      <div className="graph-panels">
        <GraphVizPanel
          state={g.state}
          dispatch={g.dispatch}
          debouncedQuery={g.debouncedQuery}
          wsId={g.wsId}
          fullGraph={g.fullGraph}
          maxNodes={g.maxNodes}
          setMaxNodes={g.setMaxNodes}
          maxEdges={g.maxEdges}
          setMaxEdges={g.setMaxEdges}
          maxHops={g.maxHops}
          setMaxHops={g.setMaxHops}
          graphSearch={g.graphSearch}
          setGraphSearch={g.setGraphSearch}
          debouncedGraphSearch={g.debouncedGraphSearch}
          focusNodeId={g.focusNodeId}
          setFocusNodeId={g.setFocusNodeId}
          resetView={g.resetView}
          handleResetViewReady={g.handleResetViewReady}
          handleGraphSelect={g.handleGraphSelect}
          handleGraphBgClick={g.handleGraphBgClick}
          selectConcept={g.selectConcept}
          setQuery={g.setQuery}
          filteredTiers={g.filteredTiers}
          toggleTierFilter={g.toggleTierFilter}
          clearTierFilter={g.clearTierFilter}
          onGardenerSuccess={g.refreshFullGraph}
        />

        <GraphDetailPanel
          wsId={g.wsId}
          state={g.state}
          practiceState={g.practiceState}
          practiceMode={g.practiceMode}
          luckyLoading={g.luckyLoading}
          statefulCards={g.statefulCards}
          statefulConceptName={g.statefulConceptName}
          statefulLoading={g.statefulLoading}
          statefulError={g.statefulError}
          ratingInFlight={g.ratingInFlight}
          lucky={g.lucky}
          selectConcept={g.selectConcept}
          loadStatefulFlashcards={g.loadStatefulFlashcards}
          handleRate={g.handleRate}
          loadQuiz={g.loadQuiz}
          submitQuiz={g.submitQuiz}
          handleNextQuiz={g.handleNextQuiz}
          dispatchPractice={g.dispatchPractice}
          setPracticeMode={g.setPracticeMode}
          setStatefulCards={g.setStatefulCards}
          conceptActivity={g.conceptActivity}
          allNodes={g.fullGraph?.nodes}
          filteredTiers={g.filteredTiers}
        />
      </div>
    </div>
  );
}
