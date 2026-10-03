# Data model — proposed relational design

PostgreSQL is the accepted primary database. The following is a design sketch, not executable migrations. Scope identifiers, keys and constraints must be implemented and tested before production. Graph relations remain ordinary tables initially.

## Key entities

| Entity | Purpose / suggested fields |
|---|---|
| `workspaces`, `workspace_members` | Ownership and authenticated access; member role is server derived. |
| `desks`, `desk_goals` | Workspace, title, capability, state, goal revisions. |
| `sessions` | Desk, start/end, optional next activity and return summary. |
| `documents` | Workspace, owner, kind (`note`, `response`, `annotation`), current revision, private override. |
| `document_revisions` | Document, revision, versioned content payload, block identities/provenance, author, timestamp. |
| `desk_document_links` | Desk + document, shelf/working placement, explicit tutor-read grant, timestamp. |
| `source_records`, `source_revisions` | Origin, URL, licence/access metadata, immutable bytes/parser version, object key. |
| `source_fragments` | Revision, locator, text, optional embedding; can be regenerated from authorised source. |
| `cards`, `card_revisions` | Desk, renderer binding, title, fallback, provenance, input/state pointers. |
| `activity_definitions`, `activity_revisions` | Versioned tasks/questions and expected response shapes. |
| `attempts` | Activity revision + learner response document + assistance snapshot; explicit submission/evaluation lifecycle. |
| `feedback_records` | Attempt/revision, evaluator, rubric version, findings; separate from the answer. |
| `annotations` | Learner document + source/card/document revision target. |
| `concepts`, `concept_edges` | Workspace concept identity; typed relation; evidence; proposed/confirmed state. |
| `concept_document_links` | Note/source/activity relationships; linking does not grant access. |
| `learning_evidence`, `learner_summaries` | Immutable observations and revisable derived view; no automatic mastery transfer. |
| `plugin_releases`, `mcp_connections` | Exact approved release/connection identity, policy and review state; no credentials in public descriptors. |
| `change_sets`, `object_change_refs` | Atomic operation, actor, idempotency scope, before/after pointers, optional reversal. |
| `checkpoints` | Recovery snapshot manifest of object revisions; not a replay of external actions. |
| `research_jobs`, `research_sources` | Goal, minimal brief, status, budget, provenance and selected evidence. |
| `export_jobs` | Export type, status, manifest, data cutoff, permissions and expiring download. |

## Note identity and sharing

A note has no mandatory single-desk owner. It belongs to a learner/workspace and can be referenced by several desks. Its effective tutor access is the intersection of current workspace access, explicit document privacy, and the current desk link/grant. A global private override wins. Creating a concept link or adding a reference to a new desk does not implicitly grant read access.

A newly created note may use the clearly disclosed current-desk default; a reusable existing note requires an explicit linking/sharing action. Cross-workspace sharing is not an initial implicit feature. Owner access to backups is distinct from tutor access.

## Editor representation

Do not choose canonical Markdown versus editor JSON by accident. The proposed direction is a versioned logical document containing stable blocks and provenance, with a tested Markdown import/export projection. The exact editor representation is an evaluation gate. Required content includes paragraphs, headings, lists, code, tables, math, attributed quotes and links. Unsupported conversions produce a loss report and retain the native backup.

Plain Markdown cannot be claimed to preserve all targets, partial authorship and interactive state. Retain IDs/provenance in the restorable format. Preserve Unicode, mathematical notation, code indentation and accessibility labels.

## Definitions, attempts and feedback

Changing a question creates a new task revision. Existing attempts continue to reference the old revision. Draft answer saves create learner revisions without submitting for assessment. Regenerating a worksheet or worked example does not mutate response documents or annotations. Copied/generated blocks keep origin; saving does not establish independent authorship.

An annotation can become stale when its target changes. Store the original target and show staleness; do not silently attach it to nearby text. A learner may explicitly retarget it.

## Durable interactive state

Record exact engine release, input, model assumptions, random seed when applicable, selected meaningful state, output/fallback and source provenance. A remote tool result is not reproducible just because its UI URL was saved. Treat remote engine availability, licence/access and migrations separately. Cache approved artifacts only where permitted. State restoration must not re-execute side-effecting operations automatically.

## Revision and conflict rules

Use stable object IDs, unique per-object revisions and current pointers. Idempotency keys are scoped to principal/workspace/operation; a reused key with different input fails. Check expected revisions and scope in the mutation transaction. Validate same-workspace relations instead of trusting unqualified foreign keys.

Undo writes a compensating change. If newer learner content or dependent objects make reversal unsafe, return a conflict and preserve work. Do not keep database transactions open during inference or remote tool calls.

## Deletion, retention and recovery

“Immutable history” describes normal audit semantics, not a promise of never deleting private data. Define a retention/purge policy for documents, indexes, cached excerpts, summaries, exports and backups before public use. Permission revocation affects future access immediately but cannot recall provider-bound requests already sent. Record derivative provenance so caches can be invalidated.

## v0.4 graph and decision records

The proposed graph schema adds explicit `concept_level` and `node_type` rather than encoding either in edge labels. Every concept has a declared graph/curriculum scope. Store typed edges separately with relation schema/version, endpoints, origin/evidence and review state. Per-scope level mappings and imported IDs must be reconciled explicitly. See GRAPH_MODEL.md and contracts/graph-contracts.ts before creating a migration; this package has not changed the existing database.

Optional decision traces record task/spec version, authorised context revision references, permission-policy epoch, provider/model/version, candidate-set identity, proposed outcome/abstention, latency/usage and disposition. Do not persist private raw inputs or full provider reasoning by default. These traces are operational diagnostics, not learner assessment. Scope retention/access accordingly. A model selection result never rewrites a note, approved graph edge or learning-evidence record by itself.
