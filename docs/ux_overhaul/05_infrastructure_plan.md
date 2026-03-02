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

Three independent slices:
1. **Sources page polish**: Fix hover cursor on upload button, change "concepts" count to show node tier breakdown
2. **LLM prompt caching**: Implement OpenAI prefix caching support for repeated system prompts
3. **Dev stats toggle**: Add a localStorage-based toggle so users can opt into seeing generation traces
4. **Phoenix Info tab observability**: Make system prompts and LLM output visible in the Phoenix Info tab for every LLM trace (not just buried in attributes)

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

1. `UXI.1` Sources page polish
2. `UXI.2` LLM prompt caching
3. `UXI.3` Dev stats toggle
4. `UXI.4` Phoenix Info tab: system prompts & output in LLM traces

## Verification Matrix

```bash
PYTHONPATH=. pytest -q
npx vitest run  # from apps/web/
```

## Removal Ledger

{Append entries during implementation}

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
Read docs/UX_OVERHAUL_MASTER_PLAN.md, then read docs/ux_overhaul/05_infrastructure_plan.md.
Begin with the next incomplete UXI slice exactly as described.

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
