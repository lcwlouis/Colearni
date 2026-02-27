export type GroundingMode = "hybrid" | "strict";
export type RefusalReason = "insufficient_evidence" | "invalid_citations";
export type LuckyMode = "adjacent" | "wildcard";
export type QuizItemType = "short_answer" | "mcq";
export type QuizItemResult = "correct" | "partial" | "incorrect";
export type MasteryStatus = "locked" | "learning" | "learned";
export type CitationLabel = "From your notes" | "General context";
export type ConceptSwitchDecision = "accept" | "reject";

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

export interface ConceptSwitchSuggestion {
  from_concept_id: number;
  from_concept_name: string;
  to_concept_id: number;
  to_concept_name: string;
  reason: string;
}

export interface ConversationMeta {
  session_id: number | null;
  resolved_concept_id: number | null;
  resolved_concept_name: string | null;
  concept_confidence: number | null;
  requires_clarification: boolean;
  concept_switch_suggestion: ConceptSwitchSuggestion | null;
}

export interface AssistantResponseEnvelope {
  kind: "answer" | "refusal";
  text: string;
  grounding_mode: GroundingMode;
  evidence: EvidenceItem[];
  citations: Citation[];
  refusal_reason: RefusalReason | null;
  conversation_meta: ConversationMeta | null;
  response_mode?: "grounded" | "social";
  actions?: ActionCTA[];
}

export interface ChatRespondRequest {
  query: string;
  session_id?: number;
  concept_id?: number;
  suggested_concept_id?: number;
  concept_switch_decision?: ConceptSwitchDecision;
  top_k?: number;
  grounding_mode?: GroundingMode;
}

export type ChatMessageType = "user" | "assistant" | "system" | "tool" | "card";

export interface ChatSessionSummary {
  session_id: number;
  workspace_id: number;
  user_id: number;
  title: string | null;
  last_activity_at: string;
}

export interface ChatSessionListResponse {
  workspace_id: number;
  user_id: number;
  sessions: ChatSessionSummary[];
}

export interface ChatMessageRecord {
  message_id: number;
  session_id: number;
  type: ChatMessageType;
  payload: JsonObject;
  created_at: string;
}

export interface ChatMessagesResponse {
  workspace_id: number;
  user_id: number;
  session_id: number;
  messages: ChatMessageRecord[];
}

export interface CreateChatSessionRequest {
  title?: string;
}

export interface DeleteChatSessionRequest {
  session_id: number;
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

export interface GraphConceptDetail {
  concept_id: number;
  canonical_name: string;
  description: string;
  aliases: string[];
  degree: number;
}

export interface GraphConceptDetailResponse {
  workspace_id: number;
  concept: GraphConceptDetail;
}

export interface GraphConceptSummary {
  concept_id: number;
  canonical_name: string;
  description: string;
  degree: number;
  mastery_status: MasteryStatus | null;
  mastery_score: number | null;
}

export interface GraphConceptListResponse {
  workspace_id: number;
  user_id: number | null;
  concepts: GraphConceptSummary[];
}

export interface GraphSubgraphNode {
  concept_id: number;
  canonical_name: string;
  description: string;
  hop_distance: number;
  mastery_status: MasteryStatus | null;
  mastery_score: number | null;
}

export interface GraphSubgraphEdge {
  edge_id: number;
  src_concept_id: number;
  tgt_concept_id: number;
  relation_type: string;
  description: string;
  keywords: string[];
  weight: number;
}

export interface GraphSubgraphResponse {
  workspace_id: number;
  root_concept_id: number;
  max_hops: number;
  nodes: GraphSubgraphNode[];
  edges: GraphSubgraphEdge[];
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
  answers: QuizSubmitAnswer[];
}

export interface FlashcardsRequest {
  concept_id: number;
  card_count?: number;
}

export interface CreateQuizRequest {
  concept_id: number;
  session_id?: number;
  question_count?: number;
}

export interface SubmitQuizRequest {
  answers: QuizSubmitAnswer[];
}

// ── WOW Release Types ──────────────────────────────────────────────

export type ResponseMode = "grounded" | "social";
export type FlashcardSelfRating = "again" | "hard" | "good" | "easy";

export interface ActionCTA {
  action_type: "quiz_cta" | "review_cta" | "research_cta";
  label: string;
  concept_id?: number;
  concept_name?: string;
}

export interface AssessmentCard {
  card_type: "quiz_result" | "practice_result";
  quiz_id?: number;
  concept_id?: number;
  concept_name?: string;
  score: number;
  passed: boolean;
  summary: string;
}

// ── Auth ─────────────────────────────────────────────────────────────

export interface UserPublic {
  public_id: string;
  email: string;
  display_name: string | null;
}

export interface MagicLinkResponse {
  message: string;
  debug_token: string | null;
}

export interface VerifyTokenResponse {
  session_token: string;
  user: UserPublic;
}

export interface TutorProfileResponse {
  readiness_summary: string;
  learning_style_notes: string;
  last_activity_at: string | null;
}

// ── Workspaces ───────────────────────────────────────────────────────

export interface WorkspaceSummary {
  workspace_id: number;
  public_id: string;
  name: string;
  description: string | null;
}

export interface WorkspaceListResponse {
  workspaces: WorkspaceSummary[];
}

export interface WorkspaceDetail extends WorkspaceSummary {
  settings: JsonObject;
}

// ── Knowledge Base ───────────────────────────────────────────────────

export interface KBDocumentSummary {
  document_id: number;
  public_id: string;
  title: string | null;
  source_uri: string | null;
  chunk_count: number;
  ingestion_status: "pending" | "ingested";
  graph_status: "disabled" | "pending" | "extracted";
  graph_concept_count: number;
  created_at: string;
}

export interface KBDocumentListResponse {
  workspace_id: number;
  documents: KBDocumentSummary[];
}

// ── Readiness ────────────────────────────────────────────────────────

export interface ReadinessTopicState {
  concept_id: number;
  concept_name: string;
  readiness_score: number;
  recommend_quiz: boolean;
  last_assessed_at: string | null;
}

export interface ReadinessSnapshotResponse {
  workspace_id: number;
  user_id: number;
  topics: ReadinessTopicState[];
}

// ── Stateful Flashcards ──────────────────────────────────────────────

export interface StatefulFlashcard {
  flashcard_id: string;
  front: string;
  back: string;
  hint: string;
  self_rating: FlashcardSelfRating | null;
  passed: boolean;
}

export interface StatefulFlashcardsResponse {
  workspace_id: number;
  concept_id: number;
  concept_name: string;
  run_id: string;
  flashcards: StatefulFlashcard[];
  has_more: boolean;
  exhausted_reason: string | null;
}

export interface FlashcardRateResponse {
  flashcard_id: string;
  self_rating: FlashcardSelfRating;
  passed: boolean;
}

// ── Research ─────────────────────────────────────────────────────────

export interface ResearchSourceSummary {
  source_id: number;
  url: string;
  label: string | null;
  active: boolean;
}

export interface ResearchRunSummary {
  run_id: number;
  status: "pending" | "running" | "completed" | "failed";
  candidates_found: number;
  started_at: string;
  finished_at: string | null;
}

export interface ResearchCandidateSummary {
  candidate_id: number;
  source_url: string;
  title: string | null;
  snippet: string | null;
  status: "pending" | "approved" | "rejected" | "ingested";
}
