# CoLearni Architecture

## Direction

CoLearni is a local-ready, graph-first learning system. It should be architected so SaaS features can be added later as a thin shell, but the MVP must first prove the learning loop:

```text
Trail -> concept graph -> Socratic tutor -> mastery check -> safe Trail Pack sharing
```

The product is not a generic RAG chatbot. The graph and mastery model are first-class data structures, and every source used for retrieval must carry provenance.

## High-Level System

```text
Frontend
  - Trail creation UI
  - Graph viewer
  - Tutor chat
  - Level-up quiz cards
  - Import/export UI

Backend API
  - Trail service
  - Graph service
  - Tutor service
  - Mastery service
  - Source provenance service
  - Research service
  - Hydration service
  - Trail Pack import/export service

Database
  - workspaces
  - trails
  - concept_nodes
  - concept_edges
  - source_records
  - concept_source_links
  - mastery_records
  - quiz_attempts
  - conversation/session tables

Private Storage
  - uploaded files
  - hydrated source text
  - chunks
  - embeddings

Public Trail Pack
  - manifest.yaml
  - graph.yaml
  - concepts/
  - sources.yaml
  - research_trace.yaml
```

## Layer Boundaries

FastAPI routes stay thin. Routes validate request data, call a service, and return a response. Business logic belongs in service modules.

Backend layout:

```text
backend/
  app/
    api/        # HTTP routes and FastAPI dependencies only
    services/   # Trail, tutor, mastery, source, research, export/import logic
    agents/     # LLM orchestration, prompt rendering (uses PromptRegistry)
      prompts/  # Versioned Markdown prompt files (see docs/PROMPTS.md)
    models/     # SQLAlchemy ORM models
    schemas/    # Pydantic request/response models
  alembic/      # DB migrations
  tests/        # pytest tests
```

Do not put business logic in `api/`. Do not inline LLM prompt strings in `agents/` or `services/` — use the prompt registry in `agents/prompts/`.

## Workspace Scoping

For the local-ready MVP, there is no auth. Workspace id is passed in the URL path of every API call. A default workspace is auto-created on first backend startup if none exists. The workspace id should be stored client-side (e.g. localStorage or a config file) and included in all requests.

This design keeps the API SaaS-compatible: adding auth later is a matter of binding workspace access to user identity, not changing the URL structure.

## Public vs Private Layers

Separate these layers strictly:

```text
Public Shareable Layer
- Trail Pack
- graph structure
- source links
- research trace
- learning objectives
- abstract mastery checks

Private Workspace Layer
- uploaded files
- chunks
- embeddings
- generated summaries
- generated quizzes
- notes
- chat history
- mastery records
```

Public sharing shares learning structure, not source-derived content.

## Core Data Model

```sql
workspaces
- id
- name
- created_at

trails
- id
- workspace_id
- title
- topic
- goal
- target_depth
- created_at

concept_nodes
- id
- trail_id
- slug
- title
- node_type
- concept_level
- difficulty
- bloom_level
- metadata_json

concept_edges
- id
- trail_id
- source_node_id
- target_node_id
- relation_type

source_records
- id
- workspace_id
- origin
- access
- title
- url
- license
- include_on_public_export
- metadata_json

concept_source_links
- id
- concept_id
- source_id
- relation

mastery_records
- id
- workspace_id
- concept_id
- status
- bloom_level
- score
- updated_at

quiz_attempts
- id
- concept_id
- quiz_type          (level_up | practice)
- questions_json     (snapshot of the card at time of attempt)
- answers_json       (user answers keyed by question_id)
- evaluator_feedback
- passed
- score              (0.0–1.0)
- created_at

conversations
- id
- workspace_id
- trail_id
- concept_id
- created_at
- updated_at

conversation_turns
- id
- conversation_id
- role               (user | assistant)
- content
- mode               (socratic | direct | repair | quiz_prompt | explore)
- turn_index         (sequential, used for context window management)
- created_at

conversation_summaries
- id
- conversation_id
- summary_text
- turns_covered_to   (turn_index of last turn included in this summary)
- created_at
```

`concept_level` is required and must be one of:

```text
umbrella
topic
subtopic
granular
```

This level is an intrinsic node attribute. Parent/child or `contains` edges can connect levels, but they do not replace the level field.

## Trail Generation Flow

```text
User enters topic/goal
-> backend calls graph generator
-> graph JSON is validated
-> nodes/edges are stored
-> frontend renders graph
```

Validation must enforce node schema, concept level values, edge schema, duplicate slug handling, graph size caps, and prerequisite cycle rules.

## Tutor Flow

```text
User selects concept
-> backend loads concept, nearby graph context, mastery state, safe sources
-> tutor chooses mode
-> tutor responds Socratically
-> mastery service may update progress after explicit checks
```

Tutor context should be scoped in this order:

1. Current concept.
2. Prerequisites.
3. Containing nodes and contained child nodes.
4. Current Trail.
5. Explicitly linked sources.
6. Broader workspace only when needed.

The tutor must not search the entire graph by default.

## Export Flow

```text
User exports Trail
-> export sanitizer checks provenance
-> private/uploaded/source-derived content is stripped
-> public Trail Pack is generated
-> export report shows included/excluded data
```

The export sanitizer is a safety boundary, not a UI convenience. Export tests must prove that private workspace content cannot enter a public Trail Pack.

## Import/Hydration Flow

```text
User imports Trail Pack
-> manifest is validated
-> graph is imported into workspace
-> source manifest is shown
-> user may hydrate from public/user-provided sources
-> hydrated content stays private
```

Hydration enriches local learning, but hydrated content remains private unless later provenance and licensing checks explicitly allow export.

## Retrieval and Evidence

CoLearni should remain evidence-first. User-visible sourced answers must either include citations to allowed evidence or refuse in strict grounded mode.

Retrieval should stay scoped and budgeted:

- Prefer current concept and nearby graph context.
- Use Trail-linked source records before broad workspace retrieval.
- Use hybrid vector + full-text search where available.
- Avoid unbounded loops and whole-workspace searches by default.

## Local-Ready First, SaaS Later

Local-ready core:

```text
single-user or simple-user
Docker Compose
local Postgres
local workspace storage
local Trail Pack import/export
LLM provider configured by env
```

SaaS layer later:

```text
auth
multi-user workspaces
object storage
billing
rate limits
public Trail registry
moderation
abuse prevention
organization/school accounts
```
