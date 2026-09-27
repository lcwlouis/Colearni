/**
 * Desk contract vocabulary v0.1 — prototype design seed only.
 * This file contains no renderer, runtime validator, authorisation, or sandbox.
 * A production service derives identity/permissions; client actor labels are untrusted.
 */
export type JsonValue =
  | null | boolean | number | string
  | JsonValue[] | { [key: string]: JsonValue };
export type Origin = "learner" | "tutor" | "source";
export type Revision = number; // Runtime: positive integer.

export interface SourceRef {
  sourceId: string;
  sourceRevision: Revision;
  locator: string;
  label: string;
}

export interface Provenance {
  origin: Origin;
  sourceRefs: SourceRef[];
  /** A saving/accepting learner does not replace the original author. */
  acceptedByLearnerId?: string;
  derivedFromObjectIds?: string[];
}

export interface TextBlock {
  id: string;
  text: string;
  provenance: Provenance;
}

export interface LearningGoal {
  id: string;
  deskId: string;
  capability: string;
  /** Planning labels, not a mastery score or mandatory user vocabulary. */
  bloomTags: Array<"remember" | "understand" | "apply" | "analyze" | "evaluate" | "create">;
}

export interface LearnerNote {
  id: string;
  deskId: string;
  revision: Revision;
  ownerId: string;
  title: string;
  tutorReadAccess: "shared" | "private";
  blocks: TextBlock[];
  updatedAt: string;
}

export interface PluginRef {
  id: string;
  version: string; // Exact installed version, not a semver range.
}

export type CardBody =
  | { kind: "text"; blocks: TextBlock[] }
  | { kind: "plugin"; plugin: PluginRef; input: JsonValue; savedState: JsonValue };

export interface DeskCard {
  id: string;
  deskId: string;
  revision: Revision;
  contractVersion: "1";
  title: string;
  provenance: Provenance;
  body: CardBody;
  textFallback: string;
}

export type SemanticTarget = {
  objectId: string;
  objectRevision: Revision;
} & (
  | { kind: "block"; blockId: string }
  | { kind: "step"; stepId: string }
  | { kind: "plot_object"; plotObjectId: string }
  | { kind: "table_cell"; rowId: string; columnId: string }
  | { kind: "code_range"; startLine: number; endLine: number }
);

export interface BundledPluginDescriptor {
  id: string;
  version: string;
  contractVersion: "1";
  runtime: "bundled";
  inputSchemaId: string;
  stateSchemaId: string;
  semanticTargetKinds: Array<SemanticTarget["kind"]>;
  events: string[];
  capabilities: Array<"emit_semantic_event" | "save_own_state">;
  assumptions: string[];
  validRanges: Record<string, { min: number; max: number }>;
  /** Review state is deliberately absent; only the trusted host may attest it. */
}

/** Not an uploadable plugin module. The host explicitly registers reviewed code. */
export interface PluginHostEvent {
  eventId: string;
  cardId: string;
  cardRevision: Revision;
  plugin: PluginRef;
  event: string; // Runtime: must match descriptor and per-event schema.
  payload: JsonValue;
}

export interface RevisionPointer {
  objectId: string;
  revision: Revision;
}

export interface ChangeSet {
  id: string;
  deskId: string;
  actor: "learner" | "tutor";
  description: string;
  idempotencyKey: string;
  before: RevisionPointer[];
  after: RevisionPointer[];
  createdAt: string;
  reversesChangeSetId?: string;
}

export interface CommandEnvelope<T> {
  commandId: string;
  deskId: string;
  idempotencyKey: string;
  expectedRevisions: RevisionPointer[];
  action: T;
}

export type TutorAction =
  | { type: "add_support"; title: string; body: CardBody; textFallback: string; sourceRefs: SourceRef[] }
  | { type: "highlight"; target: SemanticTarget }
  | { type: "suggest_link"; fromConceptId: string; toConceptId: string; reason: string; evidence: SemanticTarget[] }
  | { type: "propose_change"; objectId: string; description: string };
// No edit_note, set_note_sharing, install_plugin, or arbitrary executable action.
// Runtime still checks data, provenance, engine allowlists, ownership and scope.

export type LearnerAction =
  | { type: "edit_note"; noteId: string; blocks: TextBlock[] }
  | { type: "set_note_sharing"; noteId: string; access: "shared" | "private" }
  | { type: "save_contribution"; contributionId: string; destinationNoteId: string }
  | { type: "undo_change_set"; changeSetId: string };

export interface SharedNoteIndexEntry {
  noteId: string;
  revision: Revision;
  title: string;
  changedBlockIds: string[];
}

export interface NoteDeltaExcerpt {
  noteId: string;
  fromRevision: Revision;
  toRevision: Revision;
  blocks: TextBlock[];
  truncated: boolean;
  trust: "untrusted_task_data";
}

/** Current permissions are checked before assembly and again before model dispatch. */
export interface NoteContextPreview {
  deskId: string;
  index: SharedNoteIndexEntry[];
  recentExcerpts: NoteDeltaExcerpt[];
  sizeEstimate: { value: number; unit: "tokens" | "characters"; approximate: boolean };
  remainingNoteReads: number;
}

export type LearningEvidence =
  | { kind: "interaction"; objectId: string; description: string; occurredAt: string }
  | { kind: "attempt"; activityId: string; responseObjectId: string;
      assistance: "independent" | "hinted" | "worked_example_visible" | "solution_revealed";
      occurredAt: string; evaluationStatus: "unreviewed" | "reviewed" };
// Neither type automatically sets mastery. Assessment quality is a separate decision.
