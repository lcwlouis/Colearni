# {PROJECT_NAME} — Master Plan

<!--
TEMPLATE INSTRUCTIONS:
1. Replace all {PLACEHOLDERS} with project-specific values
2. Delete this instructions block when done
3. File path convention: docs/{PROJECT_PREFIX}_MASTER_PLAN.md
4. Child plans go in: docs/{project_prefix}/NN_{track_name}_plan.md
-->

Last updated: {DATE}

Archive snapshots:
- `{path_or_none}`

Template usage:
- This is the cross-track execution plan for {brief_project_description}.
- It does not replace {list_of_other_active_plans_if_any}.
- All child plans are subordinate to this document.

## Plan Completeness Checklist

This plan should be treated as incomplete unless it includes:

1. archive snapshot path(s)
2. current verification status
3. ordered track list with stable IDs
4. verification block template
5. removal entry template
6. final section named `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`

## Non-Negotiable Run Rules

1. You MUST re-open and re-read this file:
   - at the start of the run
   - after every 2 refactor slices
   - after any context compaction / summarization / "I may lose context" moment
   - before claiming any slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in the child plan are met
3. Work in SMALL PR-sized chunks:
   - one slice or sub-slice at a time
   - prefer commit message format: `chore(refactor): <slice-id> <short description>`
4. For each slice, you MUST produce a `Verification Block` (see template below).
5. Do not reopen completed slices unless:
   - the current slice is blocked by them, or
   - the code no longer matches the assumptions in this file
6. If implementation uncovers a behavior change risk, STOP and update this plan before widening scope.
7. {Additional_project_specific_rule_or_delete}
8. A generated refactor plan is INCOMPLETE unless it ends with a section titled:
   - `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`
   - followed by exactly one fenced code block containing the run prompt

## Purpose

{2-3 paragraphs explaining:
- What this project is about
- What earlier work already landed
- Why this plan exists now}

## Inputs Used

This plan is based on:

- {list of documents, test results, user feedback, repo state references}

## Executive Summary

What is already in good shape:
- {list completed/working features}

What is critically broken or materially missing:
1. {numbered list of gaps}

## Non-Negotiable Constraints

1. {constraint_1}
2. {constraint_2}

## Completed Work (Do Not Reopen Unless Blocked)

- {list of completed tracks/features that are off-limits}

## Remaining Track IDs

- `{PREFIX}1` {Track 1 name} — {one-line description}
- `{PREFIX}2` {Track 2 name} — {one-line description}

## Child Plan Map

| Track | Child Plan | Status |
|---|---|---|
| `{PREFIX}1` {name} | `docs/{project_prefix}/01_{track_name}_plan.md` | pending |
| `{PREFIX}2` {name} | `docs/{project_prefix}/02_{track_name}_plan.md` | pending |

## Decision Log

1. {Pre-made decision relevant to this project}
2. {Another decision}

## Clarifications Requested (Already Answered)

1. {Question → Answer}

## Deferred Follow-On Scope

- {Work intentionally excluded and why}

## Removal Safety Rules

These rules apply whenever a remaining slice removes, replaces, inlines, or archives code:

1. Do not remove a file, function, route, schema, type, selector, or compatibility shim without recording:
   - what is being removed
   - why removal is safe
   - what replaces it
   - how to restore it if rollback is needed
2. Prefer staged removal over hard deletion.
3. Maintain a removal ledger in each child plan during the run.

## Removal Entry Template

```text
Removal Entry - <slice-id>

Removed artifact
- <file / function / route / schema / selector>

Reason for removal
- <why it was dead, duplicated, or replaced>

Replacement
- <new file/module/path or "none" if true deletion>

Reverse path
- <exact steps to restore or revert>

Compatibility impact
- <public/internal, none/minor/major>

Verification
- <tests or manual checks proving the replacement works>
```

## Current Verification Status

Current repo verification status:

- `{test_command_1}`: {count} passed
- `{test_command_2}`: {count} passed

Current remaining hotspots:

| File | Why it still matters |
|---|---|
| `{file_path}` | {reason} |

## Remaining Work Overview

### {PREFIX}1. {Track 1 Name}

{2-5 sentences describing what this track does, the root problem, and the approach.}

### {PREFIX}2. {Track 2 Name}

{Same format.}

## Cross-Track Execution Order

Tracks should be executed in this order. Each track's child plan defines its internal slice order.

1. `{PREFIX}1` {name} — {why first}
2. `{PREFIX}2` {name} — {why second}

Dependencies between tracks:

- `{PREFIX}2` depends on `{PREFIX}1` because {reason}
- `{PREFIX}3` is independent and can run in parallel with {PREFIX}2

## Master Status Ledger

| Track | Status | Last note |
|---|---|---|
| `{PREFIX}1` {name} | 🔄 pending | Not started |
| `{PREFIX}2` {name} | 🔄 pending | Not started |

## Verification Block Template

For every completed slice, include this exact structure in the child plan:

```text
Verification Block - <slice-id>

Root cause
- <what made this area insufficient?>

Files changed
- <file list>

What changed
- <short description of the changes>

Commands run
- <tests / typecheck / lint commands>

Manual verification steps
- <UI/API/dev verification steps>

Observed outcome
- <what was actually observed>
```

## Verification Matrix

Run these commands at the end of every slice unless the slice is docs-only:

```bash
{test_command_1}
{test_command_2}
```

## What Not To Do

Do not do the following during this project:

- {guard_rail_1}
- {guard_rail_2}

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

This section is mandatory.

If this plan does not end with this section and the fenced prompt block below, the plan is incomplete and should be fixed before use.

Use this single prompt for the implementation phase:

```text
Read {master_plan_path}.
Select the first child plan in execution order that still has incomplete slices.
Read that child plan and begin with its current incomplete slice exactly as described.

Execution loop:

1. Work on exactly one sub-slice at a time and keep the change set PR-sized.
2. Preserve all constraints in {master_plan_path} and the active child plan.
3. Run the slice verification steps before claiming completion.
4. When a slice is complete, update:
   - the active child plan with a Verification Block
   - the active child plan with any Removal Entries added during that slice
   - {master_plan_path} with the updated status ledger / remaining status note
5. After every 2 completed slices OR if your context is compacted/summarized, re-open {master_plan_path} and the active child plan and restate which slices remain.
6. If the active child plan still has incomplete slices, continue to the next slice.
7. If the active child plan is complete, go back to {master_plan_path}, pick the next incomplete child plan in order, and continue.

Stop only if:

- verification fails
- the current repo behavior does not match plan assumptions and the plan must be updated first
- a blocker requires user input or approval
- completing the next slice would force a risky scope expansion

Do NOT stop because one child plan is complete.
Do NOT stop because you updated the session plan, todo list, or status ledger.
The run is only complete when {master_plan_path} shows no remaining incomplete tracks.

{project_specific_constraints}

START:

Read {master_plan_path}.
Pick the first incomplete child plan in execution order.
Begin with the current slice in that child plan exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
Make sure you re-read {master_plan_path} before every move to the next child plan. It can be dynamically updated. Check the latest version and continue.
```
