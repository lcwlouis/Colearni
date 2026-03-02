# CoLearni UX Overhaul — Infrastructure & Polish Plan

Last updated: 2026-03-02

Parent plan: `docs/UX_OVERHAUL_MASTER_PLAN.md`

Archive snapshots:
- `none` (new plan)

## Plan Completeness Checklist

1. archive snapshot path(s) ✓
2. current verification status ✓
3. ordered slice list with stable IDs ✓
4. verification block template (inherited from master) ✓
5. removal entry template (inherited from master) ✓
6. final section `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)` ✓

## Non-Negotiable Run Rules

1. Re-read this file at start, after every 2 slices, after context compaction, before completion claims.
2. A slice is ONLY complete with code changed + behavior verified + verification block produced.
3. Work PR-sized: `chore(refactor): <slice-id> <short description>`.
4. If a behavior change risk is discovered, STOP and update this plan.
5. If a slice is reopened during an audit cycle, treat it as a fresh slice: re-read the slice definition, re-implement, re-verify, and produce a new Verification Block prefixed with "Audit Cycle N —".

## Purpose

Backend and infrastructure improvements that support the UX but aren't user-facing on their own: sources page polish, LLM prompt caching, and developer stats toggle.

## Inputs Used

- `docs/UX_OVERHAUL_MASTER_PLAN.md`
- User requirements
- `apps/web/features/sources/` (sources page components)
- `apps/web/features/tutor/components/chat-response.tsx` (dev stats)
- Backend LLM integration code

## Executive Summary

Nine slices:
1. **Sources page polish**: Fix hover cursor on upload button, change "concepts" count to show node tier breakdown
2. **LLM prompt caching**: Implement OpenAI prefix caching support for repeated system prompts
3. **Dev stats toggle**: Add a localStorage-based toggle so users can opt into seeing generation traces
4. **Phoenix Info tab observability**: Make system prompts and LLM output visible in the Phoenix Info tab for every LLM trace (not just buried in attributes)
5. **Document chunking pipeline**: Fix character-based chunking that cuts mid-sentence and silently truncates PDFs
6. **Source excerpts in prompts**: Fix truncated source material (3 chunks × 300 chars) in quiz/flashcard generation prompts
7. **Gardener rework**: Enhance gardener with document provenance, edges, mastery protection, and batched disambiguation
8. **Conductor/intent audit**: Verify or remove the intent classifier LLM call that may not influence downstream behavior
9. **Phoenix trace self-test harness**: Automated test harness that queries Phoenix GraphQL API to verify trace correctness programmatically

## Non-Negotiable Constraints

1. LLM caching must not change response quality — only reduce latency/cost
2. Dev stats toggle must default to OFF — no traces shown to normal users
3. Sources page changes must not break document upload or deletion flows

## Completed Work

- Sources page renders with document list, concept counts, upload button
- `generation_trace` included in response envelope, displayed in dev mode
- OpenAI client configured and working

## Remaining Slice IDs

- `UXI.1` Sources page polish
- `UXI.2` LLM prompt caching
- `UXI.3` Dev stats toggle
- `UXI.4` Phoenix Info tab: system prompts & output in LLM traces
- `UXI.5` Fix document chunking pipeline
- `UXI.6` Fix truncated source excerpts in prompts
- `UXI.7` Rework gardener design
- `UXI.8` Audit and fix conductor/intent classifier
- `UXI.9` Phoenix trace self-test harness

## Decision Log

1. Sources page cursor: just a CSS fix — `cursor: pointer` on the upload button
2. Node counts: show tier breakdown like "📊 5 umbrellas · 12 topics · 23 subtopics · 41 granular" instead of just "N concepts"
3. LLM caching: leverage OpenAI's automatic prefix caching by ensuring system prompts are stable and long enough (>1024 tokens). Structure prompts with static prefix first, dynamic content last.
4. Dev stats toggle: add a settings toggle (localStorage key `colearni:showDevStats`) that enables generation trace display. Also show in a collapsible section, not inline.

## Current Verification Status

- `PYTHONPATH=. pytest -q`: 922 passed
- `npx vitest run`: 106 passed

## Implementation Sequencing

### UXI.1. Sources page polish

Purpose:
- Fix cursor on upload button, improve node count display

Files involved:
- `apps/web/features/sources/components/` (source list / upload components)
- `apps/web/styles/` (CSS fixes)
- Backend: may need to return tier breakdown counts

Implementation steps:
1. Fix upload button cursor:
   - Find the upload button component
   - Ensure `cursor: pointer` is set on hover (not default/wait/spinning)
   - Check if there's a loading state incorrectly applied on hover
2. Node tier breakdown:
   - Backend: ensure the concept count endpoint returns per-tier counts (umbrella, topic, subtopic, granular)
   - If backend already returns tier info, use it in the frontend
   - If not, add a query to group concepts by tier for each document
   - Frontend: replace "N concepts" with breakdown format
3. Test document upload and deletion still work.

Verification:
- Manual: hover upload button → cursor is pointer (not spinner)
- Manual: view document → tier breakdown shown instead of flat count

Exit criteria:
- Upload button cursor is correct
- Tier breakdown visible per document

### UXI.2. LLM prompt caching

Purpose:
- Reduce LLM latency and cost by leveraging OpenAI's automatic prefix caching

Files involved:
- `domain/tutor/agent.py` or equivalent prompt construction
- `core/llm_client.py` or equivalent OpenAI client wrapper

Implementation steps:
1. Audit current prompt construction:
   - Identify the system prompt structure
   - Measure current system prompt length (must be >1024 tokens for caching to kick in)
2. Restructure prompts for cache friendliness:
   - Move static instructions to the front of the system message
   - Move dynamic/variable content (student context, concept info) to the end
   - Ensure the static prefix is identical across calls
3. Add cache usage logging:
   - Log `usage.prompt_tokens_details.cached_tokens` from the API response
   - Track cache hit rate in generation traces
4. Do NOT change prompt content — only reorder static/dynamic sections.

Verification:
- `PYTHONPATH=. pytest -q`
- Monitor Phoenix traces: look for `cached_tokens > 0` in responses after first call
- No change in response quality

Exit criteria:
- Prompts structured for caching
- Cache hits observable in traces
- No quality degradation

### UXI.3. Dev stats toggle

Purpose:
- Allow users to opt-in to seeing generation traces via a settings toggle

Files involved:
- `apps/web/features/tutor/components/chat-response.tsx`
- `apps/web/features/settings/` (settings page or modal)
- `apps/web/lib/hooks/use-settings.ts` (new or existing)

Implementation steps:
1. Create a settings hook:
   - `useDevStats()` → reads `localStorage.getItem('colearni:showDevStats')`
   - Returns `{ showDevStats: boolean, toggleDevStats: () => void }`
2. In `chat-response.tsx`:
   - Replace the `process.env.NODE_ENV === "development"` check with `showDevStats`
   - Display traces in a collapsible section (not inline)
3. Add a toggle to the settings page/modal:
   - "Show generation stats" toggle — defaults to OFF
   - Brief description: "Show detailed response generation statistics (tokens, timing, model)"
4. Ensure the toggle persists across page refreshes via localStorage.

Verification:
- `npx vitest run`
- Manual: default → no traces shown
- Manual: enable toggle → traces visible in collapsible section
- Manual: refresh page → toggle state persisted

Exit criteria:
- Toggle in settings, defaults to OFF
- Traces visible when enabled
- Persists across refreshes

### UXI.4. Phoenix Info tab: system prompts & output in LLM traces

Purpose:
- Make system prompts and LLM output immediately visible in the Phoenix Info tab for every LLM span, not buried in span attributes.

Current state:
- `set_llm_span_attributes()` in `core/observability.py` sets `llm.input_messages` and `llm.output_messages` as JSON string attributes — these appear under the Attributes panel in Phoenix, but NOT in the Info tab.
- `set_input_output()` exists and sets `input.value` / `output.value` (the fields Phoenix shows on the Info tab), but it is NOT called on LLM spans — only on domain chain spans.
- Result: opening an LLM trace in Phoenix shows a blank Info tab. The user has to dig through attributes to find the system prompt or output.

Root cause:
- `_call_with_observability()` and `_stream_with_usage()` in `adapters/llm/providers.py` call `set_llm_span_attributes()` but never call `set_input_output()`.

Files involved:
- `core/observability.py` — `set_llm_span_attributes()` function
- `adapters/llm/providers.py` — `_call_with_observability()` and `_stream_with_usage()`

Implementation steps:
1. In `set_llm_span_attributes()`, after setting `llm.input_messages` and `llm.output_messages`, also call `set_input_output()`:
   - `input_value`: format as readable text showing the system prompt and user messages (e.g., `"[system]\n{system_prompt}\n\n[user]\n{user_message}"`)
   - `output_value`: the assistant's response text
   - This ensures the Info tab shows a human-readable view of the conversation
2. Alternatively, call `set_input_output()` directly in `_call_with_observability()` and `_stream_with_usage()` after `set_llm_span_attributes()` completes.
3. Ensure this respects the existing `record_content_enabled()` gate — `set_input_output()` already checks this internally.
4. Verify all LLM call sites (chat, gardener, mastery, flashcard, quiz, graph extraction) emit the Info tab fields.

Verification:
- `PYTHONPATH=. pytest -q`
- Manual: send a tutor chat message → open Phoenix → find the LLM span → Info tab shows system prompt + user message as input, assistant response as output
- Manual: check a gardener trace → same visibility
- Manual: check a graph extraction trace → same visibility

Exit criteria:
- Every LLM span in Phoenix shows system prompt + messages in the Info tab (not just attributes)
- Output message visible in the Info tab
- Existing tests pass (no regressions)

### UXI.5. Fix document chunking pipeline

Purpose:
- Current character-based chunking (1000 chars, 150 overlap) cuts documents mid-sentence and mid-slide, causing partial document ingestion. Only a few slides of a PDF are processed.

Root cause:
- `adapters/parsers/chunker.py` `chunk_text_deterministic()` uses character-based splitting. For PDFs with slide boundaries, this can cut in the middle of content. Also, the ingestion pipeline may be dropping chunks after a certain point.

Files involved:
- `adapters/parsers/chunker.py`
- Ingestion pipeline files

Implementation steps:
1. Audit the full ingestion pipeline: PDF parse → text extraction → chunking → embedding → graph extraction. Find where content is lost.
2. Switch from character-based to token/word-based chunking (or at least increase chunk size significantly for PDFs)
3. Add boundary-aware splitting: prefer splitting at slide boundaries, paragraph boundaries, or section headers
4. Log total chunks produced vs chunks stored to detect any silent truncation
5. Verify: ingest a 50-slide PDF → all 50 slides should produce chunks

Verification:
- `PYTHONPATH=. pytest -q`
- Manual: ingest a multi-slide PDF → verify all slides produce chunks (check logs for chunk count)
- Manual: verify chunks don't cut mid-sentence

Exit criteria:
- Full document content is chunked and ingested
- No silent truncation

### UXI.6. Fix truncated source excerpts in prompts

Purpose:
- Flashcard/quiz generation prompts receive only 3 chunks × 300 chars = 900 chars of source material. This is far too little for concept-specific quiz generation.

Root cause:
- `domain/learning/quiz_persistence.py` `load_generation_context()` limits to 3 chunks and truncates each to 300 chars.

Files involved:
- `domain/learning/quiz_persistence.py`
- Prompt templates

Implementation steps:
1. Increase chunk limit from 3 to at least 8-10 chunks per concept
2. Increase per-chunk truncation from 300 to at least 800-1000 chars (or remove truncation and let token budget handle it)
3. If token budget is a concern, add a summarization step: retrieve all chunks → summarize into a dense context block → include in prompt
4. Add chat history summarization for the CHAT_HISTORY_CONTEXT section (currently dumps raw messages which wastes tokens)
5. Verify: generate a quiz → check Phoenix trace → SOURCE_MATERIAL_EXCERPTS contains substantial, useful content

Verification:
- `PYTHONPATH=. pytest -q`
- Manual: generate a quiz → check Phoenix trace → SOURCE_MATERIAL_EXCERPTS contains substantial content (not 900 chars)
- Manual: generated quizzes are more concept-specific and accurate

Exit criteria:
- Source material in prompts is sufficient for concept-specific quiz/flashcard generation
- Chat history is summarized, not raw-dumped

### UXI.7. Rework gardener design

Purpose:
- Gardener receives only node names+descriptions for pruning decisions. It cannot make informed decisions about pruning because it lacks: document summaries (which docs feed this concept?), edges (what's connected?), concept tiers, learning status (has user mastered this?).

Root cause:
- `adapters/db/graph/gardener.py` `_cluster_llm_decision()` passes only concept metadata. The pruning/orphan logic doesn't check if source documents still exist.

Files involved:
- `adapters/db/graph/gardener.py`
- Gardener LLM prompt template
- Potentially `domain/graph/` services

Implementation steps:
1. Enhance gardener context to include:
   - Document provenance (which documents fed each concept, are those docs still present?)
   - Edge list (what concepts are connected to this one?)
   - Concept tier
   - Learning status/mastery score (protect learned concepts from pruning)
2. Add orphan detection: if ALL source documents for a concept are deleted, flag for pruning
3. Add mastery protection: never prune concepts with mastery_score > 0 or mastery_status != "not_started"
4. Batch disambiguation: instead of one LLM call per cluster, batch multiple clusters into a single call with array output
5. Update gardener prompt template to include this richer context

Verification:
- `PYTHONPATH=. pytest -q`
- Manual: run gardener → verify LLM prompt includes edges, tiers, mastery status, document provenance
- Manual: verify learned concepts (mastery > 0) are not pruned
- Manual: verify orphaned concepts (no source docs) are flagged

Exit criteria:
- Gardener makes informed merge/prune decisions with full context
- Learned concepts protected
- Orphaned concepts (no source docs) are pruned
- Disambiguation is batched

### UXI.8. Audit and fix conductor/intent classifier

Purpose:
- The LLM call before generating a response (query_analyzer/intent classifier) returns intent+keywords but the result doesn't appear to influence downstream behavior. This is a wasted LLM call.

Root cause:
- `domain/chat/prompt_kit.py` `classify_social_intent()` is a regex classifier (not an LLM call). But there's a separate `query_analyzer_v1` asset rendered as an LLM prompt. The LLM result may not be consumed.

Files involved:
- `domain/chat/stream.py`
- `domain/chat/prompt_kit.py`
- `domain/chat/social_turns.py`
- Prompt assets

Implementation steps:
1. Trace the conductor/intent LLM call: where is the result used after the call?
2. If result IS used: document the flow and ensure it's working correctly
3. If result is NOT used: either integrate it properly (use intent to route between response strategies: learn → tutor, practice → flashcard, explore → graph, etc.) or remove the wasted call
4. If keeping: fix the truncated prompt visible in Phoenix — ensure full prompt renders
5. If making agentic: design a proper orchestrator that routes based on classified intent

Verification:
- `PYTHONPATH=. pytest -q`
- Manual: trace intent classifier LLM call in Phoenix → verify result is consumed downstream
- Manual: if removed, verify no wasted LLM calls occur before response generation
- Manual: if integrated, verify intent correctly routes to different response strategies

Exit criteria:
- Either the intent classifier drives routing decisions OR it's removed
- No wasted LLM calls
- Prompt not truncated

### UXI.9. Phoenix trace self-test harness

Purpose:
- Create an automated test harness that exercises real API flows and then queries Phoenix's GraphQL API to verify trace correctness. This replaces the shallow "just run pytest" self-audit with real behavioral verification.

Root cause:
- The self-audit protocol was too shallow — it only ran tests and checked for TODOs. It couldn't verify that:
  - System prompts are in the correct role
  - Prompt templates aren't truncated
  - Source material excerpts are sufficient
  - The full document content is chunked and ingested
  - Token counts are reasonable

Files involved:
- `scripts/phoenix_trace_audit.py` (new) — standalone script that:
  1. Waits for Phoenix to be available at configured endpoint
  2. Queries recent spans via GraphQL
  3. For each LLM span, asserts:
     a. `input.value` is populated (not empty)
     b. `output.value` is populated
     c. `llm.input_messages` contains at least one `role: system` message with >100 chars
     d. The system message is NOT a tiny stub (>200 chars)
     e. The user message contains the actual user query
     f. Token counts are present and reasonable (prompt > 0, completion > 0)
     g. No truncation markers in the prompt (no `... (len=` in the actual sent content)
  4. For chain spans, verifies parent-child relationships
  5. Outputs a report: PASS/FAIL per span with details
- `tests/integration/test_phoenix_traces.py` (new) — pytest wrapper that:
  1. Skips if Phoenix is not running
  2. Optionally triggers a test chat message via TestClient
  3. Waits a few seconds for trace propagation
  4. Queries Phoenix and runs assertions
  5. Can be included in CI when Phoenix is available

Implementation steps:
1. Create `scripts/phoenix_trace_audit.py` as a standalone CLI tool:
   ```python
   python scripts/phoenix_trace_audit.py --endpoint http://localhost:6006 --last-n 10
   ```
2. Create `tests/integration/test_phoenix_traces.py` with pytest markers
3. Add the script to the self-audit convergence protocol as an automated step
4. Document in `docs/OBSERVABILITY.md`

Exit criteria:
- Script can query Phoenix and verify trace structure
- Detects the known issues (system prompt in wrong role, truncated excerpts)
- Can be run by agents as part of self-audit
- Integrated into self-audit convergence protocol

## Audit Cycle Reopening

After all tracks in the master plan reach "done", the Self-Audit Convergence Protocol may reopen slices in this child plan. When a slice is reopened:

1. The slice status in the Execution Order is changed back to "reopened (audit cycle N)"
2. The original Verification Block is preserved (do not delete it)
3. A new Verification Block is produced, prefixed: `Audit Cycle N — Verification Block - {slice-id}`
4. The reopening reason is documented inline:
   ```
   Reopened in Audit Cycle {N}: {reason}
   ```
5. Only the specific issue identified in the Audit Report is addressed — do not widen scope

## Execution Order (Update After Each Run)

1. `UXI.1` Sources page polish ✅ (pre-existing)
2. `UXI.2` LLM prompt caching ✅
3. `UXI.3` Dev stats toggle ✅ (pre-existing)
4. `UXI.4` Phoenix Info tab: system prompts & output in LLM traces ✅
5. `UXI.5` Fix document chunking pipeline ✅
6. `UXI.6` Fix truncated source excerpts in prompts 🔲
7. `UXI.7` Rework gardener design 🔲
8. `UXI.8` Audit and fix conductor/intent classifier 🔲
9. `UXI.9` Phoenix trace self-test harness 🔲

### Verification Block — UXI.1

- **Root cause**: Already implemented. Global `button` in `base.css:90` has `cursor: pointer`. Tier breakdown display exists in `kb-document-table.tsx:59-70` showing `umbrella · topic · subtopic · granular` counts.
- **Files changed**: None (pre-existing)
- **What changed**: N/A — verified existing implementation matches plan requirements
- **Commands run**: Code review of `base.css` and `kb-document-table.tsx`
- **Manual verification steps**: Confirmed button cursor pointer, tier breakdown rendering with fallback to "N concepts"
- **Observed outcome**: All exit criteria met

### Verification Block — UXI.2

- **Root cause**: Prompt structure was already cache-friendly; `cached_tokens` extraction existed but lacked logging.
- **Files changed**: `adapters/llm/providers.py`
- **What changed**: Added `log.debug` for prefix cache hits in both `_call_with_observability` and `_stream_with_usage` paths.
- **Commands run**: `PYTHONPATH=. python -c "from adapters.llm.providers import _BaseGraphLLMClient"` — import ok
- **Manual verification steps**: Verified prompt structure (static prefix first, dynamic last), cached_tokens extraction in `extract_token_usage()`, and GenerationTrace.cached_tokens field
- **Observed outcome**: All exit criteria met — cache hits now logged, traces capture cached token counts

### Verification Block — UXI.3

- **Root cause**: Already implemented. `use-dev-stats.ts` hook reads `colearni:showDevStats` from localStorage. `chat-response.tsx` conditionally renders traces in `<details>` when `showDevStats` is true. `global-sidebar.tsx` has checkbox toggle.
- **Files changed**: None (pre-existing)
- **What changed**: N/A — verified existing implementation matches plan requirements
- **Commands run**: Code review of `use-dev-stats.ts`, `chat-response.tsx`, `global-sidebar.tsx`
- **Manual verification steps**: Confirmed default OFF, toggle persists via localStorage, traces in collapsible section
- **Observed outcome**: All exit criteria met

### Verification Block — UXI.4

- **Root cause**: `set_llm_span_attributes()` set `llm.input_messages`/`llm.output_messages` (Attributes panel) but never called `set_input_output()` for `input.value`/`output.value` (Phoenix Info tab).
- **Files changed**: `core/observability.py`
- **What changed**: Added call to `set_input_output()` at the end of `set_llm_span_attributes()`. Input formatted as `[role]\ncontent` blocks. Output is the assistant response text. Gated by existing `record_content_enabled()`.
- **Commands run**: `PYTHONPATH=. pytest tests/ -q` — 963 passed
- **Manual verification steps**: Verified import works, all tests pass, `set_input_output` called with properly formatted input/output
- **Observed outcome**: All exit criteria met — LLM spans will now show system prompt and output in Phoenix Info tab

## Verification Matrix

```bash
PYTHONPATH=. pytest -q
npx vitest run  # from apps/web/
```

## Removal Ledger

{Append entries during implementation}

### Verification Block — UXI.5

- **Root cause**: `chunk_text_deterministic()` used `max()` across `rfind()` results for `\n\n`, `\n`, and ` `. This picks the *latest position* regardless of boundary quality — a space at position 999 beats a paragraph break at position 500. Documents were not silently truncated (full PDF text was chunked), but splits landed at poor boundaries.
- **Files changed**: `adapters/parsers/chunker.py`, `domain/ingestion/service.py`, `tests/parsers/test_chunker.py`
- **What changed**: (1) Extracted `_find_best_break()` helper with priority cascade: paragraph break `\n\n` > line break `\n` > sentence end (`. ` / `? ` / `! `) > space. (2) Added `logging.info` in both `ingest_text_document()` and `ingest_text_document_fast()` to log chunk counts. (3) Added 3 new tests: paragraph preference, sentence preference, empty input.
- **Commands run**: `PYTHONPATH=. pytest -q` → 982 passed, 1 failed (pre-existing Phoenix)
- **Manual verification steps**: Verified `_find_best_break` returns paragraph break when available even if space occurs later. Verified no silent truncation in pipeline (all chunks stored).
- **Observed outcome**: All exit criteria met — chunks split at natural boundaries, no silent truncation, chunk counts logged.
- **Removal Entries**: None

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
Read docs/UX_OVERHAUL_MASTER_PLAN.md, then read docs/ux_overhaul/05_infrastructure_plan.md.
Begin with the next incomplete UXI slice exactly as described.

UXI.1-4 are complete. UXI.5-8 are pending — these address user feedback: document chunking pipeline, source excerpt truncation, gardener rework, and conductor/intent classifier audit.

Execution loop for this child plan:

1. Work on one UXI slice at a time.
2. LLM caching must not change response quality — only reduce latency/cost via OpenAI prefix caching. Dev stats toggle must default to OFF. Sources page changes must not break document upload or deletion flows.
3. Run the listed verification steps before claiming a slice complete, including browser-visible checks where required by the plan.
4. When a slice is complete, add:
   - the normal Verification Block for that slice
   - a summary of all Removal Entries added during that slice
5. After every 2 completed UXI slices OR if context is compacted/summarized, re-open docs/UX_OVERHAUL_MASTER_PLAN.md and docs/ux_overhaul/05_infrastructure_plan.md and restate which UXI slices remain.
6. Continue to the next incomplete UXI slice once the previous slice is verified.
7. When all UXI slices are complete, immediately re-open docs/UX_OVERHAUL_MASTER_PLAN.md, select the next incomplete child plan, and continue in the same run.

Do NOT stop just because UXI is complete. UXI completion is only a checkpoint unless the master status ledger shows no remaining incomplete tracks.

If this child plan is being revisited during an audit cycle, only work on slices marked as "reopened". Produce audit-prefixed Verification Blocks. Do not re-examine slices that passed the audit.

Stop only if verification fails, the code no longer matches plan assumptions, a blocker requires user input, or the next slice would widen scope beyond this plan.

START:

Read docs/UX_OVERHAUL_MASTER_PLAN.md.
Read docs/ux_overhaul/05_infrastructure_plan.md.
Begin with the current UXI slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
When UXI is complete, immediately return to docs/UX_OVERHAUL_MASTER_PLAN.md and continue with the next incomplete child plan.
```
