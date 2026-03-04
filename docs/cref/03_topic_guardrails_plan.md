# Colearni Refinement — Topic Guardrails & Graph Context Plan

Last updated: 2026-03-04

Parent plan: `docs/CREF_MASTER_PLAN.md`

Archive snapshots:
- `docs/archive/cref/03_topic_guardrails_plan_v0.md`

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

This track addresses two related problems:

1. **Topic switching is unguarded**: When RAG retrieves evidence that mentions a distant topic, the tutor may switch to that topic without the student intending it. The system should guardrail topic changes: first try to keep the student on their current topic, and if they truly want to switch, only allow adjacent topics on the canonical graph (within k hops).

2. **Graph representation to LLM is suboptimal**: The LLM currently has limited context about the graph structure, topic adjacency, and the student's position in the learning path. Reworking how the graph is retrieved and represented to the LLM will enable both better topic guardrails and more contextual tutoring.

These changes depend on CREF1 (standardized message format) for proper graph context injection.

## Inputs Used

- `docs/CREF_MASTER_PLAN.md` (parent plan)
- `docs/GRAPH.md` — graph data structures, canonical concepts, edges
- `domain/chat/query_analyzer.py` — current query analysis
- `domain/chat/response_service.py` — tutor response generation
- `domain/graph/` — graph queries, exploration
- `adapters/db/` — graph DB queries

## Executive Summary

What works today:
- Query analyzer detects topic intent
- Tutor responds based on current concept
- Graph adjacency data is available in the DB
- Retrieval returns evidence with source metadata

What this track fixes or adds:
1. Topic switching guardrails — keep student on topic, allow only adjacent transitions
2. Graph context for LLM — provide the LLM with local graph topology around current topic
3. Improved topic change detection and handling in the response pipeline

## Non-Negotiable Constraints

1. Topic guardrails must not prevent the student from eventually switching — they should guide, not block
2. Adjacency is defined as k-hop on the canonical graph (default k=2)
3. Graph context must stay within token budget — no dumping the full graph into context
4. Do not change the canonical graph schema (GRAPH.md)
5. Evidence retrieval logic stays in `adapters/retrieval/`

## Completed Work (Do Not Reopen Unless Blocked)

- Query analyzer with intent detection
- Canonical graph with adjacency edges
- Graph exploration API

## Remaining Slice IDs

- `CREF3.1` Graph Context Retrieval for LLM
- `CREF3.2` Topic Change Detection
- `CREF3.3` Topic Switching Guardrails

## Decision Log

1. Graph context is a compact text representation of the local subgraph (current node + k-hop neighbors with edge types), injected as a system message section.
2. Topic change is detected by comparing the user query's detected concept against the session's current concept — if different, it's a potential switch.
3. Guardrail logic: if detected topic is within k-hops → allow with confirmation; if outside k-hops → redirect student back to current topic and explain adjacency.
4. k=2 hops as default adjacency limit.

## Current Verification Status

- `pytest -q`: baseline to be recorded

Hotspots:

| File | Why it matters |
|---|---|
| `domain/chat/query_analyzer.py` | Topic detection logic |
| `domain/chat/response_service.py` | Where guardrails are applied |
| `domain/graph/` | Graph adjacency queries |
| `adapters/db/` | Graph DB queries |

## Implementation Sequencing

### CREF3.1. Slice 1: Graph Context Retrieval for LLM

Purpose:
- Create a function that retrieves the local graph topology around the current topic and formats it for LLM context.

Root problem:
- The LLM has no awareness of graph structure. It doesn't know which topics are adjacent, which are distant, or what the student's learning path looks like.

Files involved:
- New: `domain/graph/context.py`
- `adapters/db/` graph query helpers
- `domain/chat/response_service.py` (to inject context)

Implementation steps:
1. Create `domain/graph/context.py` with `get_graph_context(workspace_id, concept_id, k_hops=2)`:
   - Query canonical graph for the current concept and its k-hop neighbors
   - Include edge types (structural + semantic)
   - Include concept names, tiers, and mastery status
   - Format as compact text: `"Current topic: {name} (tier: {tier}, mastery: {status})\nAdjacent topics:\n- {name1} ({relation})\n- {name2} ({relation})\n..."`
2. Limit output to ~500 tokens max
3. Add the graph context as a section in the system message (after static instructions, before dynamic context)
4. Add tests for the context retrieval and formatting

What stays the same:
- Graph data structures
- Retrieval logic
- System message static prefix

Verification:
- `pytest -q tests/`
- Unit test: graph context includes current node + neighbors within k hops
- Unit test: output stays within 500 token budget

Exit criteria:
- LLM receives graph context about current topic's neighborhood
- Context is token-bounded
- Graph context is visible in Phoenix traces

### CREF3.2. Slice 2: Topic Change Detection

Purpose:
- Detect when the user's query implies a topic different from the session's current topic.

Root problem:
- Currently, topic changes can happen implicitly through RAG retrieval. The system needs to explicitly detect when the user's intent is about a different topic.

Files involved:
- `domain/chat/query_analyzer.py`
- `domain/chat/response_service.py`

Implementation steps:
1. Extend `QueryAnalysis` with `detected_concept_id: Optional[UUID]` and `is_topic_change: bool`
2. In `run_query_analysis()`, compare detected concept against session's current concept
3. If different, set `is_topic_change = True` and include the detected concept ID
4. Use the graph context (from CREF3.1) to determine if the detected concept is within k-hops
5. Add `is_adjacent: bool` to the analysis result
6. Update tests

What stays the same:
- Query analysis prompt
- Other analysis fields (intent, needs_retrieval, etc.)
- Session concept management

Verification:
- `pytest -q tests/`
- Unit test: query about a different topic sets `is_topic_change=True`
- Unit test: `is_adjacent` correctly reflects graph distance

Exit criteria:
- Topic changes are explicitly detected
- Adjacency is determined from graph data
- Analysis result includes all new fields

### CREF3.3. Slice 3: Topic Switching Guardrails

Purpose:
- Implement the guardrail logic that keeps students on topic and limits switching to adjacent graph nodes.

Root problem:
- Students can jump to any topic through their queries, even if the topic is across the graph with no learning path connection.

Files involved:
- `domain/chat/response_service.py`
- `domain/chat/` new guardrail module
- Prompt templates (add guardrail instructions)

Implementation steps:
1. Create guardrail logic in `domain/chat/topic_guard.py`:
   - `evaluate_topic_change(analysis: QueryAnalysis, session_concept_id, workspace_id) -> TopicGuardResult`
   - Returns: `action` (allow, redirect, confirm), `redirect_message`, `adjacent_topics`
2. If `action == "redirect"`: tutor steers back to current topic, mentions the student's topic interest
3. If `action == "confirm"`: tutor asks "Would you like to switch to {topic}? It's related to your current study."
4. If `action == "allow"`: proceed normally (topic is current or adjacent and user confirmed)
5. Add system prompt instructions about topic guardrails
6. Wire into response pipeline after query analysis
7. Update tests

What stays the same:
- Retrieval logic
- Mastery tracking
- Level-up flow

Verification:
- `pytest -q tests/`
- Unit test: query about distant topic returns `redirect` action
- Unit test: query about adjacent topic returns `confirm` action
- Unit test: query about current topic returns `allow` action
- Manual check: tutor redirects when student asks about a far-away topic

Exit criteria:
- Topic switching is guardrailed
- Adjacent topics (k<=2 hops) can be switched to with confirmation
- Distant topics are redirected
- Tutor is helpful, not blocking

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

1. `CREF3.1` Graph Context Retrieval for LLM
2. `CREF3.2` Topic Change Detection
3. `CREF3.3` Topic Switching Guardrails

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
Read docs/CREF_MASTER_PLAN.md, then read docs/cref/03_topic_guardrails_plan.md.
Begin with the next incomplete CREF3 slice exactly as described.

Execution loop for this child plan:

1. Work on one CREF3 slice at a time.
2. Do not change the canonical graph schema. Guardrails must guide, not block. k=2 hop default.
3. Run the listed verification steps before claiming a slice complete.
4. When a slice is complete, add:
   - the normal Verification Block for that slice
   - a summary of all Removal Entries added during that slice
5. After every 2 completed CREF3 slices OR if context is compacted/summarized, re-open docs/CREF_MASTER_PLAN.md and docs/cref/03_topic_guardrails_plan.md and restate which CREF3 slices remain.
6. Continue to the next incomplete CREF3 slice once the previous slice is verified.
7. When all CREF3 slices are complete, immediately re-open docs/CREF_MASTER_PLAN.md, select the next incomplete child plan, and continue in the same run.

Do NOT stop just because CREF3 is complete. CREF3 completion is only a checkpoint unless the master status ledger shows no remaining incomplete tracks.

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
Read docs/cref/03_topic_guardrails_plan.md.
Begin with the current CREF3 slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
When CREF3 is complete, immediately return to docs/CREF_MASTER_PLAN.md and continue with the next incomplete child plan.
```
