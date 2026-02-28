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
| `APP_OBSERVABILITY_RECORD_CONTENT` | `true` | When `true`, LLM input/output messages are recorded on spans. Set to `false` to omit message content (metadata and token counts still recorded). |

---

## What Is Traced

### Span Hierarchy

Traces form a tree: **http.request → domain span → llm.call**.

```
http.request (CHAIN)             ← middleware root span
  └─ chat.respond (CHAIN)        ← domain orchestrator
       └─ llm.call (LLM)         ← LLM adapter call
```

### Spans (`start_span`)

| Span Name | Kind | Source |
|---|---|---|
| `http.request` | CHAIN | `apps/api/middleware.py` |
| `chat.respond` | CHAIN | `domain/chat/respond.py` |
| `practice.flashcards.generate` | CHAIN | `domain/learning/practice.py` |
| `practice.quiz.generate` | CHAIN | `domain/learning/practice.py` |
| `graph.resolver.run` | CHAIN | `domain/graph/pipeline.py` |
| `graph.gardener.run` | CHAIN | `domain/graph/gardener.py` |
| `grading.level_up` | CHAIN | `domain/learning/level_up.py` |
| `grading.practice` | CHAIN | `domain/learning/level_up.py` |
| `llm.call` | LLM | `adapters/llm/providers.py` |

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

### OpenInference Attributes on Domain Spans

| Attribute | Description |
|---|---|
| `openinference.span.kind` | `CHAIN` — displays chain icon in Phoenix |
| `input.value` | User query or input (when content recording is on) |
| `output.value` | Response text or JSON summary (when content recording is on) |

### Structured Events (`emit_event`)

| Event Name | Component | Status Values | Source |
|---|---|---|---|
| `llm.call` | LLM adapter | `success`, `failure` | `adapters/llm/providers.py` |
| `grading.level_up.start` | Grading | `info` | `domain/learning/level_up.py` |
| `grading.level_up.result` | Grading | `success` | `domain/learning/level_up.py` |
| `grading.level_up.failure` | Grading | `failure` | `domain/learning/level_up.py` |
| `grading.practice.start` | Grading | `info` | `domain/learning/level_up.py` |
| `grading.practice.result` | Grading | `success` | `domain/learning/level_up.py` |
| `grading.practice.failure` | Grading | `failure` | `domain/learning/level_up.py` |
| `graph.resolver.budget.usage` | Graph resolver | `info` | `domain/graph/resolver.py` |
| `graph.gardener.budget.usage` | Graph gardener | `info` | `domain/graph/gardener.py` |

---

## Token Accounting Caveats

| Provider Path | Token Fields Available | Notes |
|---|---|---|
| **Direct OpenAI** (`graph_llm_provider=openai`) | `token_prompt`, `token_completion`, `token_total` | Full `usage` object returned by API. |
| **LiteLLM proxy** (`graph_llm_provider=litellm`) | Usually all three | Depends on upstream model passing `usage` through LiteLLM. |
| **No `usage` in response** | All `null` | `extract_token_usage()` returns `null` for all fields. |

- Token counts are **per LLM call**, not per request or per quiz.
- Aggregate token counts in the Phoenix UI using span grouping.
- The `extract_token_usage` helper normalises both OpenAI (`prompt_tokens`) and Anthropic (`input_tokens`) key names.

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
   # verify: nested spans, LLM kind icons, input/output messages, token counts
   ```

4. **Content recording off**
   ```bash
   APP_OBSERVABILITY_RECORD_CONTENT=false make dev
   # verify: spans appear but llm.input_messages / output.value are absent
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
- `configure_observability()` skips all OTel SDK initialization.
- **No network connections** are made to any collector or Phoenix instance.
