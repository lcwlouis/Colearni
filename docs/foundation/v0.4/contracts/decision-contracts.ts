/** Desk v0.4 OPTIONAL internal decision vocabulary; not any vendor API schema. */
export type DecisionTask = "current_turn_intent" | "context_relevance" | "representation_choice";
export interface DecisionCandidate { id: string; description: string }
export interface DecisionContextItem {
  objectId: string;
  revision: number;
  text: string;
}
export interface DecisionRequest {
  requestId: string;
  task: DecisionTask;
  rubricVersion: string;
  workspaceId: string;
  deskId: string;
  turnId: string;
  /** Filtered by trusted code; sending these fields does not grant permission. */
  context: DecisionContextItem[];
  allowedCandidates: DecisionCandidate[];
  deadlineAt: string;
  maximumInputSize: number;
  dataPolicy: "configured_local_only" | "explicitly_allowed_remote";
}
export interface DecisionMetrics {
  providerId: string;
  modelRevision?: string;
  adapterVersion: string;
  elapsedMs: number;
  inputTokens?: number;
  outputTokens?: number;
  /** Preserve meaning; do not compare across providers without evaluation. */
  reportedConfidence?: {
    value: number;
    semantics: "probability_concentration" | "provider_probability" | "self_report" | "other";
    description: string;
  };
}
export type DecisionResult = (
  | { outcome: "candidate"; candidateId: string }
  | { outcome: "abstain"; reason: "ambiguous" | "insufficient_context" | "policy" }
  | { outcome: "unavailable"; reason: "disabled" | "timeout" | "invalid_response" | "unsupported" | "provider_error" }
) & { requestId: string; metrics?: DecisionMetrics };
/** A result never grants a capability or mutates user-authored data. */
