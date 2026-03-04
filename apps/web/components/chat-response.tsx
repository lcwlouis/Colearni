import type { AssistantResponseEnvelope, ActionCTA, AnswerParts } from "@/lib/api/types";
import { MarkdownContent } from "@/components/markdown-content";
import { useState } from "react";
import { useDevStats } from "@/lib/hooks/use-dev-stats";

const refusalReasonLabel: Record<string, string> = {
  insufficient_evidence: "Insufficient evidence from your notes",
  invalid_citations: "Citation validation failed",
};

const ctaLabel: Record<string, string> = {
  quiz_cta: "📝 Take a quiz",
  review_cta: "🔄 Review",
  research_cta: "🔍 Research",
  quiz_offer: "📝 Ready for a quiz?",
  quiz_start: "🚀 Start quiz now",
};

/**
 * Derive structured answer parts from the envelope.
 * Prefers backend-provided `answer_parts`; falls back to full text with no hint.
 */
function getAnswerParts(response: AssistantResponseEnvelope): AnswerParts {
  if (response.answer_parts) return response.answer_parts;
  return { body: response.text, hint: null };
}

export function CollapsibleHint({ hint, index }: { hint: string; index: number }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="chat-hint-section">
      <button type="button" className="chat-hint-toggle" onClick={() => setOpen(!open)}>
        {open ? "▼" : "▶"} 💡 Hint {index > 0 ? index + 1 : ""}
      </button>
      {open && (
        <div className="chat-hint-content">
          <MarkdownContent content={hint} />
        </div>
      )}
    </div>
  );
}

export function ChatResponse({ response, onCtaClick }: { response: AssistantResponseEnvelope; onCtaClick?: (cta: ActionCTA) => void }) {
  const { showDevStats } = useDevStats();
  const evidenceById = new Map(response.evidence.map((item) => [item.evidence_id, item]));
  const isSocial = response.response_mode === "social";
  const actions = response.actions ?? [];
  const { body: main, hint } = getAnswerParts(response);

  return (
    <div className={`chat-response ${response.kind === "refusal" ? "refusal" : "answer"}`}>
      <MarkdownContent content={main} />
      {hint ? <CollapsibleHint hint={hint} index={0} /> : null}
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

      {/* F5: Generation trace — controlled by backend APP_INCLUDE_DEV_STATS */}
      {showDevStats && response.generation_trace ? (
        <details className="dev-trace">
          <summary>
            ⚡ {response.generation_trace.model ?? "unknown"} · {response.generation_trace.timing_ms ?? "?"}ms · {response.generation_trace.total_tokens ?? "?"} tokens
            {response.generation_trace.plan_strategy ? ` · 🎯 ${response.generation_trace.plan_strategy}` : null}
          </summary>
          <pre>
            {JSON.stringify(response.generation_trace, null, 2)}
          </pre>
        </details>
      ) : null}
    </div>
  );
}
