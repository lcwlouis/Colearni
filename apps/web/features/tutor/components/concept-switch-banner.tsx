import type { ConceptSwitchSuggestion, GraphConceptSummary } from "@/lib/api/types";

interface ConceptSwitchBannerProps {
  switchSuggestion: ConceptSwitchSuggestion;
  concepts: GraphConceptSummary[];
  setCurrentConcept: (concept: GraphConceptSummary | null) => void;
  setSuggestedConceptId: (id: number | null) => void;
  setSwitchDecision: (decision: "accept" | "reject" | null) => void;
  switchDecisionRef: React.MutableRefObject<"accept" | "reject" | null>;
  setSwitchSuggestion: (suggestion: ConceptSwitchSuggestion | null) => void;
  onStartNewChat?: (conceptId: number) => void;
}

/**
 * Non-blocking inline banner for concept switch suggestions.
 * Replaces the previous modal dialog to avoid interrupting the chat flow.
 * Rejecting a switch simply dismisses the banner — no synthetic follow-up.
 */
export function ConceptSwitchBanner({
  switchSuggestion,
  concepts,
  setCurrentConcept,
  setSuggestedConceptId,
  setSwitchDecision,
  switchDecisionRef,
  setSwitchSuggestion,
  onStartNewChat,
}: ConceptSwitchBannerProps) {
  const isOutOfScope = switchSuggestion.reason?.includes("outside the current chat scope");

  return (
    <div className="switch-banner" role="status" aria-live="polite">
      <span className="switch-banner-text">
        💡 {isOutOfScope ? "Different topic:" : "Possible topic:"}{" "}
        <strong>{switchSuggestion.to_concept_name}</strong>
      </span>
      <span className="switch-banner-actions">
        {isOutOfScope && onStartNewChat ? (
          <button
            type="button"
            className="secondary"
            style={{ fontSize: "0.75rem", padding: "0.15rem 0.5rem" }}
            onClick={() => {
              onStartNewChat(switchSuggestion.to_concept_id);
              setSwitchSuggestion(null);
            }}
          >
            Start new chat
          </button>
        ) : (
          <button
            type="button"
            className="secondary"
            style={{ fontSize: "0.75rem", padding: "0.15rem 0.5rem" }}
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
            Switch
          </button>
        )}
        <button
          type="button"
          className="secondary"
          style={{ fontSize: "0.75rem", padding: "0.15rem 0.5rem" }}
          onClick={() => {
            setSwitchDecision("reject");
            switchDecisionRef.current = "reject";
            setSwitchSuggestion(null);
          }}
        >
          Dismiss
        </button>
      </span>
    </div>
  );
}
