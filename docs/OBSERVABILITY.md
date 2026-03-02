# docs/OBSERVABILITY.md

Local observability for Colearni uses **Arize Phoenix** as an OTLP collector + trace viewer.
All tracing is **opt-in** — the app runs identically when Phoenix is not present.

Traces use **OpenInference semantic conventions** so Phoenix can display rich LLM-specific
details (input/output messages, token counts, span hierarchies, span kind icons).

---

## Quick Start

```bash
# 1. Start Phoenix (Docker Compose profile keeps it separate from default startup)
docker compose --profile observability up -d phoenix
# shortcut: make phoenix

# 2. Set env vars (add to .env or export in shell)
APP_OBSERVABILITY_ENABLED=true
APP_OBSERVABILITY_OTLP_ENDPOINT=http://localhost:6006

# 3. Start the app
make dev

# 4. Open Phoenix UI
open http://localhost:6006

# 5. Generate some traces
curl http://localhost:8000/api/healthz
```

To tear down Phoenix:

```bash
docker compose --profile observability down
# shortcut: make phoenix-down
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `APP_OBSERVABILITY_ENABLED` | `false` | Master toggle. When `false`, all `emit_event` and `start_span` calls are no-ops. |
| `APP_OBSERVABILITY_OTLP_ENDPOINT` | *(empty)* | OTLP HTTP receiver base URL. Set to `http://localhost:6006` for local Phoenix. `/v1/traces` is appended automatically. |
| `APP_OBSERVABILITY_SERVICE_NAME` | `colearni-backend` | Value of the `service.name` OTel resource attribute. |
| `APP_OBSERVABILITY_RECORD_CONTENT` | `true` | When `true`, full LLM input/output messages are recorded on spans. When `false`, only preview (first 256 chars) and length are recorded — token counts and metadata are always present. |

---

## What Is Traced

### Span Hierarchy

AI-relevant traces are exported to Phoenix. Generic HTTP/CRUD endpoints
(healthz, session listing, etc.) do **not** create Phoenix spans — request
correlation stays in structured logs via `observation_context`.

```
chat.respond (CHAIN)                            ← blocking chat orchestrator
  ├─ retrieval.hybrid (RETRIEVER)               ← hybrid retrieval root
  │    ├─ retrieval.vector.search (RETRIEVER)   ← pgvector cosine search
  │    ├─ retrieval.fts.search (RETRIEVER)      ← Postgres FTS search
  │    └─ retrieval.hybrid.fuse (CHAIN)         ← RRF weighted fusion
  ├─ retrieval.graph.bias (RETRIEVER)           ← concept-based reranking
  └─ llm.chat.respond (LLM)                    ← LLM adapter call

chat.stream (CHAIN)                             ← streaming chat orchestrator
  ├─ retrieval.hybrid (RETRIEVER)
  │    ├─ retrieval.vector.search (RETRIEVER)
  │    ├─ retrieval.fts.search (RETRIEVER)
  │    └─ retrieval.hybrid.fuse (CHAIN)
  ├─ retrieval.graph.bias (RETRIEVER)
  └─ llm.chat.respond (LLM)
```

Background tasks create their own root spans:

```
ingestion.post_ingest (CHAIN)           ← post-ingest background task
  ├─ llm.graph.extract (LLM)
  └─ graph.resolver.run (CHAIN)
       └─ graph.resolver.chunk (CHAIN)

graph.gardener.run (CHAIN)              ← offline graph consolidation
  └─ llm.graph.disambiguate (LLM)
```

### Spans (`start_span` / `create_span`)

| Span Name | Kind | Source |
|---|---|---|
| `chat.respond` | CHAIN | `domain/chat/respond.py` |
| `chat.stream` | CHAIN | `domain/chat/stream.py` |
| `retrieval.hybrid` | RETRIEVER | `domain/chat/retrieval_context.py` |
| `retrieval.vector.search` | RETRIEVER | `domain/retrieval/vector_retriever.py` |
| `retrieval.fts.search` | RETRIEVER | `domain/retrieval/fts_retriever.py` |
| `retrieval.hybrid.fuse` | CHAIN | `domain/retrieval/hybrid_retriever.py` |
| `retrieval.graph.bias` | RETRIEVER | `domain/chat/retrieval_context.py` |
| `ingestion.post_ingest` | CHAIN | `domain/ingestion/post_ingest.py` |
| `practice.flashcards.generate` | CHAIN | `domain/learning/practice.py` |
| `practice.flashcards.generate_stateful` | CHAIN | `domain/learning/practice.py` |
| `practice.quiz.generate` | CHAIN | `domain/learning/practice.py` |
| `graph.resolver.run` | CHAIN | `domain/graph/pipeline.py` |
| `graph.resolver.chunk` | CHAIN | `domain/graph/pipeline.py` |
| `graph.gardener.run` | CHAIN | `domain/graph/gardener.py` |
| `grading.level_up` | CHAIN | `domain/learning/quiz_flow.py` |
| `grading.practice` | CHAIN | `domain/learning/quiz_flow.py` |
| `llm.chat.respond` | LLM | `adapters/llm/providers.py` |
| `llm.chat.stream` | LLM | `adapters/llm/providers.py` |
| `llm.chat.social` | LLM | `adapters/llm/providers.py` |
| `llm.graph.extract` | LLM | `adapters/llm/providers.py` |
| `llm.graph.disambiguate` | LLM | `adapters/llm/providers.py` |
| `llm.practice.flashcards.generate` | LLM | `adapters/llm/providers.py` |
| `llm.practice.flashcards.generate_stateful` | LLM | `adapters/llm/providers.py` |
| `llm.practice.quiz.generate` | LLM | `adapters/llm/providers.py` |
| `llm.grading.level_up.submit` | LLM | `adapters/llm/providers.py` |
| `llm.grading.practice.submit` | LLM | `adapters/llm/providers.py` |

> **AI-only export**: The OTLP exporter is wrapped in `_AIOnlySpanExporter` which
> silently drops any span that lacks an `openinference.span.kind` attribute.  This
> prevents generic HTTP, database, or middleware spans from polluting Phoenix even if
> an instrumentation library adds them automatically.

> **Note on `create_span`**: The streaming path uses `create_span()` instead
> of `start_span()` because Python generators cannot use context managers that
> cross async boundaries (Starlette runs sync generators in a thread pool).

### OpenInference Attributes on LLM Spans

| Attribute | Description |
|---|---|
| `openinference.span.kind` | `LLM` — displays LLM icon in Phoenix |
| `llm.model_name` | Model used (e.g. `gpt-4.1-mini`) |
| `llm.input_messages` | JSON array of messages sent to the API (when content recording is on) |
| `llm.output_messages` | JSON array of assistant response (when content recording is on) |
| `llm.invocation_parameters` | JSON of model params (temperature, etc.) |
| `llm.token_count.prompt` | Input token count |
| `llm.token_count.completion` | Output token count |
| `llm.token_count.total` | Total token count |
| `llm.token_count.cached` | Cached prompt tokens (prefix caching); null when provider does not report |
| `llm.usage_source` | `provider_reported`, `estimated`, or `missing` |

### Content Capture Policy

| Condition | What is recorded |
|---|---|
| Always | Preview (first 256 chars), message length, token counts |
| Always (metadata spans) | `input.value` / `output.value` with compact non-sensitive summaries via `set_span_summary` |
| `APP_OBSERVABILITY_RECORD_CONTENT=true` | Full message bodies on LLM spans; full query/response text on chat spans |
| `APP_OBSERVABILITY_RECORD_CONTENT=false` | Preview and length only, no full bodies |

> **`set_span_summary` vs `set_input_output`**: Domain chain spans (graph, practice, grading,
> ingestion) use `set_span_summary()` to unconditionally populate Phoenix list view columns
> with compact metadata (e.g. `"concept=Python, 5 flashcards"`).  Chat spans that carry actual
> user queries use `set_input_output()` which is gated by `APP_OBSERVABILITY_RECORD_CONTENT`.

### Prompt Metadata on LLM Spans

When a prompt is rendered via `render_with_meta()`, these attributes are set:

| Attribute | Description |
|---|---|
| `prompt.id` | Prompt asset identifier (e.g. `tutor_chat_respond_v1`) |
| `prompt.version` | Prompt version number |
| `prompt.task_type` | Task family (e.g. `chat`, `graph`, `practice`) |
| `prompt.rendered_length` | Length of the rendered prompt in characters |

### Correlation Fields on Domain Spans

| Attribute | Available on |
|---|---|
| `session.id` | `chat.respond`, `chat.stream` |
| `user.id` | `chat.respond`, `chat.stream`, `grading.*` |
| `concept.id` | `chat.respond`, `chat.stream`, practice spans |
| `workspace_id` | All domain spans |
| `document_id` | `ingestion.post_ingest` |
| `quiz_id` | `grading.level_up`, `grading.practice` |
| `run_id` | `graph.resolver.run`, `graph.gardener.run`, `grading.*` |

### OpenInference Attributes on Domain Spans

| Attribute | Description |
|---|---|
| `openinference.span.kind` | `CHAIN`, `RETRIEVER` |
| `input.value` | User query or input summary |
| `output.value` | Response text or JSON summary |

### Retrieval Span Attributes

**Parent span (`retrieval.hybrid`)**:

| Attribute | Description |
|---|---|
| `retrieval.query` | Query text (first 256 chars) |
| `retrieval.top_k` | Requested result count |
| `retrieval.results_count` | Actual results returned |
| `retrieval.documents` | JSON summary of top 5 results: `[{rank, chunk_id, document_id, score, method, ?preview}]` |

**Vector stage (`retrieval.vector.search`)**:

| Attribute | Description |
|---|---|
| `retrieval.top_k` | Bounded top-k for vector search |
| `retrieval.results_count` | Vector hits returned |
| `retrieval.documents` | JSON summary of top 5 vector results: `[{rank, chunk_id, document_id, score, ?preview}]` |

**FTS stage (`retrieval.fts.search`)**:

| Attribute | Description |
|---|---|
| `retrieval.top_k` | Bounded top-k for FTS search |
| `retrieval.results_count` | FTS hits returned |
| `retrieval.documents` | JSON summary of top 5 FTS results: `[{rank, chunk_id, document_id, score, ?preview}]` |

**Fusion stage (`retrieval.hybrid.fuse`)**:

| Attribute | Description |
|---|---|
| `retrieval.vector_count` | Number of vector candidates |
| `retrieval.fts_count` | Number of FTS candidates |
| `retrieval.rrf_k` | RRF parameter used |
| `retrieval.vector_weight` | Weight applied to vector scores |
| `retrieval.fts_weight` | Weight applied to FTS scores |
| `retrieval.results_count` | Final fused result count |
| `retrieval.method_distribution` | JSON count of vector/fts/hybrid methods |
| `retrieval.documents` | JSON summary of top 5 fused results: `[{rank, chunk_id, document_id, score, method, ?preview}]` |

**Graph bias stage (`retrieval.graph.bias`)**:

| Attribute | Description |
|---|---|
| `retrieval.input_count` | Chunks before bias |
| `retrieval.graph.linked_count` | Number of provenance-linked chunks found |
| `retrieval.graph.boosted_count` | Number of chunks boosted by graph bias |
| `retrieval.graph.linked_chunk_ids` | JSON array of linked chunk IDs (up to 20) |

### Graph Span Output Summaries

**Resolver (`graph.resolver.run`)**:

| Attribute | Description |
|---|---|
| `graph.chunk_count` | Number of chunks to process |
| `graph.chunks_processed` | Chunks actually processed |
| `graph.canonical_created` | New canonical concepts created |
| `graph.canonical_merged` | Concepts merged into existing |
| `graph.llm_disambiguations` | LLM calls for disambiguation |
| `graph.raw_concepts_written` | Raw concept rows written |
| `graph.raw_edges_written` | Raw edge rows written |

**Resolver chunk (`graph.resolver.chunk`)**:

| Attribute | Description |
|---|---|
| `graph.concepts_extracted` | Raw concept count extracted from this chunk |
| `graph.edges_extracted` | Raw edge count extracted from this chunk |

**Gardener (`graph.gardener.run`)**:

| Attribute | Description |
|---|---|
| `graph.seed_nodes` | Number of dirty seed concepts selected |
| `graph.clusters_total` | Total clusters found |
| `graph.clusters_processed` | Clusters processed by LLM |
| `graph.clusters_skipped` | Clusters skipped (low confidence, etc.) |
| `graph.merges_applied` | Successful concept merges |
| `graph.llm_calls` | LLM calls made |
| `graph.stopped_by_cluster_budget` | Whether cluster budget was exhausted |
| `graph.stopped_by_llm_budget` | Whether LLM budget was exhausted |

### Structured Events (`emit_event`)

Events are emitted both as structured logs and as OTel span events on the
active span (visible in the Phoenix Events tab).

| Event Name | Component | Status Values | Source |
|---|---|---|---|
| `llm.call` | LLM adapter | `success`, `failure` | `adapters/llm/providers.py` |
| `grading.level_up.start` | Grading | `info` | `domain/learning/quiz_flow.py` |
| `grading.level_up.result` | Grading | `success` | `domain/learning/quiz_flow.py` |
| `grading.level_up.failure` | Grading | `failure` | `domain/learning/quiz_flow.py` |
| `grading.practice.start` | Grading | `info` | `domain/learning/quiz_flow.py` |
| `grading.practice.result` | Grading | `success` | `domain/learning/quiz_flow.py` |
| `grading.practice.failure` | Grading | `failure` | `domain/learning/quiz_flow.py` |
| `graph.resolver.budget.usage` | Graph resolver | `info` | `domain/graph/resolver.py` |
| `graph.resolver.budget.hard_stop` | Graph resolver | `warning` | `domain/graph/resolver.py` |
| `graph.gardener.budget.usage` | Graph gardener | `info` | `domain/graph/gardener.py` |
| `graph.gardener.budget.hard_stop` | Graph gardener | `warning` | `domain/graph/gardener.py` |
| `graph.gardener.cluster.skip` | Graph gardener | `info` | `domain/graph/gardener.py` |

---

## Phoenix Operator Guide

### Routes That Should Never Appear

Only AI-significant operations produce Phoenix spans. You should **never**
see spans for:

- `/api/healthz`, `/api/openapi.json`, or any static/docs endpoints
- CRUD-only routes (workspace listing, session CRUD, document listing)
- Middleware-level HTTP requests — these are tracked via structured logs only

If any of the above appear in Phoenix, it indicates a tracing scope bug.

### Suggested Filters

| What to find | Phoenix filter |
|---|---|
| All chat requests | Span name contains `chat.respond` or `chat.stream` |
| Streaming only | Span name = `chat.stream` |
| LLM calls | Span kind = `LLM` |
| Token usage | Attribute `llm.token_count.total` exists |
| Budget stops | Event name contains `hard_stop` |
| Graph extraction | Span name = `graph.resolver.run` |
| Gardener runs | Span name = `graph.gardener.run` |
| Retrieval pipeline | Span kind = `RETRIEVER` |
| Vector search only | Span name = `retrieval.vector.search` |
| FTS search only | Span name = `retrieval.fts.search` |
| Graph bias effect | Span name = `retrieval.graph.bias` |
| Specific concept | Attribute `concept.id` = `<value>` |
| Specific user | Attribute `user.id` = `<value>` |
| Specific workspace | Attribute `workspace_id` = `<value>` |

### Reading Retrieval Spans

The retrieval pipeline produces four child spans under `chat.respond` / `chat.stream`:

1. **`retrieval.vector.search`** — pgvector cosine similarity search. Check
   `retrieval.results_count` to see how many chunks the vector index returned.
2. **`retrieval.fts.search`** — Postgres full-text search. Low `results_count`
   may indicate the query didn't match well via keywords.
3. **`retrieval.hybrid.fuse`** — RRF fusion combining vector and FTS results.
   The `retrieval.method_distribution` attribute shows how many results came
   from each source and how many appeared in both.
4. **`retrieval.graph.bias`** — concept-graph reranking. `boosted_count` shows
   how many chunks were boosted by knowledge-graph provenance links.

### Understanding Token Usage Sources

The `llm.usage_source` attribute indicates where token counts come from:

| Value | Meaning |
|---|---|
| `provider_reported` | Token counts returned by the LLM API (authoritative) |
| `estimated` | Token counts estimated locally (less reliable) |
| `missing` | No token data available for this call |

When `llm.usage_source` is `missing`, the token count fields will be null.
Do not assume zero tokens — the provider simply did not report usage.

### Safe Mode (Content Omitted)

When `APP_OBSERVABILITY_RECORD_CONTENT=false`:

- LLM span `llm.input_messages` and `llm.output_messages` are **not set**
- Chat domain span `input.value` and `output.value` contain **preview only** (first 256 chars)
- Graph, practice, grading, and ingestion spans **still show compact metadata summaries**
  via `set_span_summary` — these are non-sensitive (IDs, counts) and are always emitted
- Token counts, prompt metadata, and all other attributes remain fully populated
- Retrieval `retrieval.query` still shows the first 256 characters
- Retrieval `retrieval.documents` `preview` field is **omitted** in safe mode

This mode is appropriate for shared/production Phoenix instances where prompt
content should not be persisted.

---

## Token Accounting Caveats

| Provider Path | Token Fields Available | Notes |
|---|---|---|
| **Direct OpenAI** (`graph_llm_provider=openai`) | `token_prompt`, `token_completion`, `token_total` | Full `usage` object returned by API. |
| **LiteLLM proxy** (`graph_llm_provider=litellm`) | Usually all three | Depends on upstream model passing `usage` through LiteLLM. |
| **No `usage` in response** | All `null` | `extract_token_usage()` returns `null` for all fields. |

- Token counts are **per LLM call**, not per request or per quiz.
- Aggregate token counts in the Phoenix UI using span grouping.
- The `extract_token_usage` helper normalises both OpenAI (`prompt_tokens`) and Anthropic (`input_tokens`) key names and extracts `cached_tokens` from `prompt_tokens_details.cached_tokens` when present.
- Usage source is always labeled via `llm.usage_source` — never silently estimated.
- **Cached tokens**: When the provider reports `prompt_tokens_details.cached_tokens`, this value is surfaced on LLM spans as `llm.token_count.cached`, in the `llm.call` event as `token_cached`, and in the user-facing `GenerationTrace` as `cached_tokens`.  A non-null value indicates a prefix-caching hit — the corresponding prompt tokens were served from cache at reduced cost/latency.

---

## Span Status

All spans created via `start_span()` automatically set OTel status:

- **OK** on normal completion
- **ERROR** with recorded exception on failure

Streaming spans via `create_span()` set status manually in the generator
lifecycle (OK on final event yield, ERROR on exception).

---

## Verification Checklist

1. **Default startup (no Phoenix)**
   ```bash
   docker compose up -d          # only Postgres starts
   APP_OBSERVABILITY_ENABLED=false make dev
   curl http://localhost:8000/api/healthz   # 200 OK, no errors
   ```

2. **Phoenix starts in isolation**
   ```bash
   docker compose --profile observability up -d phoenix
   curl -s http://localhost:6006 | head -1   # HTML response
   ```

3. **Traces visible in Phoenix**
   ```bash
   # .env has APP_OBSERVABILITY_ENABLED=true + endpoint set
   make dev
   # trigger chat or practice operations
   # open http://localhost:6006 → filter by service "colearni-backend"
   # verify: nested spans with chat.respond/chat.stream as root, LLM kind icons,
   #         input/output messages, token counts, prompt metadata
   # verify: retrieval sub-spans (vector.search, fts.search, hybrid.fuse, graph.bias)
   #         are nested under chat root
   ```

4. **Content recording off**
   ```bash
   APP_OBSERVABILITY_RECORD_CONTENT=false make dev
   # verify: spans appear but llm.input_messages / output.value are absent
   # verify: preview/length attributes are still present
   ```

5. **Streaming chat traced**
   ```bash
   # trigger streaming chat with APP_CHAT_STREAMING_ENABLED=true
   # verify: chat.stream root span appears with input/output
   # verify: child LLM span and retrieval span are nested under it
   ```

6. **Graph traces have summaries**
   ```bash
   # trigger document ingest
   # verify: graph.resolver.run span shows chunk_count, canonical_created, etc.
   # trigger gardener run
   # verify: graph.gardener.run span shows seed_nodes, merges, budget flags
   # verify: cluster skip events appear in Events tab
   ```

---

## Generation Trace (User-Facing)

The `GenerationTrace` object is attached to every `AssistantResponseEnvelope` on the
blocking `/chat/respond` path and emitted as a `trace` SSE event on the streaming
`/chat/respond/stream` path.  It contains **safe operational metrics only** — no
chain-of-thought, prompt content, or raw model output is ever included.

### Trace Fields

| Field | Type | Notes |
|---|---|---|
| `provider` | string \| null | `"openai"` or `"litellm"` |
| `model` | string \| null | Model identifier (e.g. `gpt-4o`, `qwen/qwen3-30b-a3b`) |
| `timing_ms` | number \| null | Wall-clock latency in milliseconds |
| `prompt_tokens` | integer \| null | Input token count |
| `completion_tokens` | integer \| null | Output token count |
| `total_tokens` | integer \| null | Sum of prompt + completion |
| `cached_tokens` | integer \| null | Cached prompt tokens (prefix caching hit); null when provider does not report |
| `reasoning_tokens` | integer \| null | Reasoning tokens (o1/o3/o4 models only) |
| `reasoning_requested` | boolean \| null | Whether reasoning was requested for this call |
| `reasoning_supported` | boolean \| null | Whether the model supports reasoning params |
| `reasoning_used` | boolean \| null | Whether reasoning params were actually sent |

All fields are nullable.  When the LLM provider does not report usage, token fields
are `null`.  Social and onboarding fast-path responses have `generation_trace: null`.

### Safety Guarantees

- **No chain-of-thought**: reasoning content is never included; only the token count and boolean metadata.
- **No prompt leakage**: the trace carries only provider/model identifiers and numeric metrics.
- **Capability gating**: `reasoning_tokens` is only populated for models that support the
  reasoning API (prefix `o1`, `o3`, `o4`).  Other models return `null`.
- **Reasoning metadata**: `reasoning_requested/supported/used` indicate whether reasoning was
  attempted without exposing any reasoning content.  Raw reasoning summaries are explicitly
  deferred (see S5 in GENERATION_STATUS_PLAN.md).

---

## Stream Diagnostics

When `APP_CHAT_STREAMING_ENABLED=true`, the streaming chat path emits diagnostic logs:

### Backend (`apps/api/routes/chat.py`)

- Logs each SSE event with its type and count: `stream event #N type=<type> ws=<ws_id>`
- Logs stream completion: `stream complete: N events ws=<ws_id>`

### Frontend (`use-tutor-messages.ts`, `client.ts`)

Console diagnostics (visible in browser DevTools):

| Log | Level | Meaning |
|---|---|---|
| `[tutor-stream] STREAMING_ENABLED=<value>` | info | Module-load: confirms streaming flag |
| `[tutor-stream] initiating SSE stream` | info | Stream path entered |
| `[tutor-stream] first event received: <type>` | info | First SSE event parsed |
| `[tutor-stream] phase -> <phase>` | info | Phase transition from backend |
| `[tutor-stream] final event received` | info | Final envelope arrived |
| `[tutor-stream] stream error, falling back` | warn | Stream failed, blocking fallback |
| `[respondChatStream] connecting to <url>` | info | SSE URL being used |
| `[respondChatStream] response ok` | info | HTTP response received |

### Fallback Visibility

When streaming fails and falls back to blocking mode:

- `streamFallback` boolean is exposed via `useTutorMessages` hook
- The tutor timeline displays a `⚠ fallback` badge next to the phase label
- Console warning includes the error message that triggered fallback

### Transport Configuration

| Env var | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_STREAM_BASE_URL` | `/api` (proxied) | Direct backend URL for SSE; set to `http://127.0.0.1:8000` to bypass Next.js proxy |
| `APP_CORS_ALLOWED_ORIGINS` | `[]` | Backend CORS origins; must include frontend origin when using direct SSE |
| `APP_CHAT_STREAMING_ENABLED` | `false` | Backend feature gate |
| `NEXT_PUBLIC_CHAT_STREAMING_ENABLED` | `false` | Frontend feature gate |

---

## Default (Off) Behavior

When `APP_OBSERVABILITY_ENABLED=false` (the default):

- `emit_event()` returns `None` immediately — no JSON serialization, no logging.
- `start_span()` yields `None` — no tracer is allocated, no span context is created.
- `create_span()` returns `None` — safe for streaming generators.
- `configure_observability()` skips all OTel SDK initialization.
- **No network connections** are made to any collector or Phoenix instance.
