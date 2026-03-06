# L7 — Graph Batch Completion Plan

Parent: `docs/llm/LLM_MASTER_PLAN.md`
Track: L7 Graph Batching
Depends on: L1 ✅ (MessageBuilder)

## Problem

Graph extraction processes chunks serially in `build_graph_for_chunks()`. Each chunk
window makes a separate `extract_raw_graph()` LLM call. For documents with many windows
this is slow. `litellm.batch_completion()` and `asyncio.gather` on the OpenAI SDK path
can parallelize these calls.

## Approach

1. Add `batch_extract_raw_graph()` to the `GraphLLMClient` protocol and implement in
   `LiteLLMGraphLLMClient` using `litellm.batch_completion()`.
2. Add a domain-level `batch_extract_raw_graph_from_chunks()` helper.
3. Wire batch extraction into the pipeline, respecting existing budget limits.
4. Add equivalent parallel path for OpenAI SDK using `asyncio.gather`.

## Slices

### L7.1 — Batch extraction method (LiteLLM)

**Files changed:**
- `core/contracts.py` — add `batch_extract_raw_graph()` to `GraphLLMClient` protocol
- `adapters/llm/providers.py` — implement in `_BaseGraphLLMClient` using
  `complete_messages_json`, add `_batch_complete_messages_json()` in LiteLLM subclass
  using `litellm.batch_completion()`; OpenAI subclass gets a serial fallback
- `domain/graph/extraction.py` — add `batch_extract_raw_graph_from_chunks()`
- `tests/domain/test_graph_batch_extraction.py` — tests

Status: 🔄 pending

### L7.2 — Wire into pipeline with budget enforcement

**Files changed:**
- `domain/graph/pipeline.py` — replace serial loop with batched call, respect
  `max_llm_calls_per_document` budget
- `tests/domain/test_graph_pipeline_batch.py` — tests

Status: 🔄 pending

### L7.3 — OpenAI SDK parallel path

**Files changed:**
- `adapters/llm/providers.py` — implement true parallel `_batch_complete_messages_json`
  in OpenAI subclass using `asyncio.gather` + `_async_sdk_call`
- `tests/adapters/test_graph_batch_openai.py` — tests

Status: 🔄 pending

## Verification Matrix

| Check | Command |
|-------|---------|
| Unit tests pass | `.venv/bin/python -m pytest tests/domain/test_graph_batch_extraction.py tests/domain/test_graph_pipeline_batch.py tests/adapters/test_graph_batch_openai.py -v` |
| Full suite no regressions | `.venv/bin/python -m pytest tests/ --ignore=tests/db -x -q` |
| No TODO/FIXME in changed files | `grep -rn 'TODO\|FIXME\|HACK' domain/graph/extraction.py domain/graph/pipeline.py adapters/llm/providers.py core/contracts.py` |

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```
Read docs/llm/LLM_MASTER_PLAN.md and docs/llm/07_graph_batching_plan.md.
Begin with slice L7.1. Implement exactly the changes listed. Run verification.
Continue to L7.2, then L7.3.
```
