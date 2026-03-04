# Chat Codeblock Overflow Refactor Plan (READ THIS OFTEN)

Last updated: 2026-02-28

Archive snapshots:
- `docs/archive/REFACTOR_PLAN_2026-02-28_pre-chat-codeblock-overflow-plan.md`

Template source:
- `docs/prompt_templates/refactor_plan.md`

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

## Purpose

This document is the active execution plan for fixing the tutor chat layout bug where long, unbroken markdown code lines cause the chat message width to expand and make the full page horizontally scrollable.

The prior active refactor plan covered broader backend and docs cleanup. That work has been archived instead of mixed into this bug because:

- this issue is a narrow frontend containment regression
- the fix should stay CSS-first and small-PR sized
- widening scope would violate the template rule against unrelated refactor work

Use this document as the source of truth for the remaining bug-fix work. If implementation discovers that the width overflow comes from a different container than the files listed here, update this plan before widening scope.

## Inputs Used

This plan is based on:

- `docs/archive/REFACTOR_PLAN_2026-02-28_pre-chat-codeblock-overflow-plan.md`
- `docs/CODEX.md`
- `docs/ARCHITECTURE.md`
- `docs/PRODUCT_SPEC.md`
- `docs/GRAPH.md`
- `docs/prompt_templates/refactor_plan.md`
- current tutor UI and markdown rendering files as of 2026-02-28

## Executive Summary

The tutor UI is already in decent shape for a narrow fix:

- markdown rendering is centralized in `apps/web/components/markdown-content.tsx`
- tutor timeline layout is centralized in `apps/web/features/tutor/components/tutor-timeline.tsx`
- current codeblock styles already attempt local scrolling via `.markdown-content pre`

What is still materially missing is the full width-containment contract across the nested chat wrappers. Today:

- `.chat-content` resets `min-width: 0`, but still uses `overflow: visible`
- `.chat-response` and `.markdown-content` do not explicitly opt out of grid/flex automatic minimum sizing
- `.markdown-content pre` has `overflow-x: auto`, but not a fully explicit ownership contract for width, sizing, and scroll behavior
- there is no regression test or browser-level verification path for a long unbroken code line

The remaining work should stay narrow because the likely fix is still local to the web app CSS/render path and should not require backend changes.

The main unfinished areas are:

1. Width containment stops too early in the nested chat wrapper chain.
2. The codeblock frame has partial overflow handling but not a complete sizing contract.
3. There is no focused regression coverage for this specific layout failure.

## Non-Negotiable Constraints

These constraints apply to every remaining slice:

1. Keep the fix inside `apps/web` unless implementation proves the message payload contract itself is the problem.
2. Do not solve this by soft-wrapping fenced code lines. Long code must remain horizontally scrollable inside the code frame.
3. Preserve the current tutor/chat message structure and evidence/citation behavior.
4. Prefer CSS-first fixes. Only touch `MarkdownContent` markup if CSS alone cannot provide a stable hook.
5. Do not mix in JavaScript execution/rendering-in-chat feature work during this bug fix.
6. Add verification that distinguishes page-level overflow from codeblock-local overflow.

## Completed Work (Do Not Reopen Unless Blocked)

These areas are considered complete enough for this phase:

- `CB0A` Tutor layout decomposition into `apps/web/styles/*.css` and `features/tutor/*`
- `CB0B` Shared markdown rendering path via `apps/web/components/markdown-content.tsx`
- `CB0C` Baseline codeblock styling in `apps/web/styles/base.css`
- `CB0D` Prior broad chat overflow cleanup documented in `docs/PROGRESS.md`

These slices are not execution targets anymore unless a remaining slice directly depends on them.

## Remaining Slice IDs

Use these stable IDs in commits, reports, and verification blocks:

- `CB1` Width Containment Audit
- `CB2` Codeblock Scroll Ownership
- `CB3` Regression Coverage and Verification

## Decision Log For Remaining Work

These decisions are already made for the remaining phase:

1. Overflow ownership belongs to the code frame, not the page shell.
2. The parent chat column must remain width-bounded even when child code content has a huge max-content width.
3. `min-width: 0` and `max-width: 100%` should be applied intentionally along the flex/grid chain rather than relying on defaults.
4. If a structural hook is needed, add a small `pre`/`code` override in `MarkdownContent`; do not replace `react-markdown`.
5. JavaScript rendering inside chat is a separate feature track and not part of this bug fix.

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

- `pytest -q`: not run in this planning-only pass
- `npm --prefix apps/web test`: not run in this planning-only pass
- `npm --prefix apps/web run typecheck`: not run in this planning-only pass

Current remaining hotspots:

| File | Lines | Why it still matters |
|---|---:|---|
| `apps/web/styles/base.css` | 422 | Holds the current `.markdown-content pre` and `.markdown-content pre code` overflow contract. |
| `apps/web/styles/tutor.css` | 668 | Holds the chat wrapper chain; `.chat-content` currently keeps `overflow: visible`. |
| `apps/web/components/markdown-content.tsx` | 18 | Central markdown renderer; currently provides no custom `pre`/`code` hook or additional containment classes. |
| `apps/web/components/chat-response.tsx` | 115 | Wraps assistant markdown and hint sections; may need explicit width containment if grid defaults are participating. |
| `apps/web/features/tutor/components/tutor-timeline.tsx` | 101 | Defines the assistant message wrapper chain from `.chat-message` to `.chat-content`. |

## Remaining Work Overview

### 1. Width containment ends before the markdown leaf

The chat message layout is a nested flex/grid chain:

- `.chat-message` in `apps/web/styles/tutor.css`
- `.chat-content` in `apps/web/styles/tutor.css`
- `.chat-response` in `apps/web/styles/tutor.css`
- `.markdown-content` in `apps/web/styles/base.css`
- `pre > code` emitted by `apps/web/components/markdown-content.tsx`

Only part of that chain explicitly resets intrinsic sizing. Long unbroken code lines can therefore still participate in min-content sizing and push overflow pressure outward instead of keeping it inside the code frame.

### 2. The code frame does not fully own horizontal overflow yet

`.markdown-content pre` already has `overflow-x: auto`, `overflow-y: auto`, and `max-width: 100%`, but that is not enough when parent grid items still use automatic minimum widths or when the code frame itself does not explicitly claim the available inline size.

Likely fix points:

- add `min-width: 0` / `max-width: 100%` to the intermediate chat wrappers
- make the fenced code frame explicitly width-bounded with `width: 100%` and `box-sizing: border-box`
- keep `pre code` non-wrapping while ensuring the scrollport stays on `pre`

### 3. There is no focused regression harness for this bug

Current frontend tests only cover reducer/API logic in a Node environment. There is no browser-level assertion for:

- page horizontal scroll stays unchanged
- code frame itself becomes horizontally scrollable
- standard prose markdown is unaffected

That gap makes this bug easy to reintroduce during future CSS cleanup.

## Implementation Sequencing

The remaining work should be executed in the order below.

Each slice should end with green tests before the next slice starts.

### CB1. Slice 1: Width Containment Audit

Purpose:

- identify the exact wrapper where intrinsic width escapes the chat column

Root problem:

- the chat layout contains nested flex/grid items, but only `.chat-content` currently resets min-size and it still leaves overflow visible

Files involved:

- `apps/web/styles/tutor.css`
- `apps/web/styles/base.css`
- `apps/web/features/tutor/components/tutor-timeline.tsx`
- `apps/web/components/chat-response.tsx`

Implementation steps:

1. Trace the width/overflow chain from `.chat-message` through `.markdown-content`.
2. Add explicit containment rules to intermediate wrappers that still rely on automatic minimum sizing.
3. Decide whether `.chat-content` should use `overflow-x: hidden` or `overflow-x: clip` after the inner code frame is hardened.

What stays the same:

- chat message max width remains `48rem`
- user and assistant content structure stays the same
- non-code markdown layout remains visually consistent

Verification:

- `npm --prefix apps/web run typecheck`
- manual reproduction with a tutor message containing a single very long unbroken fenced code line
- confirm `document.documentElement.scrollWidth === document.documentElement.clientWidth`

Exit criteria:

- the page no longer becomes horizontally scrollable from the reproduction case
- the chat message stays within its intended max width

### CB2. Slice 2: Codeblock Scroll Ownership

Purpose:

- make the fenced code frame itself the only horizontal scroll container

Root problem:

- `pre` already scrolls, but its sizing contract is incomplete and may still allow max-content width to leak into layout calculations

Files involved:

- `apps/web/styles/base.css`
- `apps/web/components/markdown-content.tsx`

Implementation steps:

1. Update `.markdown-content pre` so it explicitly owns width with `width: 100%`, `max-width: 100%`, `min-width: 0`, and `box-sizing: border-box`.
2. Keep `pre code` non-wrapping and, if needed, render it as a block with `min-width: max-content` so horizontal scroll stays local to the `pre`.
3. If CSS selectors are too generic, add a tiny `ReactMarkdown` override to attach a dedicated fenced-code class without changing markdown semantics.

What stays the same:

- inline code styling remains separate from fenced code styling
- KaTeX and standard markdown rendering stay on the existing path

Verification:

- `npm --prefix apps/web run typecheck`
- manual check that the code frame shows a local horizontal scrollbar for the reproduction case
- manual check that normal paragraphs and inline code still wrap/read normally

Exit criteria:

- long code lines scroll inside the code frame only
- no visual clipping regression on bordered code frames

### CB3. Slice 3: Regression Coverage and Verification

Purpose:

- leave behind a repeatable proof that page-level overflow is fixed and codeblock-local overflow still works

Root problem:

- the repo has no current browser UI regression coverage for layout overflow bugs

Files involved:

- `apps/web/package.json`
- `apps/web/vitest.config.ts`
- `apps/web/components/markdown-content.tsx`
- `apps/web/features/tutor/components/tutor-timeline.tsx`
- `apps/web/styles/base.css`
- `apps/web/styles/tutor.css`

Implementation steps:

1. Add the smallest viable frontend regression harness for this bug:
   - preferred: a browser-based assertion that page scroll width does not exceed viewport width while the code frame itself overflows
   - fallback: a component-level render test plus documented manual verification if browser harness setup is too large for this PR
2. Add a fixed reproduction fixture containing one very long unbroken fenced code line.
3. Record the manual verification recipe in the slice verification block so future CSS passes can replay it quickly.

What stays the same:

- existing reducer/API unit tests remain untouched unless shared config must expand
- no backend test scope is added for this frontend-only bug

Verification:

- `npm --prefix apps/web test`
- `npm --prefix apps/web run typecheck`
- manual browser verification on desktop width and mobile width

Exit criteria:

- automated coverage exists for the chosen regression path
- manual verification recipe is short, repeatable, and matches the implemented fix

## Execution Order (Update After Each Run)

Start with the highest-priority remaining slices and proceed sequentially. Do not skip ahead unless the current slice is fully verified or explicitly blocked.

1. `CB1` Width Containment Audit
2. `CB2` Codeblock Scroll Ownership
3. `CB3` Regression Coverage and Verification

Re-read this file after every 2 completed slices and restate which slices remain.
