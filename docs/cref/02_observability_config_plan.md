# Colearni Refinement — Observability & Config Fixes Plan

Last updated: 2026-03-04

Parent plan: `docs/CREF_MASTER_PLAN.md`

Archive snapshots:
- `docs/archive/cref/02_observability_config_plan_v0.md`

## Plan Completeness Checklist

This plan should be treated as incomplete unless it includes:

1. archive snapshot path(s)
2. current verification status
3. ordered slice list with stable IDs
4. verification block template (inherited from master)
5. removal entry template (inherited from master)
6. final section named `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`

## Non-Negotiable Run Rules

1. You MUST re-open and re-read this file:
   - at the start of the run
   - after every 2 refactor slices
   - after any context compaction / summarization
   - before claiming any slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in this file are met
3. Work in SMALL PR-sized chunks:
   - one slice or sub-slice at a time
   - prefer commit message format: `chore(refactor): <slice-id> <short description>`
4. For each slice, you MUST produce a `Verification Block` (template in master plan).
5. If implementation uncovers a behavior change risk, STOP and update this plan and the master plan before widening scope.
6. If a slice is reopened during an audit cycle, treat it as a fresh slice: re-read the slice definition, re-implement, re-verify, and produce a new Verification Block prefixed with "Audit Cycle N —".

## Purpose

This track fixes two targeted issues in the observability and configuration layer:

1. **Phoenix evidence truncation**: Evidence data in OpenTelemetry spans is being truncated, making it impossible to inspect full evidence payloads in the Phoenix UI. This is likely caused by the `_AIOnlySpanExporter` or OTel attribute size limits.

2. **Query agent model misconfiguration**: The query analyzer reports using `gpt5nano` when the configuration specifies `4.1nano`. This is a settings lookup bug — either a hardcoded default, a wrong config key, or a fallback that's taking precedence.

These are quick-win fixes that unblock debugging for all other tracks.

## Inputs Used

- `docs/CREF_MASTER_PLAN.md` (parent plan)
- `core/observability.py` — span exporter, attribute serialization
- `domain/chat/query_analyzer.py` — query analysis LLM call
- `adapters/llm/factory.py` — model selection
- `docs/OBSERVABILITY.md` — Phoenix setup reference

## Executive Summary

What works today:
- OpenTelemetry tracing is configured and exports to Phoenix
- Spans include `llm.input_messages`, `llm.output_messages`, token counts
- Content redaction works for sensitive keys
- Query analyzer runs and returns typed results

What this track fixes or adds:
1. Evidence data no longer truncated in Phoenix spans
2. Query agent uses the correct configured model

## Non-Negotiable Constraints

1. Never log secrets or full sensitive payloads (ARCHITECTURE.md)
2. Keep observability provider-agnostic; Phoenix is optional
3. Do not change span schema — only fix serialization/size issues

## Completed Work (Do Not Reopen Unless Blocked)

- OpenTelemetry TracerProvider setup
- `_AIOnlySpanExporter` filtering
- OpenInference semantic conventions
- Query analyzer typed output schema

## Remaining Slice IDs

- `CREF2.1` Fix Phoenix Evidence Truncation
- `CREF2.2` Fix Query Agent Model Config

## Decision Log

1. Evidence truncation fix should increase attribute size limits or split evidence across multiple attributes, not remove evidence from spans.
2. Model config fix should trace the full config lookup chain to find where the wrong default is applied.

## Current Verification Status

- `pytest -q`: baseline to be recorded
- Phoenix UI: evidence truncation visible in span attributes

Hotspots:

| File | Why it matters |
|---|---|
| `core/observability.py` | Span attribute serialization — truncation source |
| `domain/chat/query_analyzer.py` | Model selection for query analysis |
| `adapters/llm/factory.py` | Model config lookup |

## Implementation Sequencing

Each slice should end with green tests before the next slice starts.

### CREF2.1. Slice 1: Fix Phoenix Evidence Truncation

Purpose:
- Ensure full evidence payloads are visible in Phoenix spans without truncation.

Root problem:
- OpenTelemetry has default attribute value length limits (typically 1024 or 4096 bytes). Evidence items can exceed this. The `_AIOnlySpanExporter` may also be filtering or clipping content.

Files involved:
- `core/observability.py`

Implementation steps:
1. Check the `TracerProvider` configuration for `max_attribute_length` — increase if set too low
2. Check `_AIOnlySpanExporter` for any content clipping logic
3. For evidence attributes, consider:
   - Increasing `max_attribute_length` on the span processor (e.g., 32768)
   - Or splitting large evidence into multiple indexed attributes (`retrieval.evidence.0`, `retrieval.evidence.1`, etc.)
4. Verify that content redaction is not accidentally redacting evidence
5. Add a test that verifies evidence attributes are not truncated

What stays the same:
- Span filtering logic (AI-only spans)
- Content redaction for sensitive keys
- All other span attributes

Verification:
- `pytest -q tests/`
- Manual check: trigger a chat with evidence retrieval, inspect Phoenix span — full evidence visible
- Verify no sensitive data is newly exposed

Exit criteria:
- Evidence payloads are fully visible in Phoenix UI
- No truncation of evidence content in span attributes
- Sensitive data redaction still works

### CREF2.2. Slice 2: Fix Query Agent Model Config

Purpose:
- Ensure the query analyzer uses the configured model (e.g., `gpt-4.1-nano`) instead of a stale default (`gpt5nano`).

Root problem:
- The model name shown in traces/logs for the query analyzer is `gpt5nano` when the configuration specifies `4.1nano`. This could be:
  - A hardcoded default in `query_analyzer.py`
  - A wrong config key in the factory
  - An environment variable override
  - A stale cached value

Files involved:
- `domain/chat/query_analyzer.py`
- `adapters/llm/factory.py`
- Settings/config files

Implementation steps:
1. Trace the model selection path for the query analyzer:
   - What model does `query_analyzer.py` request?
   - What does `factory.py` resolve?
   - What config/env var is read?
2. Find the discrepancy — likely a hardcoded default or wrong config key
3. Fix the lookup to use the correct configuration
4. Add a log line that records the resolved model name at startup
5. Add a test that verifies the correct model is used

What stays the same:
- Query analyzer logic and output schema
- All other model configurations

Verification:
- `pytest -q tests/`
- Manual check: trigger query analysis, verify Phoenix trace shows correct model name
- Check startup log for resolved model name

Exit criteria:
- Query analyzer uses the configured model
- Model name is correctly shown in traces and logs
- No hardcoded model defaults that override configuration

## Audit Cycle Reopening

After all tracks in the master plan reach "done", the master plan's Self-Audit Convergence Protocol may reopen slices in this child plan. The audit uses a **Fresh-Eyes** approach: the auditor treats each slice as if it has NOT been implemented, independently analyzes what should exist, then compares against actual code.

When a slice is reopened:

1. The slice status in the Execution Order is changed back to "reopened (audit cycle N)"
2. The original Verification Block is preserved (do not delete it)
3. The auditor's fresh-eyes analysis is recorded in the Audit Workspace below
4. A new Verification Block is produced, prefixed: `Audit Cycle N — Verification Block - {slice-id}`
5. The reopening reason is documented inline:
   ```
   Reopened in Audit Cycle {N}: {reason}
   ```
6. The reopened slice is **re-implemented from scratch** — do not just patch the previous attempt. Re-read the slice definition, think about what needs to happen, implement it properly, then verify.
7. Only the specific issue identified in the Audit Report is addressed — do not widen scope

**IMPORTANT**: Tests passing is necessary but NOT sufficient for marking a reopened slice as done. The auditor must confirm the logic is correct through code review, not just test results.

## Audit Workspace

This section is initially empty. During the Self-Audit Convergence Protocol, the auditor writes their fresh-eyes analysis here. For each slice being audited:

1. **Before looking at any code**, write down what SHOULD exist based on the slice definition
2. **Then** open the code and compare against the independent analysis
3. Document gaps, verdict, and reasoning

```text
(Audit entries will be appended here during the audit convergence loop)
```

## Execution Order (Update After Each Run)

1. `CREF2.1` Fix Phoenix Evidence Truncation
2. `CREF2.2` Fix Query Agent Model Config

Re-read this file after every 2 completed slices and restate which slices remain.

## Verification Matrix

Run these commands at the end of every slice unless the slice is docs-only:

```bash
pytest -q
ruff check .
```

## Removal Ledger

Append removal entries here during implementation (use template from master plan).

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

This section is mandatory.

```text
Read docs/CREF_MASTER_PLAN.md, then read docs/cref/02_observability_config_plan.md.
Begin with the next incomplete CREF2 slice exactly as described.

Execution loop for this child plan:

1. Work on one CREF2 slice at a time.
2. Do not change span schema. Keep observability provider-agnostic. Never log secrets.
3. Run the listed verification steps before claiming a slice complete.
4. When a slice is complete, add:
   - the normal Verification Block for that slice
   - a summary of all Removal Entries added during that slice
5. After every 2 completed CREF2 slices OR if context is compacted/summarized, re-open docs/CREF_MASTER_PLAN.md and docs/cref/02_observability_config_plan.md and restate which CREF2 slices remain.
6. Continue to the next incomplete CREF2 slice once the previous slice is verified.
7. When all CREF2 slices are complete, immediately re-open docs/CREF_MASTER_PLAN.md, select the next incomplete child plan, and continue in the same run.

Do NOT stop just because CREF2 is complete. CREF2 completion is only a checkpoint unless the master status ledger shows no remaining incomplete tracks.

If this child plan is being revisited during an audit cycle:
- Treat every reopened slice as if it has NOT been implemented.
- In the Audit Workspace, write what SHOULD exist BEFORE looking at code.
- Then compare against actual implementation.
- Re-implement from scratch if gaps are found — do not just patch.
- Tests passing is NOT sufficient — confirm logic correctness through code review.
- Only work on slices marked as "reopened". Do not re-examine slices that passed the audit.

Stop only if verification fails, the code no longer matches plan assumptions, a blocker requires user input, or the next slice would widen scope beyond this plan.

START:

Read docs/CREF_MASTER_PLAN.md.
Read docs/cref/02_observability_config_plan.md.
Begin with the current CREF2 slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
When CREF2 is complete, immediately return to docs/CREF_MASTER_PLAN.md and continue with the next incomplete child plan.
```
