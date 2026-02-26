import type { AssistantResponseEnvelope } from "@/lib/api/types";
import { MarkdownContent } from "@/components/markdown-content";

const refusalReasonLabel: Record<string, string> = {
  insufficient_evidence: "Insufficient evidence from your notes",
  invalid_citations: "Citation validation failed",
};

export function ChatResponse({ response }: { response: AssistantResponseEnvelope }) {
  const evidenceById = new Map(response.evidence.map((item) => [item.evidence_id, item]));

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
      ) : (
        <p className="field-label">Grounding mode: {response.grounding_mode}</p>
      )}
    </div>
  );
}
