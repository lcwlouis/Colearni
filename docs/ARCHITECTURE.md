# CoLearni Architecture

## Direction

CoLearni is a local-ready, graph-first learning system. It should be architected so SaaS features can be added later as a thin shell, but the MVP must first prove the Trail learning and sharing loop:

```text
Create Trail
-> Learn concept
-> Level-up quiz
-> Graph mastery update
-> Safe Trail Pack export
-> Trail Pack import/fork
-> Optional research trace/hydration
```

The product is not a generic RAG chatbot. The graph and mastery model are first-class data structures, and every source used for retrieval must carry provenance.

Dashboard UX, Learn/Inspect graph modes, source ingestion, retrieval tooling, provider-native tools, and future visualisers exist to improve that Trail experience. They must not weaken or outrank safe Trail Pack sharing/import.

## High-Level System

```text
Frontend
  - Learning dashboard with Continue Learning, Trail progress, and Recommended Next
  - Trail creation UI
  - Graph viewer — React Flow per-Trail view (≤100 nodes) with Learn Mode and Inspect Mode
  - Tutor chat (assistant-ui + custom LocalRuntime adapter)
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
  - Provider tool adapter layer for normalized tool calls/results
  - Source ingestion and controlled retrieval services

Database
  - workspaces
  - trails
  - concept_nodes
  - concept_edges
  - source_records
  - concept_source_links
  - mastery_records
  - quiz_attempts
  - quiz_drafts
  - conversation/session tables

Private Storage
  - uploaded files
  - parsed source revisions
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

quiz_drafts
- id
- concept_id
- quiz_type          (level_up | practice)
- questions_json     (server-owned ungraded card snapshot)
- created_at
- updated_at

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
- role               (user | assistant | tool)
- kind               (visible | tool_call | tool_result)
- content
- reasoning          (optional provider-exposed thinking text for UI rehydration)
- reasoning_parts    (optional ordered status/thinking/tool trace for UI rehydration)
- mode               (socratic | direct | repair | quiz_prompt | explore | free_explore)
- turn_index         (sequential, used for context window management)
- created_at

conversation_summaries
- id
- conversation_id
- summary_text
- turns_covered_to   (turn_index of last turn included in this summary)
- created_at
```

`conversation_summaries` is currently schema-only plumbing. Automatic summary generation is deferred, so prompt context still falls back to recent raw turns unless an older summary row already exists.

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
-> tutor runs one base prompt for Socratic / repair / bounded explore behaviour
-> tutor may request a mastery-gated instruction tool for direct or free_explore mode
-> tutor may emit public `status` / `thinking` / `tool_call` / `tool_result` trace events and persist ordered `reasoning_parts`
-> tutor streams the final response
-> mastery service may update progress after explicit checks
```

Tutor context should be scoped in this order:

1. Current concept.
2. Mastery state.
3. Learner state summary, when available.
4. Prerequisites, containing, contained, and related nodes.
5. Explicitly linked sources.
6. Recent turns or conversation summary.
7. Source chunks only when needed.

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

- Prefer current concept, mastery state, learner state summary, and nearby graph context.
- Use concept-linked source records before broad workspace retrieval.
- Use source chunks only when needed and only through controlled retrieval/open tools.
- Use hybrid vector + full-text search where available.
- Avoid unbounded loops and whole-workspace searches by default.

Planned controlled tools:

- `search_sources(query, concept_id?)`.
- `open_source_chunk(chunk_id)`.
- `get_concept_sources(concept_id)`.
- `get_graph_neighbourhood(concept_id)`.

These tools should be registered through the provider tool abstraction, enforce workspace/Trail/concept/source budgets, and return citation-ready source metadata rather than dumping large source text into every prompt.

## Source Ingestion Pattern

Source ingestion arrives after safe export/import and provider tool foundations. It must create private, provenance-aware source records before retrieval uses uploaded material.

Preferred V1 flow:

```text
Uploaded file
-> private object storage
-> parser
-> markdown-like canonical text
-> source revision
-> chunks
-> embeddings / full-text index
-> concept-source links
-> controlled retrieval/open tools
```

Priority formats are PDF, DOCX, and PPTX. CSV/Excel, arbitrary file types, and broad filesystem browsing are deferred.

Do not use git internally for user source tracking in V1. Use content hashes, parser versions, source revision records, object keys, and database/object-storage versioning. Uploaded files, parsed text, chunks, embeddings, and derived summaries remain private by default and must be excluded by the Trail Pack sanitizer.

## Provider Tool Abstraction

Provider-native tool calling should be supported through a small internal abstraction before retrieval/source tools expand. This is not a full agent framework rewrite.

The abstraction should define:

- Provider-agnostic tool definitions.
- Tool call ids, names, normalized JSON arguments, and validation errors.
- Tool result payloads plus learner-safe public previews.
- Normalized streaming events for `tool_call` and `tool_result`.

Adapters should cover:

- OpenAI Responses API.
- OpenAI-compatible Chat Completions providers, including OpenRouter.
- Anthropic Claude native tool use.

Rules:

- Keep direct provider calls in `LLMClient`; do not introduce LiteLLM.
- Tool execution is service-owned and budgeted.
- Hidden/internal tool turns may be persisted for replay, but public APIs only expose sanitized previews.
- Invalid tool arguments fail safely without unbounded retries.
- The existing tutor SSE stream, reasoning trace UI, and conversation replay behavior must remain compatible.

## LLM Client Pattern

CoLearni makes direct calls to LLM provider APIs via `backend/app/agents/llm_client.py`. **Do not use LiteLLM.** LiteLLM is not a dependency of this project.

### Why direct calls

- Fewer dependencies = smaller attack surface and simpler auditing.
- Explicit, reviewable routing logic with no hidden behaviour.
- The `openai` SDK supports any OpenAI-compatible endpoint via `base_url`, covering OpenAI, OpenRouter, DeepSeek, Gemini, local Ollama, and most hosted alternatives without extra packages.
- Anthropic is supported natively via their SDK (lazy import, only needed when `LLM_PROVIDER=anthropic`).

### Supported providers

| `LLM_PROVIDER` | Routing | Extra install |
|---|---|---|
| `openai` | openai SDK (default endpoint) | — |
| `openrouter` | openai SDK + `base_url` | — |
| `deepseek` | openai SDK + `base_url` | — |
| `gemini` | openai SDK + `base_url` (Google's OAI-compat endpoint) | — |
| `anthropic` | anthropic SDK (native) | `pip install -e ".[providers]"` |
| custom | openai SDK + explicit `LLM_API_BASE` | — |

> **Anthropic runtime note:** The default install supports all OpenAI-compatible providers (`openai`, `openrouter`, `deepseek`, `gemini`, custom). Anthropic requires the `[providers]` optional extra. If `LLM_PROVIDER=anthropic` but the extra is not installed, the server will raise `ImportError` on the first LLM call. Install with: `pip install -e ".[providers]"`.

### Standard pattern for new LLM tasks

Every LLM-using service defines an injectable Protocol and a concrete implementation that wraps `LLMClient`:

```python
# In backend/app/services/my_task.py
from typing import Protocol
from backend.app.agents.llm_client import LLMClient

class MyTaskGenerator(Protocol):
    async def generate(self, **inputs) -> str: ...
    async def repair(self, raw: str, error: str) -> str: ...

class LLMMyTaskGenerator:
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    async def generate(self, **inputs) -> str:
        prompt = load_and_render_prompt("task_name", version=1, variables=inputs)
        return await self._client.chat([{"role": "user", "content": prompt}])

    async def repair(self, raw: str, error: str) -> str:
        repair_prompt = f"Fix this:\nERROR: {error}\nJSON:\n{raw}"
        return await self._client.chat([{"role": "user", "content": repair_prompt}], temperature=0.2)
```

### Factory in routes

```python
# In backend/app/api/my_route.py
from backend.app.agents.llm_client import LLMClient
from backend.app.settings import settings

def get_my_generator() -> MyTaskGenerator:
    return LLMMyTaskGenerator(client=LLMClient.from_settings(settings))
```

### Testing (no LLM needed)

Inject a `FakeGenerator` through FastAPI `dependency_overrides`. Tests never call a real LLM:

```python
class FakeGenerator:
    async def generate(self, **inputs) -> str:
        return VALID_JSON_FIXTURE

    async def repair(self, raw: str, error: str) -> str:
        return REPAIRED_JSON_FIXTURE

app.dependency_overrides[get_my_generator] = lambda: FakeGenerator()
```

### One-repair rule

Generate once. If parsing or validation fails, call `repair()` exactly once. Raise `GenerationError` on the second failure. **No unbounded loops.**

### Configuration

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` | Provider name: `openai`, `openrouter`, `anthropic`, `gemini`, `deepseek` |
| `LLM_MODEL` | Model name for the provider (e.g. `gpt-4o-mini`, `claude-3-5-haiku-20241022`) |
| `LLM_API_KEY` | API key for the provider |
| `LLM_API_BASE` | Optional: override base URL for custom/local endpoints |
| `LLM_THINKING_ENABLED` | Enable extended thinking/reasoning (default: `false`). Gracefully skipped if model doesn't support it. |
| `LLM_THINKING_BUDGET` | Anthropic: `budget_tokens` for extended thinking, min 1024 (default: `8000`) |
| `LLM_THINKING_LEVEL` | OpenAI o-series: `reasoning_effort` — `low`, `medium`, `high` (default: `medium`) |
| `LLM_TUTOR_MAX_TOKENS` | Requested tutor answer budget per call (default: `4096`). Tune this independently from provider reasoning settings. |

## Frontend Graph Library: React Flow

The per-Trail concept graph uses [`@xyflow/react`](https://github.com/xyflow/xyflow) with [`dagre`](https://github.com/dagrejs/dagre) for layout. This is already implemented and is the correct tool for the current use case.

### Why React Flow for per-Trail graphs

- Nodes render as React components, making rich per-node content (title, level badge, difficulty, mastery colour) straightforward.
- `dagre`'s hierarchical layout suits the `umbrella → topic → subtopic → granular` structure better than force-directed physics.
- At 10–100 nodes (the per-Trail cap in `docs/GRAPH.md`) DOM-based rendering is comfortable.

### Known ceiling

React Flow is DOM-based. Pan/zoom triggers style recalculations across all rendered nodes. Interactions become sluggish around **300–500 nodes** and degrade further beyond that. This does not affect per-Trail graphs but matters if a combined or workspace-level view is ever introduced.

### Sigma.js trigger

If any view ever shows nodes from **more than one Trail simultaneously** — a workspace overview, merged Trail, or community graph — React Flow is the wrong tool. Sigma.js should be adopted for that surface (WebGL-based, handles thousands of nodes with smooth pan/zoom). See `docs/CONSIDERED.md` for the full decision record.

Do not pre-emptively migrate the per-Trail graph to Sigma.js.

## Frontend Chat Library: assistant-ui

The tutor chat panel uses [`@assistant-ui/react`](https://github.com/assistant-ui/assistant-ui), an open-source MIT-licensed React/TypeScript library. It is **not** the Vercel AI SDK and introduces no server-side route changes.

### Integration pattern

assistant-ui connects to the FastAPI backend through a `LocalRuntime` model adapter — a single async generator function that calls `POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/chat` and yields token chunks. The library owns all UI state (messages, streaming, auto-scroll, retries). The installed shadcn/ui components live in `apps/web/components/assistant-ui/` and are fully owned by this repo.

### What the library provides

- `Thread`, `Message`, `Composer`, and `ActionBar` primitives.
- Streaming token rendering, auto-scroll, markdown, code highlighting.
- A `Sources` component for inline citation chips.
- Markdown extension points we can use for KaTeX math rendering.

### What CoLearni adds on top

- Tutor mode badge (`socratic`, `direct`, `repair`, `quiz_prompt`, `explore`) on assistant messages.
- Concept context header above the thread (title, concept level).
- Mastery level-up prompt surfaced when the tutor shifts to `quiz_prompt` mode.
- `concept_id` and `workspace_id` injected into every request by the adapter.
- A custom message markdown renderer for LaTeX and fenced `mermaid` diagram blocks.

### Streaming

`POST /api/workspaces/{workspace_id}/trails/{trail_id}/concepts/{concept_id}/chat` should return a streaming SSE response for token-by-token rendering.

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
