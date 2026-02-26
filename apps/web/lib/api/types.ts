export type GroundingMode = "hybrid" | "strict";
export type RefusalReason = "insufficient_evidence" | "invalid_citations";
export type LuckyMode = "adjacent" | "wildcard";
export type QuizItemType = "short_answer" | "mcq";
export type QuizItemResult = "correct" | "partial" | "incorrect";
export type MasteryStatus = "locked" | "learning" | "learned";
export type CitationLabel = "From your notes" | "General context";

export type JsonValue = string | number | boolean | null | JsonObject | JsonValue[];
export type JsonObject = { [key: string]: JsonValue };
export type QuizItemPayloadDraft = Record<string, JsonValue>;

export interface HealthzResponse {
  status: string;
}

export interface EvidenceItem {
  evidence_id: string;
  source_type: "workspace" | "general";
  content: string;
  document_id: number | null;
  chunk_id: number | null;
  chunk_index: number | null;
  document_title: string | null;
  source_uri: string | null;
  score: number | null;
}

export interface Citation {
  citation_id: string;
  evidence_id: string;
  label: CitationLabel;
  quote: string | null;
}

export interface AssistantResponseEnvelope {
  kind: "answer" | "refusal";
  text: string;
  grounding_mode: GroundingMode;
  evidence: EvidenceItem[];
  citations: Citation[];
  refusal_reason: RefusalReason | null;
}

export interface ChatRespondRequest {
  workspace_id: number;
  query: string;
  user_id?: number;
  concept_id?: number;
  top_k?: number;
  grounding_mode?: GroundingMode;
}

export interface QuizChoiceSummary {
  id: string;
  text: string;
}

export interface QuizItemSummary {
  item_id: number;
  position: number;
  item_type: QuizItemType;
  prompt: string;
  choices: QuizChoiceSummary[] | null;
}

export interface QuizFeedbackItem {
  item_id: number;
  item_type: QuizItemType;
  result: QuizItemResult;
  is_correct: boolean;
  critical_misconception: boolean;
  feedback: string;
  score: number | null;
}

export interface QuizCreateResponse {
  quiz_id: number;
  workspace_id: number;
  user_id: number;
  concept_id: number;
  status: string;
  items: QuizItemSummary[];
}

export interface PracticeQuizSubmitResponse {
  quiz_id: number;
  attempt_id: number;
  score: number;
  passed: boolean;
  critical_misconception: boolean;
  overall_feedback: string;
  items: QuizFeedbackItem[];
  replayed: boolean;
  retry_hint: string | null;
}

export interface LevelUpQuizSubmitResponse extends PracticeQuizSubmitResponse {
  mastery_status: MasteryStatus;
  mastery_score: number;
}

export interface PracticeFlashcard {
  front: string;
  back: string;
  hint: string;
}

export interface PracticeFlashcardsResponse {
  workspace_id: number;
  concept_id: number;
  concept_name: string;
  flashcards: PracticeFlashcard[];
}

export interface GraphConceptDetailResponse {
  workspace_id: number;
  concept: JsonObject;
}

export interface GraphSubgraphResponse {
  workspace_id: number;
  root_concept_id: number;
  max_hops: number;
  nodes: JsonObject[];
  edges: JsonObject[];
}

export interface GraphLuckyResponse {
  workspace_id: number;
  seed_concept_id: number;
  mode: LuckyMode;
  pick: JsonObject;
}

export interface QuizItemCreateDraft {
  item_type: QuizItemType;
  prompt: string;
  payload: QuizItemPayloadDraft;
}

export interface CreateLevelUpQuizRequest {
  workspace_id: number;
  user_id: number;
  concept_id: number;
  session_id?: number;
  question_count?: number;
  items?: QuizItemCreateDraft[];
}

export interface QuizSubmitAnswer {
  item_id: number;
  answer: string;
}

export interface SubmitLevelUpQuizRequest {
  workspace_id: number;
  user_id: number;
  answers: QuizSubmitAnswer[];
}

export interface FlashcardsRequest {
  workspace_id: number;
  concept_id: number;
  card_count?: number;
}

export interface CreateQuizRequest {
  workspace_id: number;
  user_id: number;
  concept_id: number;
  session_id?: number;
  question_count?: number;
}

export interface SubmitQuizRequest {
  workspace_id: number;
  user_id: number;
  answers: QuizSubmitAnswer[];
}
