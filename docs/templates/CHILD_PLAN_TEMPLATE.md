# {PROJECT_NAME} — {TRACK_NAME} Plan

<!--
TEMPLATE INSTRUCTIONS:
1. Replace all {PLACEHOLDERS} with track-specific values
2. Delete this instructions block when done
3. File path convention: docs/{project_prefix}/NN_{track_name}_plan.md
4. Parent plan: docs/{PROJECT_PREFIX}_MASTER_PLAN.md
-->

Last updated: {DATE}

Parent plan: `{master_plan_path}`

Archive snapshots:
- `{path_or_none}`

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

## Purpose

{2-3 paragraphs explaining:
- What this track accomplishes
- How it fits into the master plan
- What the root problem is}

## Inputs Used

- `{master_plan_path}` (parent plan)
- {Other documents, code files, user feedback}

## Executive Summary

What works today:
- {list existing working features relevant to this track}

What this track fixes or adds:
1. {numbered list}

## Non-Negotiable Constraints

1. {constraint inherited from master plan or track-specific}
2. {constraint_2}

## Completed Work (Do Not Reopen Unless Blocked)

- {list of completed slices or baseline features}

## Remaining Slice IDs

- `{TRACK_PREFIX}.1` {Slice 1 name}
- `{TRACK_PREFIX}.2` {Slice 2 name}
- `{TRACK_PREFIX}.3` {Slice 3 name}

## Decision Log

1. {Pre-made decision for this track}

## Current Verification Status

- `{test_command_1}`: {count} passed
- `{test_command_2}`: {count} passed

Hotspots:

| File | Why it matters |
|---|---|
| `{file_path}` | {reason} |

## Implementation Sequencing

Each slice should end with green tests before the next slice starts.

### {TRACK_PREFIX}.1. Slice 1: {Slice Name}

Purpose:
- {What this slice accomplishes}

Root problem:
- {What makes this area insufficient today}

Files involved:
- `{file_path_1}`
- `{file_path_2}`

Implementation steps:
1. {Step 1}
2. {Step 2}
3. {Step 3}

What stays the same:
- {What this slice does NOT change}

Verification:
- `{test_command}`
- Manual check: {manual verification step}

Exit criteria:
- {Condition 1 for completion}
- {Condition 2 for completion}

### {TRACK_PREFIX}.2. Slice 2: {Slice Name}

{Same format as above.}

## Execution Order (Update After Each Run)

1. `{TRACK_PREFIX}.1` {name}
2. `{TRACK_PREFIX}.2` {name}
3. `{TRACK_PREFIX}.3` {name}

Re-read this file after every 2 completed slices and restate which slices remain.

## Verification Matrix

Run these commands at the end of every slice unless the slice is docs-only:

```bash
{test_command_1}
{test_command_2}
```

## Removal Ledger

Append removal entries here during implementation (use template from master plan).

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

This section is mandatory.

```text
Read {master_plan_path}, then read {child_plan_path}.
Begin with the next incomplete {TRACK_ID} slice exactly as described.

Execution loop for this child plan:

1. Work on one {TRACK_ID} slice at a time.
2. {track_specific_constraints}
3. Run the listed verification steps before claiming a slice complete.
4. When a slice is complete, add:
   - the normal Verification Block for that slice
   - a summary of all Removal Entries added during that slice
5. After every 2 completed {TRACK_ID} slices OR if context is compacted/summarized, re-open {master_plan_path} and {child_plan_path} and restate which {TRACK_ID} slices remain.
6. Continue to the next incomplete {TRACK_ID} slice once the previous slice is verified.
7. When all {TRACK_ID} slices are complete, immediately re-open {master_plan_path}, select the next incomplete child plan, and continue in the same run.

Do NOT stop just because {TRACK_ID} is complete. {TRACK_ID} completion is only a checkpoint unless the master status ledger shows no remaining incomplete tracks.

Stop only if verification fails, the code no longer matches plan assumptions, a blocker requires user input, or the next slice would widen scope beyond this plan.

START:

Read {master_plan_path}.
Read {child_plan_path}.
Begin with the current {TRACK_ID} slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
When {TRACK_ID} is complete, immediately return to {master_plan_path} and continue with the next incomplete child plan.
```
