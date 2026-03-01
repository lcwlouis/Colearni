import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import React from "react";
import { ConceptSwitchBanner } from "./components/concept-switch-banner";
import type { ConceptSwitchSuggestion, GraphConceptSummary } from "@/lib/api/types";

const suggestion: ConceptSwitchSuggestion = {
  from_concept_id: 1,
  from_concept_name: "Linear Map",
  to_concept_id: 2,
  to_concept_name: "Gradient Descent",
  reason: "latest message appears closer to another concept",
};

const concepts: GraphConceptSummary[] = [
  {
    concept_id: 1,
    canonical_name: "Linear Map",
    mastery_status: "learning",
    mastery_score: 0.4,
    description: "A linear map",
    degree: 3,
  },
  {
    concept_id: 2,
    canonical_name: "Gradient Descent",
    mastery_status: "not_started",
    mastery_score: 0,
    description: "Gradient descent",
    degree: 2,
  },
];

function makeRef(): React.MutableRefObject<"accept" | "reject" | null> {
  return { current: null };
}

describe("ConceptSwitchBanner", () => {
  it("renders as a non-blocking banner, not a modal", () => {
    const html = renderToString(
      <ConceptSwitchBanner
        switchSuggestion={suggestion}
        concepts={concepts}
        setCurrentConcept={() => {}}
        setSuggestedConceptId={() => {}}
        setSwitchDecision={() => {}}
        switchDecisionRef={makeRef()}
        setSwitchSuggestion={() => {}}
      />,
    );
    expect(html).toContain('role="status"');
    expect(html).not.toContain('role="dialog"');
    expect(html).not.toContain("aria-modal");
    expect(html).not.toContain("switch-modal");
  });

  it("shows the suggested concept name", () => {
    const html = renderToString(
      <ConceptSwitchBanner
        switchSuggestion={suggestion}
        concepts={concepts}
        setCurrentConcept={() => {}}
        setSuggestedConceptId={() => {}}
        setSwitchDecision={() => {}}
        switchDecisionRef={makeRef()}
        setSwitchSuggestion={() => {}}
      />,
    );
    expect(html).toContain("Gradient Descent");
  });

  it("has Switch and Dismiss buttons", () => {
    const html = renderToString(
      <ConceptSwitchBanner
        switchSuggestion={suggestion}
        concepts={concepts}
        setCurrentConcept={() => {}}
        setSuggestedConceptId={() => {}}
        setSwitchDecision={() => {}}
        switchDecisionRef={makeRef()}
        setSwitchSuggestion={() => {}}
      />,
    );
    expect(html).toContain("Switch");
    expect(html).toContain("Dismiss");
  });

  it("does not include onSubmitChat prop or auto-submit behavior", () => {
    const html = renderToString(
      <ConceptSwitchBanner
        switchSuggestion={suggestion}
        concepts={concepts}
        setCurrentConcept={() => {}}
        setSuggestedConceptId={() => {}}
        setSwitchDecision={() => {}}
        switchDecisionRef={makeRef()}
        setSwitchSuggestion={() => {}}
      />,
    );
    // No synthetic clarification text
    expect(html).not.toContain("Which concept should we focus on");
  });
});
