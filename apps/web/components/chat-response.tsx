import type { AssistantResponseEnvelope, ActionCTA } from "@/lib/api/types";
import { MarkdownContent } from "@/components/markdown-content";

const refusalReasonLabel: Record<string, string> = {
  insufficient_evidence: "Insufficient evidence from your notes",
  invalid_citations: "Citation validation failed",
};

const ctaLabel: Record<string, string> = {
  quiz_cta: "📝 Take a quiz",
  review_cta: "🔄 Review",
  research_cta: "🔍 Research",
};

export function ChatResponse({ response, onCtaClick }: { response: AssistantResponseEnvelope; onCtaClick?: (cta: ActionCTA) => void }) {
  const evidenceById = new Map(response.evidence.map((item) => [item.evidence_id, item]));
  const isSocial = response.response_mode === "social";
  const actions = response.actions ?? [];

  return (
    <div className={`chat-response ${response.kind === "refusal" ? "refusal" : "answer"}`}>
      <MarkdownContent content={response.text} />
      {response.kind === "refusal" ? (
        <div className="chat-refusal-callout" role="status">
          <p className="chat-refusal-title">
            {response.grounding_mode === "strict" ? "Strict grounding refusal" : "Grounding refusal"}
          </p>
          <p className="chat-refusal-reason">
            Reason: {refusalReasonLabel[response.refusal_reason ?? ""] ?? response.refusal_reason}
          </p>
        </div>
      ) : isSocial ? (
        null /* Social responses: no citation/evidence panel */
      ) : response.citations.length > 0 ? (
        <details className="citation-toggle">
          <summary className="citation-summary">
            {response.citations.length} citation{response.citations.length !== 1 ? "s" : ""} · {response.grounding_mode}
          </summary>
          <ul className="chat-citations" aria-label="Citations">
            {response.citations.map((citation) => {
              const evidence = evidenceById.get(citation.evidence_id);
              return (
                <li key={citation.citation_id} className="chat-citation-item">
                  <p>
                    <strong>{citation.label}</strong>
                    {citation.quote ? `: ${citation.quote}` : ""}
                  </p>
                  {evidence ? (
                    <p className="field-label">
                      Evidence {evidence.evidence_id}
                      {evidence.document_title ? ` · ${evidence.document_title}` : ""}
                      {typeof evidence.score === "number" ? ` · score ${evidence.score.toFixed(2)}` : ""}
                    </p>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </details>
      ) : !isSocial ? (
        <p className="field-label">Grounding mode: {response.grounding_mode}</p>
      ) : null}

      {/* CTA action buttons */}
      {actions.length > 0 ? (
        <div className="chat-cta-row" style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem", flexWrap: "wrap" }}>
          {actions.map((cta, i) => (
            <button
              key={i}
              type="button"
              className="secondary"
              onClick={() => onCtaClick?.(cta)}
              style={{ fontSize: "0.85rem", padding: "4px 10px" }}
            >
              {ctaLabel[cta.action_type] ?? cta.label}
              {cta.concept_name ? ` — ${cta.concept_name}` : ""}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
