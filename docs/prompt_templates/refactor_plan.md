# Refactor Plan Template (READ THIS OFTEN)

Last updated: <YYYY-MM-DD>

Archive snapshots:
- `<archive snapshot path>`

Template usage:
- Copy this file to `docs/REFACTOR_PLAN.md` when starting or resetting a refactor plan.
- Replace placeholders before execution begins.
- Archive the previous active plan before rewriting it.
- Do not delete or rename the final `REQUIRED KICKOFF PROMPT (DO NOT OMIT)` section.
- If you derive a new plan from this template, preserving that final section is mandatory.

## Plan Completeness Checklist

A refactor plan generated from this template is not ready to use unless it includes all of the following:

1. archive snapshot path(s)
2. current verification status
3. ordered slice list with stable IDs
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
   - the slice-specific verification gates in this file are met
3. Work in SMALL PR-sized chunks:
   - one slice or sub-slice at a time
   - prefer commit message format: `chore(refactor): <slice-id> <short description>`
4. For each slice, you MUST produce a `Verification Block` with:
   - Root cause
   - Files changed
   - What changed
   - Commands run
   - Manual verification steps
   - Observed outcome
5. Do not reopen completed slices unless:
   - the current slice is blocked by them, or
   - the code no longer matches the assumptions in this file
6. If implementation uncovers a behavior change risk, STOP and update this plan before widening scope.
7. This is a maintainability refactor plan. Do not mix in unrelated feature work.
8. A generated refactor plan is INCOMPLETE unless it ends with a section titled:
   - `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`
   - followed by exactly one fenced code block containing the run prompt

## Purpose

This document is the active execution plan for the current refactor pass.

State clearly:

- what earlier refactor work already landed
- what remains unfinished
- why this new plan exists instead of continuing the prior active version

Use this document as the source of truth for the remaining cleanup. If implementation discovers a new constraint, update this file before widening scope.

## Inputs Used

This plan is based on:

- `<archived refactor or run/verify docs>`
- `<repo architecture docs>`
- `<product docs>`
- `<post-review findings>`
- current repository layout and verification status as of `<YYYY-MM-DD>`

## Executive Summary

Summarize:

- what is already in good shape
- what is still materially missing
- why the remaining work should stay narrow

The main unfinished areas are:

1. `<gap 1>`
2. `<gap 2>`
3. `<gap 3>`

## Non-Negotiable Constraints

These constraints apply to every remaining slice:

1. `<constraint>`
2. `<constraint>`
3. `<constraint>`

## Completed Work (Do Not Reopen Unless Blocked)

These areas are considered complete enough for this phase:

- `<slice-id>` `<completed area>`
- `<slice-id>` `<completed area>`

These slices are not execution targets anymore unless a remaining slice directly depends on them.

## Remaining Slice IDs

Use these stable IDs in commits, reports, and verification blocks:

- `<slice-id>` `<slice name>`
- `<slice-id>` `<slice name>`
- `<slice-id>` `<slice name>`

## Decision Log For Remaining Work

These decisions are already made for the remaining phase:

1. `<decision>`
2. `<decision>`
3. `<decision>`

## Removal Safety Rules

These rules apply whenever a remaining slice removes, replaces, inlines, or archives code:

1. Do not remove a file, function, route, schema, type, selector, or compatibility shim without recording:
   - what is being removed
   - why removal is safe
   - what replaces it
   - how to restore it if rollback is needed
2. Prefer staged removal over hard deletion:
   - deprecate -> route through facade/shim -> migrate callers -> delete
3. For deletions larger than trivial dead code, capture:
   - previous import/call sites
   - replacement module path
   - tests or checks proving parity
4. If a public route, payload, or CSS contract is being removed, include a compatibility note and rollback path in the slice verification block.
5. Maintain a removal ledger in this file during the run.

## Removal Entry Template

Use this exact structure for every meaningful removal:

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

- `pytest -q`: `<status>`
- `npm --prefix apps/web test`: `<status>`
- `npm --prefix apps/web run typecheck`: `<status>`

Current remaining hotspots:

| File | Lines | Why it still matters |
|---|---:|---|
| `<path>` | `<n>` | `<reason>` |

## Remaining Work Overview

### 1. <Gap title>

<Describe the unresolved problem and why it still matters.>

### 2. <Gap title>

<Describe the unresolved problem and why it still matters.>

## Implementation Sequencing

The remaining work should be executed in the order below.

Each slice should end with green tests before the next slice starts.

### <slice-id>. Slice <n>: <slice name>

Purpose:

- <goal>

Root problem:

- <root problem>

Files involved:

- `<file path>`
- `<file path>`

Implementation steps:

1. <step>
2. <step>
3. <step>

What stays the same:

- <contract preserved>
- <contract preserved>

Verification:

- `pytest -q`
- `<targeted test>`
- `<targeted test>`

Exit criteria:

- <exit criterion>
- <exit criterion>

### <slice-id>. Slice <n>: <slice name>

Purpose:

- <goal>

Root problem:

- <root problem>

Files involved:

- `<file path>`

Implementation steps:

1. <step>
2. <step>

What stays the same:

- <contract preserved>

Verification:

- `pytest -q`
- `<targeted test>`

Exit criteria:

- <exit criterion>

## Execution Order (Update After Each Run)

Start with the highest-priority remaining slices and proceed sequentially. Do not skip ahead unless the current slice is fully verified or explicitly blocked.

1. `<slice-id>` `<slice name>`
2. `<slice-id>` `<slice name>`
3. `<slice-id>` `<slice name>`

Re-read this file after every 2 completed slices and restate which slices remain.

## Verification Block Template

For every completed slice, include this exact structure in the working report or PR note:

```text
Verification Block - <slice-id>

Root cause
- <what made this area hard to maintain?>

Files changed
- <file list>

What changed
- <short description of the refactor moves>

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
pytest -q
npm --prefix apps/web test
npm --prefix apps/web run typecheck
```

Run these additionally when relevant:

```bash
ruff check .
```

Slice-specific emphasis:

- `<slice-id>`
  - `<test>`
  - `<test>`

Manual smoke checklist:

1. <smoke item>
2. <smoke item>
3. <smoke item>

## What Not To Do

Do not do the following during the remaining refactor:

- do not `<anti-goal>`
- do not `<anti-goal>`
- do not `<anti-goal>`

## Removal Ledger

Append removal entries here during implementation.

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

This section is mandatory.

If a generated refactor plan does not end with this section and the fenced prompt block below, the plan is incomplete and should be fixed before use.

Use this single prompt for the remaining implementation phase:

```text
You are working in the CoLearni repo.

STRICT INSTRUCTIONS:

Open and read docs/REFACTOR_PLAN.md now. This file is the source of truth.
You MUST implement refactor slices in the EXACT execution order listed there.
You MUST NOT claim a slice is complete until you produce a Verification Block with:
Root cause
Files changed
What changed
Commands run
Manual verification steps
Observed outcome

Before removing or replacing any file, function, route, schema, type, selector, compatibility shim, or docs surface, you MUST document the removal in docs/REFACTOR_PLAN.md using the Removal Entry Template.
For every removal, include:
Removed artifact
Reason for removal
Replacement
Reverse path
Compatibility impact
Verification

Removal policy:
- Prefer reversible staged removals over hard deletes.
- If rollback would be difficult, stop and introduce a facade/shim instead of deleting immediately.
- Do not delete public contracts without a compatibility note and rollback path.
- Do not claim the removal is complete until the replacement behavior is verified.

After every 2 slices OR if your context is compacted/summarized, re-open docs/REFACTOR_PLAN.md and restate which slices remain.
Work in small commits: chore(refactor): <slice-id> <short desc>.
If you discover a mismatch between current repo behavior and the assumptions in docs/REFACTOR_PLAN.md, STOP and update the plan before moving on.

When you finish a slice, include both:
1. The normal Verification Block for the slice
2. A summary of all Removal Entries added during that slice

START:

Read docs/REFACTOR_PLAN.md.
Begin with the current slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
Make sure you re-read docs/REFACTOR_PLAN.md before every move to the next slice. It can be dynamically updated. Check the latest version and continue.
```
