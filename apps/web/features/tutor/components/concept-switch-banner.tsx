import type { ConceptSwitchSuggestion, GraphConceptSummary } from "@/lib/api/types";

interface ConceptSwitchBannerProps {
  switchSuggestion: ConceptSwitchSuggestion;
  concepts: GraphConceptSummary[];
  setCurrentConcept: (concept: GraphConceptSummary | null) => void;
  setSuggestedConceptId: (id: number | null) => void;
  setSwitchDecision: (decision: "accept" | "reject" | null) => void;
  switchDecisionRef: React.MutableRefObject<"accept" | "reject" | null>;
  setSwitchSuggestion: (suggestion: ConceptSwitchSuggestion | null) => void;
  onSubmitChat: (text: string) => void;
}

export function ConceptSwitchBanner({
  switchSuggestion,
  concepts,
  setCurrentConcept,
  setSuggestedConceptId,
  setSwitchDecision,
  switchDecisionRef,
  setSwitchSuggestion,
  onSubmitChat,
}: ConceptSwitchBannerProps) {
  return (
    <div className="switch-modal-backdrop" role="dialog" aria-modal="true">
      <div className="panel switch-modal">
        <h3>Concept switch suggested</h3>
        <p>
          The tutor inferred your latest message may be about{" "}
          <strong>{switchSuggestion.to_concept_name}</strong> instead of{" "}
          <strong>{switchSuggestion.from_concept_name}</strong>.
        </p>
        <p className="field-label">Reason: {switchSuggestion.reason}</p>
        <div className="button-row">
          <button
            type="button"
            onClick={() => {
              const matched = concepts.find(
                (item) => item.concept_id === switchSuggestion.to_concept_id,
              );
              if (matched) setCurrentConcept(matched);
              setSuggestedConceptId(switchSuggestion.to_concept_id);
              setSwitchDecision("accept");
              switchDecisionRef.current = "accept";
              setSwitchSuggestion(null);
            }}
          >
            Switch concept
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setSwitchDecision("reject");
              switchDecisionRef.current = "reject";
              setSwitchSuggestion(null);
              // E3: Auto-fire a follow-up to get the clarification question
              void onSubmitChat("Which concept should we focus on?");
            }}
          >
            Keep current
          </button>
        </div>
      </div>
    </div>
  );
}
