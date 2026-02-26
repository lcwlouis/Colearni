import type { AssistantResponseEnvelope } from "@/lib/api/types";

const refusalReasonLabel: Record<string, string> = {
  insufficient_evidence: "Insufficient evidence from your notes",
  invalid_citations: "Citation validation failed",
};

export function ChatResponse({ response }: { response: AssistantResponseEnvelope }) {
  const evidenceById = new Map(response.evidence.map((item) => [item.evidence_id, item]));

  return (
    <div className={`chat-response ${response.kind === "refusal" ? "refusal" : "answer"}`}>
      <p className="chat-text">{response.text}</p>
      {response.kind === "refusal" ? (
        <div className="chat-refusal-callout" role="status">
          <p className="chat-refusal-title">
            {response.grounding_mode === "strict" ? "Strict grounding refusal" : "Grounding refusal"}
          </p>
          <p className="chat-refusal-reason">
            Reason: {refusalReasonLabel[response.refusal_reason ?? ""] ?? response.refusal_reason}
          </p>
        </div>
      ) : (
        <>
          <p className="field-label">Grounding mode: {response.grounding_mode}</p>
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
        </>
      )}
    </div>
  );
}
