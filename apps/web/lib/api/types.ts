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

export interface AnswerParts {
  body: string;
  hint: string | null;
}

export interface AssistantResponseEnvelope {
  kind: "answer" | "refusal";
  text: string;
  grounding_mode: GroundingMode;
  evidence: EvidenceItem[];
  citations: Citation[];
  refusal_reason: RefusalReason | null;
  conversation_meta: ConversationMeta | null;
  response_mode?: "grounded" | "social" | "clarify" | "onboarding";
  actions?: ActionCTA[];
  generation_trace?: GenerationTrace | null;
  answer_parts?: AnswerParts | null;
}

export interface ChatRespondRequest {
  query: string;
  session_id?: string;
  concept_id?: number;
  suggested_concept_id?: number;
  concept_switch_decision?: ConceptSwitchDecision;
  top_k?: number;
  grounding_mode?: GroundingMode;
}

export type ChatMessageType = "user" | "assistant" | "system" | "tool" | "card";

export interface ChatSessionSummary {
  session_id: number;
  public_id: string;
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

export interface PracticeQuizAttemptSummary {
  attempt_id: number;
  score: number;
  passed: boolean;
  critical_misconception: boolean;
  overall_feedback: string;
  graded_at: string;
}

export interface PracticeQuizHistoryEntry {
  quiz_id: number;
  workspace_id: number;
  user_id: number;
  concept_id: number | null;
  concept_name: string | null;
  status: string;
  item_count: number;
  created_at: string;
  latest_attempt: PracticeQuizAttemptSummary | null;
}

export interface PracticeQuizHistoryListResponse {
  workspace_id: number;
  user_id: number;
  concept_id: number | null;
  quizzes: PracticeQuizHistoryEntry[];
}

export interface PracticeQuizDetailResponse extends PracticeQuizHistoryEntry {
  items: QuizItemSummary[];
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

export interface FlashcardRunSummary {
  run_id: string;
  workspace_id: number;
  user_id: number;
  concept_id: number;
  concept_name: string;
  item_count: number;
  has_more: boolean;
  exhausted_reason: string | null;
  created_at: string;
}

export interface FlashcardRunListResponse {
  workspace_id: number;
  user_id: number;
  concept_id: number | null;
  runs: FlashcardRunSummary[];
}

export interface FlashcardRunDetailResponse {
  run_id: string;
  workspace_id: number;
  user_id: number;
  concept_id: number;
  concept_name: string;
  item_count: number;
  has_more: boolean;
  exhausted_reason: string | null;
  created_at: string;
  flashcards: StatefulFlashcard[];
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
  is_truncated?: boolean;
  total_concept_count?: number;
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
  session_id?: string;
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
  session_id?: string;
  question_count?: number;
}

export interface SubmitQuizRequest {
  answers: QuizSubmitAnswer[];
}

// ── WOW Release Types ──────────────────────────────────────────────

export type ResponseMode = "grounded" | "social" | "clarify" | "onboarding";
export type FlashcardSelfRating = "again" | "hard" | "good" | "easy";

export interface ActionCTA {
  action_type: "quiz_cta" | "review_cta" | "research_cta" | "quiz_offer" | "quiz_start";
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
  summary: string | null;
  source_uri: string | null;
  chunk_count: number;
  ingestion_status: "pending" | "ingested";
  graph_status: "disabled" | "pending" | "extracting" | "extracted" | "failed";
  graph_concept_count: number;
  created_at: string;
  error_message: string | null;
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

// ── Concept Activity (AR7.1) ────────────────────────────────────────

export interface ConceptActivityQuiz {
  quiz_id: number;
  title: string;
  latest_score: number | null;
  passed: boolean | null;
  graded_at: string | null;
  can_retry: boolean;
  critical_misconception?: string | null;
  can_promote?: boolean;
}

export interface ConceptActivityFlashcardRun {
  run_id: string;
  item_count: number;
  has_more: boolean;
  exhausted: boolean;
  created_at: string | null;
  can_open: boolean;
}

export interface ConceptActivityResponse {
  workspace_id: number;
  user_id: number;
  concept_id: number;
  practice_quizzes: {
    count: number;
    average_score: number | null;
    quizzes: ConceptActivityQuiz[];
  };
  level_up_quizzes: {
    count: number;
    passed_count: number;
    quizzes: ConceptActivityQuiz[];
  };
  flashcard_runs: {
    count: number;
    total_cards_generated: number;
    runs: ConceptActivityFlashcardRun[];
  };
  affordances: {
    can_generate_flashcards: boolean;
    can_create_practice_quiz: boolean;
    can_create_level_up_quiz: boolean;
    has_prior_flashcards: boolean;
    has_prior_practice: boolean;
    has_prior_level_up: boolean;
  };
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

// ── Onboarding ──────────────────────────────────────────────────────

export interface OnboardingSuggestedTopic {
  concept_id: number;
  canonical_name: string;
  description: string | null;
  degree: number;
}

export interface OnboardingStatusResponse {
  has_documents: boolean;
  has_active_concepts: boolean;
  suggested_topics: OnboardingSuggestedTopic[];
}

// ── Generation Trace & Stream Events (G0) ────────────────────────────

export interface GenerationTrace {
  provider: string | null;
  model: string | null;
  timing_ms: number | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  /** Provider-reported reasoning tokens — may be non-zero even when reasoning was not explicitly requested. */
  reasoning_tokens: number | null;
  /** Whether the app explicitly requested reasoning params. */
  reasoning_requested: boolean | null;
  reasoning_supported: boolean | null;
  /** Whether explicit reasoning params were actually sent to the provider. */
  reasoning_used: boolean | null;
  /** Effort level requested: "low" | "medium" | "high" | null. */
  reasoning_effort: string | null;
  /** Where the effort value came from: "settings" | "override" | null. */
  reasoning_effort_source: string | null;
  /** Turn planner trace (AR1.4) */
  plan_intent: string | null;
  plan_strategy: string | null;
  plan_needs_retrieval: boolean | null;
  plan_concept_hint: string | null;
  plan_should_offer_quiz: boolean | null;
  plan_should_start_quiz: boolean | null;
  /** Evidence planner trace (AR2) */
  evidence_plan_stop_reason: string | null;
  evidence_plan_budget: number | null;
  evidence_plan_chunk_count: number | null;
  evidence_plan_passes: number | null;
  evidence_plan_retrieved_count: number | null;
  evidence_plan_used_count: number | null;
  evidence_plan_provenance_chunks: number | null;
  evidence_plan_doc_summary_ids: number | null;
  evidence_plan_graph_concepts_used: number | null;
  /** Learner profile trace (AR4.4) */
  learner_weak_topic_count: number | null;
  learner_strong_topic_count: number | null;
  learner_frontier_count: number | null;
  learner_review_count: number | null;
  learner_profile_summary: string | null;
  /** Background observability trace (AR6.3) */
  bg_digest_available: boolean | null;
  bg_frontier_suggestion_count: number | null;
  bg_research_candidate_pending: number | null;
  bg_research_candidate_approved: number | null;
}

export type StreamChatPhase =
  | "thinking"
  | "searching"
  | "responding"
  | "finalizing";

export type TutorActivity =
  | "planning_turn"
  | "retrieving_chunks"
  | "expanding_graph"
  | "checking_mastery"
  | "preparing_quiz"
  | "grading_quiz"
  | "verifying_citations"
  | "generating_reply";

export interface ChatStreamStatusEvent {
  event: "status";
  phase: StreamChatPhase;
  activity?: TutorActivity | null;
  step_label?: string | null;
}

export interface ChatStreamDeltaEvent {
  event: "delta";
  text: string;
}

export interface ChatStreamTraceEvent {
  event: "trace";
  trace: GenerationTrace;
}

export interface ChatStreamFinalEvent {
  event: "final";
  envelope: AssistantResponseEnvelope;
}

export interface ChatStreamErrorEvent {
  event: "error";
  message: string;
  phase: StreamChatPhase | null;
}

/** Ephemeral reasoning summary — stream-only, never persisted. */
export interface ChatStreamReasoningSummaryEvent {
  event: "reasoning_summary";
  summary: string;
}

/** Structured answer-parts event replacing frontend regex-based hint extraction. */
export interface ChatStreamAnswerPartEvent {
  event: "answer_parts";
  parts: AnswerParts;
}

export type ChatStreamEvent =
  | ChatStreamStatusEvent
  | ChatStreamDeltaEvent
  | ChatStreamTraceEvent
  | ChatStreamFinalEvent
  | ChatStreamErrorEvent
  | ChatStreamReasoningSummaryEvent
  | ChatStreamAnswerPartEvent;
