export type BloomLevel =
  | "remember"
  | "understand"
  | "apply"
  | "analyze"
  | "evaluate"
  | "create";
export type ConceptLevel = "umbrella" | "topic" | "subtopic" | "granular";
export type Difficulty = "beginner" | "intermediate" | "advanced";
export type NodeType = "concept" | "skill" | "misconception" | "example";
export type RelationType =
  | "prerequisite"
  | "contains"
  | "application"
  | "related";
export type MasteryStatus =
  | "not_started"
  | "learning"
  | "needs_review"
  | "mastered";
export type TutorMode =
  | "socratic"
  | "direct"
  | "repair"
  | "quiz_prompt"
  | "explore"
  | "free_explore";
export type SourceOrigin =
  | "research_agent"
  | "user_upload"
  | "manual"
  | "system";
export type SourceAccess = "public" | "private" | "restricted" | "unknown";
export type SourceRevisionStatus =
  | "pending_parse"
  | "parsed"
  | "failed"
  | "skipped";

export interface Workspace {
  id: string;
  name: string;
  created_at: string;
}

export interface Trail {
  id: string;
  workspace_id: string;
  title: string;
  topic: string;
  goal: string;
  target_depth: BloomLevel;
  prior_knowledge?: string | null;
  created_at: string;
  node_count: number;
  edge_count: number;
}

export interface ConceptNode {
  id: string;
  trail_id: string;
  slug: string;
  title: string;
  node_type: NodeType;
  concept_level: ConceptLevel;
  difficulty: Difficulty;
  bloom_level: BloomLevel;
  mastery_check_labels: string[];
  metadata_json: Record<string, unknown>;
}

export interface ConceptEdge {
  id: string;
  trail_id: string;
  source_node_id: string;
  target_node_id: string;
  relation_type: RelationType;
}

export interface TrailGraph {
  nodes: ConceptNode[];
  edges: ConceptEdge[];
  mastery: Record<string, MasteryRecord>;
}

export interface MasteryRecord {
  id: string | null;
  workspace_id: string;
  concept_id: string;
  status: MasteryStatus;
  bloom_level: BloomLevel;
  score: number;
  updated_at: string | null;
}

export interface MasterySummary {
  total: number;
  not_started: number;
  learning: number;
  needs_review: number;
  mastered: number;
}

export interface TrailDetail {
  trail: Trail;
  graph: TrailGraph;
  mastery_summary: MasterySummary;
}

export interface NextConceptResponse {
  concept_id: string | null;
  concept_title: string | null;
  reason: string;
  all_mastered: boolean;
  mastery_status: MasteryStatus | null;
  concept_level: ConceptLevel | null;
}

export interface ConceptPrimerKeyTerm {
  term: string;
  definition: string;
}

export interface ConceptPrimerRead {
  overview: string;
  key_terms: ConceptPrimerKeyTerm[];
  // Suggested opening questions for the tutor welcome screen. May be empty for
  // older cached primers generated before this field existed.
  sample_questions: string[];
  version: number;
}

export type ConceptPrimer = ConceptPrimerRead;

export interface ConceptDetail {
  concept: ConceptNode;
  prerequisites: ConceptNode[];
  contained_nodes: ConceptNode[];
  containing_nodes: ConceptNode[];
  related: ConceptNode[];
  mastery: MasteryRecord;
  sources: SourceRecord[];
  primer?: ConceptPrimerRead | null;
}

export interface QuizQuestion {
  id: string;
  type:
    | "multiple_choice"
    | "multi_select"
    | "ordering"
    | "cloze"
    | "short_answer"
    | "long_answer"
    | "code";
  prompt: string;
  mastery_label: string;
  difficulty?: "light" | "standard" | "challenge";
  options?: string[] | null;
}

export interface QuizAnswer {
  question_id: string;
  answer: string;
}

export interface LevelUpCard {
  concept_id: string;
  quiz_type: "level_up" | "practice";
  questions: QuizQuestion[];
}

export interface PerQuestionEvaluation {
  question_id: string;
  score: number;
  feedback: string;
}

export interface GradeResult {
  passed: boolean;
  score: number;
  feedback: string;
  per_question?: PerQuestionEvaluation[];
  mastery_status: MasteryStatus;
  attempt_id: string;
}

export interface QuizAttempt {
  id: string;
  concept_id: string;
  quiz_type: "level_up" | "practice";
  questions: QuizQuestion[];
  answers: QuizAnswer[];
  evaluator_feedback: string;
  passed: boolean;
  score: number;
  created_at: string;
}

export interface QuizAttemptListResponse {
  attempts: QuizAttempt[];
}

export interface SourceRecord {
  id: string;
  workspace_id: string;
  title: string;
  url: string | null;
  origin: SourceOrigin;
  access: SourceAccess;
  license: string | null;
  include_on_public_export: boolean;
  metadata_json: Record<string, unknown>;
  relation?: string;
}

export interface SourceRevisionSummary {
  id: string;
  workspace_id: string;
  source_id: string;
  revision_number: number;
  content_type: string | null;
  file_size_bytes: number;
  parser_name: string;
  parser_version: string;
  status: SourceRevisionStatus;
  error_message: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface SourceUploadResponse extends SourceRecord {
  revision: SourceRevisionSummary;
}

export interface ConceptSourceLinkRead {
  id: string;
  source_id: string;
  concept_id: string;
  relation: string;
}

export interface ConceptSourceListItem {
  source_id: string;
  title: string;
  origin: SourceOrigin;
  access: SourceAccess;
  url: string | null;
  relation: string;
  ingestion_status: SourceRevisionStatus | null;
}

export interface TutorChatRequest {
  message: string;
  conversation_id: string | null;
  regenerate?: boolean;
  replace_latest_user?: boolean;
}

export interface QuizGenerateRequest {
  force_new?: boolean;
}

export type TutorStreamStatus =
  | "selecting_mode"
  | "thinking"
  | "calling_tool"
  | "tool_called"
  | "tool_complete"
  | "responding"
  | "retrying_without_thinking";

export interface TutorToolEvent {
  name: string;
  mode: TutorMode | null;
  query?: string;
  result?: string;
}

export interface ConversationReasoningPart {
  kind: "status" | "thinking" | "tool_call" | "tool_result";
  status?: TutorStreamStatus | null;
  text?: string | null;
  name?: string | null;
  mode?: TutorMode | null;
  query?: string | null;
  result?: string | null;
}

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  reasoning: string | null;
  reasoning_parts?: ConversationReasoningPart[];
  mode: TutorMode | null;
  created_at: string;
}

export interface ConversationHistoryResponse {
  conversation_id: string | null;
  messages: ConversationMessage[];
}

export interface TrailGenerateRequest {
  topic: string;
  goal: string;
  target_depth: BloomLevel;
  max_nodes: number;
  prior_knowledge?: string | null;
}

export interface TrailGenerateResponse {
  trail: Trail;
  graph: TrailGraph;
}
