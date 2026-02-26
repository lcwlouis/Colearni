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

## Default (Off) Behavior

When `APP_OBSERVABILITY_ENABLED=false` (the default):

- `emit_event()` returns `None` immediately — no JSON serialization, no logging.
- `start_span()` yields `None` — no tracer is allocated, no span context is created.
- `configure_observability()` skips all OTel SDK initialization.
- **No network connections** are made to any collector or Phoenix instance.
