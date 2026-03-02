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
You are working in the {project_name} repo.

STRICT INSTRUCTIONS:

Open and read {master_plan_path} now. This file is the cross-track source of truth.
Select the first child plan in execution order that still has incomplete slices.
Open and read that child plan.

You MUST implement slices in the EXACT execution order listed in the child plan.
You MUST NOT claim a slice is complete until you produce a Verification Block with:
Root cause
Files changed
What changed
Commands run
Manual verification steps
Observed outcome

Before removing or replacing any file, function, route, schema, type, selector, compatibility shim, or docs surface, you MUST document the removal in the child plan using the Removal Entry Template from the master plan.

Removal policy:
- Prefer reversible staged removals over hard deletes.
- If rollback would be difficult, stop and introduce a facade/shim instead of deleting immediately.
- Do not delete public contracts without a compatibility note and rollback path.

After every 2 slices OR if your context is compacted/summarized, re-open {master_plan_path} and restate which tracks and slices remain.

Work in small commits: chore(refactor): <slice-id> <short desc>.

If you discover a mismatch between current repo behavior and the assumptions in the plan, STOP and update the plan before moving on.

Execution loop:
1. Work on exactly one sub-slice at a time (PR-sized).
2. Run the verification matrix for the slice.
3. Produce the verification block in the child plan.
4. Move to the next slice.
5. After every 2 slices, re-read the master plan.
6. When a child plan is fully complete, update the Master Status Ledger and move to the next child plan.

Stop only if:
- verification fails and you cannot resolve the failure
- the current assumptions no longer match the repository
- a blocker requires human decision

Do NOT stop because one child plan is complete. Move to the next incomplete track.

START:

Read {master_plan_path}.
Pick the first incomplete child plan in execution order.
Begin with the first incomplete slice.
```
