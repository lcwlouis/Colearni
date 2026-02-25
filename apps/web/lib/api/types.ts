export type GroundingMode = "hybrid" | "strict";
export type RefusalReason = "insufficient_evidence" | "invalid_citations";
export type LuckyMode = "adjacent" | "wildcard";

export type JsonValue = string | number | boolean | null | JsonObject | JsonValue[];
export type JsonObject = { [key: string]: JsonValue };

export interface HealthzResponse { status: string }
export interface AssistantResponseEnvelope {
  kind: "answer" | "refusal";
  text: string;
  grounding_mode: GroundingMode;
  evidence: JsonObject[];
  citations: JsonObject[];
  refusal_reason: RefusalReason | null;
}

export interface ChatRespondRequest { workspace_id: number; query: string; user_id?: number; concept_id?: number; top_k?: number; grounding_mode?: GroundingMode }
export interface QuizCreateResponse { quiz_id: number; workspace_id: number; user_id: number; concept_id: number; status: string; items: JsonObject[] }
export interface PracticeQuizSubmitResponse {
  quiz_id: number;
  attempt_id: number;
  score: number;
  passed: boolean;
  critical_misconception: boolean;
  overall_feedback: string;
  items: JsonObject[];
  replayed: boolean;
  retry_hint: string | null;
}
export interface LevelUpQuizSubmitResponse extends PracticeQuizSubmitResponse { mastery_status: "locked" | "learning" | "learned"; mastery_score: number }
export interface PracticeFlashcardsResponse { workspace_id: number; concept_id: number; concept_name: string; flashcards: JsonObject[] }

export interface GraphConceptDetailResponse { workspace_id: number; concept: JsonObject }
export interface GraphSubgraphResponse { workspace_id: number; root_concept_id: number; max_hops: number; nodes: JsonObject[]; edges: JsonObject[] }
export interface GraphLuckyResponse { workspace_id: number; seed_concept_id: number; mode: LuckyMode; pick: JsonObject }

export interface CreateLevelUpQuizRequest { workspace_id: number; user_id: number; concept_id: number; session_id?: number; question_count?: number; items?: JsonObject[] }
export interface SubmitLevelUpQuizRequest { workspace_id: number; user_id: number; answers: JsonObject[] }
export interface FlashcardsRequest { workspace_id: number; concept_id: number; card_count?: number }
export interface CreateQuizRequest { workspace_id: number; user_id: number; concept_id: number; session_id?: number; question_count?: number }
export interface SubmitQuizRequest { workspace_id: number; user_id: number; answers: JsonObject[] }
