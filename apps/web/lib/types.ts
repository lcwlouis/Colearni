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
export type RelationType = "prerequisite" | "contains" | "application" | "related";
export type MasteryStatus = "not_started" | "learning" | "needs_review" | "mastered";
export type TutorMode = "socratic" | "direct" | "repair" | "quiz_prompt" | "explore";
export type SourceOrigin = "research_agent" | "user_upload" | "manual" | "system";
export type SourceAccess = "public" | "private" | "restricted" | "unknown";

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

export interface ConceptDetail {
  concept: ConceptNode;
  prerequisites: ConceptNode[];
  contained_nodes: ConceptNode[];
  containing_nodes: ConceptNode[];
  related: ConceptNode[];
  mastery: MasteryRecord;
  sources: SourceRecord[];
}

export interface QuizQuestion {
  id: string;
  type: "explain" | "apply" | "compare";
  prompt: string;
  mastery_label: string;
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

export interface GradeResult {
  passed: boolean;
  score: number;
  feedback: string;
  mastery_status: MasteryStatus;
  attempt_id: string;
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

export interface TutorChatRequest {
  message: string;
  conversation_id: string | null;
}

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  reasoning: string | null;
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
}

export interface TrailGenerateResponse {
  trail: Trail;
  graph: TrailGraph;
}
