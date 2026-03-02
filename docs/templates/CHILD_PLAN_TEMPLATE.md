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
You are working in the {project_name} repo.

STRICT INSTRUCTIONS:

Open and read {child_plan_path} now. This is the active child plan.
Also read the master plan at {master_plan_path} for cross-track context.

You MUST implement slices in the EXACT execution order listed in this child plan.
You MUST NOT claim a slice is complete until you produce a Verification Block with:
Root cause
Files changed
What changed
Commands run
Manual verification steps
Observed outcome

Before removing or replacing any artifact, document the removal using the Removal Entry Template from the master plan.

After every 2 slices OR if your context is compacted/summarized, re-open this child plan and restate which slices remain.

Work in small commits: chore(refactor): <slice-id> <short desc>.
If you discover a mismatch between current repo behavior and assumptions in this plan, STOP and update the plan before moving on.

START:

Read {child_plan_path}.
Begin with the first incomplete slice.
Do not proceed beyond the current slice until verified.
```
