# Architecture proposal

**Accepted:** PostgreSQL and bundled Docker Compose. **Proposed:** Python/FastAPI service organisation, API shapes, MCP host adapter and detailed entity layout. This is a greenfield specification, not an inventory of shipped code.

## Boundaries

```text
React / Vite frontend
  Desk shell + editor + native cards + shelf
  MCP App card adapter (optional, evaluated separately)
                  |
           owned API boundary
                  |
Trusted application services
  identity / scope / permissions / command validation
  notes / activities / revisions / learner evidence
  context assembly / tutor coordinator / bounded researcher
  plugin registry / MCP connection broker / export jobs
         |                    |                    |
    PostgreSQL        private asset storage    approved providers
                                          and MCP servers
```

The learner browser must never hold model credentials, database credentials, an administrator token, or an unrestricted MCP server credential. An MCP iframe has even less authority than the host frontend. A role field in client JSON does not establish authorship.

## Frontend

The host owns identity labels, note editing, provenance, permissions, history and layout. Native cards handle notes, task instructions, response fields, examples and ordinary text. Specialised reviewed plugins handle interactive representations. A candidate MCP Apps adapter hosts permitted HTML apps within a separately enforced isolation boundary; it is not a replacement for the domain model.

Use an in-memory adapter for the first Storybook work. Server state and unsaved editing state have different owners. Keep contracts independent of React, Query, Router, an editor vendor and an MCP SDK.

## Backend services

Keep routes thin. Start with an owned service boundary rather than a distributed agent platform. The tutor chooses teaching moves; the research worker finds scoped evidence; assessment records reviewed evidence; a trusted command service decides what may change. They may share a model/provider client without being autonomous agents.

Model and research operations happen outside database transactions. After a proposal is available, check current permissions and expected revisions again and commit a short atomic change. Long jobs need cancellation, timeouts, budgets, idempotent retries and restart recovery. A separately runnable worker can be added when needed; do not make Redis, Kubernetes or a workflow framework mandatory for the first prototype.

## Suggested service modules

`api/`, `services/notes`, `services/activities`, `services/history`, `services/context`, `services/research`, `services/export`, `agents/`, `models/`, `schemas/`, and `integrations/mcp`. These are proposed responsibilities, not instructions to recreate every folder before a feature has a consumer.

## Data flow: learner note

Local draft → explicit/autosave revision → trusted owner check → document revision and current pointer → coalesced saved-change event → permission-filtered index/deltas → next tutor turn. The note is never stored only in chat history or an iframe. A typing pause does not trigger critique.

## Data flow: interactive tool

Teaching objective → registered tool/plugin selection → validate tool inputs and scope → create/reuse an activity card → load approved renderer → host validates semantic events → save meaningful state through an owned service → later assemble bounded model context. External app state and tool results are observations until validated; they do not update mastery directly.

## Suggested API contracts — draft, not existing endpoints

| Operation | Proposed boundary | Required behaviour |
|---|---|---|
| Create/load desk | `/api/workspaces/{w}/desks` | Verify identity membership; normalise goal. |
| Save note | `/api/workspaces/{w}/notes/{n}/revisions` | Owner-only; expected revision; idempotency key; conflict does not erase draft. |
| Link note to desk | `/api/workspaces/{w}/desks/{d}/notes` | Explicit read-sharing decision; identity persists. |
| Save response | `/api/workspaces/{w}/attempts/{a}/revisions` | Pin task version; retain assistance and authorship. |
| Apply support change | `/api/workspaces/{w}/desks/{d}/commands` | Allowlist command; derive actor; validate scope; group changes. |
| Undo change | `/api/workspaces/{w}/change-sets/{c}/reversals` | Targeted compensation; conflicts preserve newer work. |
| Tutor turn | `/api/workspaces/{w}/desks/{d}/turns` | Scoped context; cancellation; bounded tools; structured action proposals. |
| Research job | `/api/workspaces/{w}/desks/{d}/research-jobs` | Minimal outbound brief; budget; source records; cancel/retry. |
| Export job | `/api/workspaces/{w}/exports` | Distinguish readable/private backup/public share; asset manifest. |
| MCP dispatch | internal broker, not generic browser RPC | Session-bound app identity; registry allowlist; current grants; audited result. |

Do not implement these all during frontend P0/P1. If HTTP is mocked later, document error states such as unauthorised, forbidden, conflict, unsupported and rate-limited. No workspace ID from a route is itself permission.

## Scaling direction

Load a focused concept neighbourhood and relevant document blocks, not the full graph/notebook. Paginate shelves and history, index workspace/desk/object IDs and revisions, and bound payload sizes. Cache immutable source revisions and permitted result fragments with provenance. Recheck permissions before serving caches. Batch embeddings and avoid model calls per keystroke/animation frame. Evaluate concrete bottlenecks before choosing a graph database or a separate search platform.

## What MCP does not replace

Session lifecycle, note ownership, version history, source provenance, evidence evaluation, safe export, provider privacy and secure remote server operation remain application concerns. See MCP_APPS.md for the evaluated protocol boundary.

## v0.4 — optional decisions and explicit graph model

Read [GRAPH_MODEL.md](GRAPH_MODEL.md) before graph persistence/retrieval. Node level is separate from kind, relation, Bloom target and learning evidence. Relations are validated proposals with stable identity, provenance and scope.

[DECISION_LAYER.md](DECISION_LAYER.md) proposes an optional backend adapter behind deterministic policy, not a new mandatory service or autonomous agent swarm. It can classify a current turn or rank authorised candidates after evaluation. It cannot grant permissions, mutate learner work or grade mastery. Explicit learner actions bypass unnecessary inference; unavailable providers fall back only to preconfigured permitted paths. Keep this independent of MCP UI transport. No live provider integration has been built.
