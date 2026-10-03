/**
 * Desk v0.4 handoff — retained draft vocabulary — contract version 2.
 * Not a runtime validator, permission system, editor format, or MCP SDK.
 * Actual identity, ownership, grants and revisions are resolved by trusted services.
 * No string sent by a browser/plugin can self-attest that the actor is the learner.
 */
export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };
export type Revision = number; // Runtime: positive integer.
export type Origin = "learner" | "tutor" | "source" | "plugin" | "unknown";
export interface RevisionPointer { objectId: string; revision: Revision }
export interface SourceRef { sourceId: string; sourceRevision: Revision; locator: string; label: string }
export interface Provenance {
  origin: Origin;
  sourceRefs: SourceRef[];
  acceptedByLearnerId?: string;
  derivedFromObjectIds?: string[];
}
/** Minimal fixture block. Production editor payload remains an evaluation gate. */
export interface TextBlock { id: string; text: string; provenance: Provenance }
export interface LearningGoal {
  id: string; deskId: string; capability: string;
  bloomTags: Array<"remember" | "understand" | "apply" | "analyze" | "evaluate" | "create">;
}
export interface LearningDesk {
  id: string; workspaceId: string; title: string; goal: LearningGoal;
  status: "active" | "paused" | "archived";
}
/** Independent document identity: no mandatory single-desk ownership. */
export interface LearnerDocument {
  id: string; workspaceId: string; ownerId: string; revision: Revision;
  kind: "note" | "response" | "annotation";
  title: string; privateOverride: boolean;
  contentSchema: "desk-blocks/0.3-draft";
  blocks: TextBlock[];
  updatedAt: string;
}
/** Referencing a note and granting read access are separate explicit operations. */
export interface DeskDocumentLink {
  deskId: string; documentId: string;
  tutorReadAccess: "shared" | "private";
  placement: "working" | "shelf";
}
export interface PluginRef { id: string; version: string }
export interface NativePluginBinding {
  kind: "native_plugin"; plugin: PluginRef; input: JsonValue; savedState: JsonValue;
}
/** Desk-specific reference shape, not a standard MCP message or self-granted policy. */
export interface McpAppBinding {
  kind: "mcp_app";
  connectionId: string; toolName: string; resourceUri: string;
  resourceDigest?: string;
  protocolVersion: string; // Record the negotiated version, not an assumed latest.
  input: JsonValue;
  integration: "generic" | "desk_learning_profile";
  profileVersion?: string;
  persistence: "fallback_only" | "host_snapshot" | "external_service";
  savedState?: JsonValue;
}
export type CardBody =
  | { kind: "text"; blocks: TextBlock[] }
  | { kind: "document_ref"; documentId: string }
  | { kind: "activity_ref"; activityId: string; activityRevision: Revision }
  | NativePluginBinding | McpAppBinding;
export interface DeskCard {
  id: string; workspaceId: string; deskId: string; revision: Revision;
  contractVersion: "2"; title: string; provenance: Provenance;
  body: CardBody; textFallback: string;
}
export type SemanticTarget = { objectId: string; objectRevision: Revision } & (
  | { kind: "block"; blockId: string }
  | { kind: "step"; stepId: string }
  | { kind: "plot_object"; plotObjectId: string }
  | { kind: "table_cell"; rowId: string; columnId: string }
  | { kind: "code_range"; startLine: number; endLine: number }
);
export interface ActivityDefinition {
  id: string; workspaceId: string; revision: Revision;
  title: string; instructions: TextBlock[];
  responseKind: "rich_text" | "number" | "code";
  provenance: Provenance;
}
export type Assistance = "independent" | "hinted" | "worked_example_visible" | "solution_revealed" | "unknown";
export interface LearnerAttempt {
  id: string; workspaceId: string; deskId: string; learnerId: string;
  activityId: string; activityRevision: Revision;
  responseDocumentId: string; responseRevision: Revision;
  assistance: Assistance;
  status: "draft" | "submitted" | "reviewed";
  createdAt: string;
}
export interface FeedbackRecord {
  id: string; attemptId: string; responseRevision: Revision;
  rubricVersion: string; feedbackBlocks: TextBlock[];
  status: "unreviewed" | "human_reviewed";
}
export interface TeachingPluginDescriptor {
  id: string; version: string; contractVersion: "2";
  runtime: "bundled" | "mcp_app";
  inputSchemaId: string; stateSchemaId: string;
  semanticTargetKinds: Array<SemanticTarget["kind"]>;
  events: string[];
  requestedCapabilities: Array<"emit_semantic_event" | "save_own_state" | "queue_context">;
  assumptions: string[];
  validRanges: Record<string, { min: number; max: number }>;
  // Trusted registry grants/review records live elsewhere, not in this descriptor.
}
export interface PluginHostEvent {
  eventId: string; cardId: string; cardRevision: Revision;
  plugin: PluginRef; event: string; payload: JsonValue;
}
/** Host-validated data envelope, not a raw ui/update-model-context wire message. */
export interface AppContextSnapshot {
  appInstanceId: string; cardId: string; cardRevision: Revision;
  sequence: number; summary: string; structured: JsonValue;
  trust: "untrusted_tool_data";
}
export interface ChangeSet {
  id: string; workspaceId: string; deskId: string;
  actor: "learner" | "tutor" | "plugin";
  description: string; idempotencyKey: string;
  before: RevisionPointer[]; after: RevisionPointer[];
  createdAt: string; reversesChangeSetId?: string;
}
export interface CommandEnvelope<T> {
  commandId: string; deskId: string; idempotencyKey: string;
  expectedRevisions: RevisionPointer[]; action: T;
}
export type TutorAction =
  | { type: "add_support"; title: string; body: CardBody; textFallback: string; sourceRefs: SourceRef[] }
  | { type: "highlight"; target: SemanticTarget }
  | { type: "suggest_link"; fromConceptId: string; toConceptId: string; reason: string; evidence: SemanticTarget[] }
  | { type: "propose_change"; objectId: string; description: string }
  | { type: "request_research"; capabilityGoal: string; minimalBrief: string };
// Deliberately no edit_note, edit_response, set_sharing, install_plugin or self_grade action.
export type LearnerAction =
  | { type: "edit_document"; documentId: string; blocks: TextBlock[] }
  | { type: "set_document_private"; documentId: string; privateOverride: boolean }
  | { type: "link_document"; documentId: string; tutorReadAccess: "shared" | "private" }
  | { type: "request_feedback"; documentId: string; revision: Revision; blockIds: string[] }
  | { type: "save_contribution"; contributionId: string; destinationDocumentId: string }
  | { type: "submit_attempt"; attemptId: string; responseRevision: Revision }
  | { type: "undo_change_set"; changeSetId: string };
export interface SharedNoteIndexEntry {
  documentId: string; revision: Revision; title: string; changedBlockIds: string[];
}
export interface NoteDeltaExcerpt {
  documentId: string; fromRevision: Revision; toRevision: Revision;
  blocks: TextBlock[]; truncated: boolean; trust: "untrusted_task_data";
}
export interface NoteContextPreview {
  deskId: string; index: SharedNoteIndexEntry[]; recentExcerpts: NoteDeltaExcerpt[];
  sizeEstimate: { value: number; unit: "tokens" | "characters"; approximate: boolean };
  remainingNoteReads: number;
}
export type LearningEvidence =
  | { kind: "interaction"; objectId: string; description: string; occurredAt: string }
  | { kind: "attempt"; attemptId: string; assistance: Assistance; occurredAt: string;
      evaluationStatus: "unreviewed" | "reviewed" };
