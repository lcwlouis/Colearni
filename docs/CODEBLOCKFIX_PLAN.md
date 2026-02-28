# Chat Codeblock Overflow Refactor Plan (READ THIS OFTEN)

Last updated: 2026-02-28

Archive snapshots:
- `docs/archive/CODEBLOCKFIX_PLAN_2026-02-28_pre-rewrite.md`
- `docs/archive/REFACTOR_PLAN_2026-02-28_pre-chat-codeblock-overflow-plan.md`

Template source:
- `docs/prompt_templates/refactor_plan.md`

## Plan Completeness Checklist

This plan is not ready to execute unless it includes all of the following:

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
8. This document is incomplete unless it ends with a section titled:
   - `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`
   - followed by a fenced code block containing the execution prompt

## Purpose

This document is the active execution plan for fixing the tutor chat layout bug where a markdown fenced codeblock with a very long unbroken line stretches the chat bubble and makes the UI horizontally scrollable.

This plan exists instead of extending the broader active refactor plan because:

- the issue is isolated to the web chat render path
- the likely fix is a small CSS-first change
- the earlier `docs/CODEBLOCKFIX_PLAN.md` draft was incomplete and did not satisfy the current template requirements

Use this document as the source of truth for the remaining bug-fix work. If implementation shows that the overflow is escaping through a different layout container than the files listed here, update this plan before widening scope.

## Inputs Used

This plan is based on:

- `docs/archive/CODEBLOCKFIX_PLAN_2026-02-28_pre-rewrite.md`
- `docs/archive/REFACTOR_PLAN_2026-02-28_pre-chat-codeblock-overflow-plan.md`
- `docs/CODEX.md`
- `docs/ARCHITECTURE.md`
- `docs/PRODUCT_SPEC.md`
- `docs/GRAPH.md`
- `docs/prompt_templates/refactor_plan.md`
- current web chat render path and verification status as of 2026-02-28

## Executive Summary

The current codebase is already structured well enough for a narrow fix:

- markdown rendering is centralized in `apps/web/components/markdown-content.tsx`
- assistant and user message rendering converges in the tutor timeline and chat response wrappers
- codeblocks already attempt local scrolling through `.markdown-content pre { overflow-x: auto; max-width: 100%; }`
- `.chat-content` already uses `min-width: 0`, which means the repo is close to the correct containment model

What is still materially missing is a complete width contract across the nested wrapper chain:

- the current attempted fix changed `.chat-content` to `overflow: hidden`, which suppresses page-level blowout by clipping descendants at the wrong layer
- `.chat-response` and `.markdown-content` do not explicitly opt out of intrinsic min-content sizing
- the fenced code frame does not fully assert ownership of its own inline size
- the repo has no browser-capable automated layout test harness for this class of overflow regression

The main unfinished areas are:

1. Width containment stops before the markdown leaf.
2. The `pre` scrollport does not fully own horizontal overflow.
3. Regression coverage for layout overflow is limited by the current Node-only frontend test setup.

## Non-Negotiable Constraints

These constraints apply to every remaining slice:

1. Keep the fix inside `apps/web` unless implementation proves the message payload contract itself is responsible.
2. Do not solve this by wrapping or mutating fenced code content. Long code lines must remain horizontally scrollable inside the code frame.
3. Preserve the existing assistant response contract, citations, and chat message semantics.
4. Prefer CSS-first changes. Add a `ReactMarkdown` `pre`/`code` override only if CSS alone cannot provide stable hooks.
5. Do not mix JavaScript execution/rendering-in-chat feature work into this bug fix.
6. Keep the change small enough for a single PR-sized pass.

## Completed Work (Do Not Reopen Unless Blocked)

These areas are considered complete enough for this phase:

- `CB0A` Shared markdown rendering path through `apps/web/components/markdown-content.tsx`
- `CB0B` Tutor message wrappers centralized in `apps/web/features/tutor/components/tutor-timeline.tsx` and `apps/web/components/chat-response.tsx`
- `CB0C` Baseline fenced-code styling already present in `apps/web/styles/base.css`
- `CB0D` Baseline web verification currently green for `npm --prefix apps/web test` and `npm --prefix apps/web run typecheck`

These slices are not execution targets anymore unless a remaining slice directly depends on them.

## Remaining Slice IDs

Use these stable IDs in commits, reports, and verification blocks:

- `CB1` Width Containment Audit
- `CB2` Codeblock Scroll Ownership
- `CB3` Regression Coverage and Verification

## Decision Log For Remaining Work

These decisions are already made for the remaining phase:

1. Overflow ownership belongs to the fenced code frame, not the page shell.
2. The parent chat column must stay width-bounded even when a child code line has extreme max-content width.
3. `min-width: 0` and `max-width: 100%` should be applied intentionally along the chat wrapper chain instead of relying on browser defaults.
4. `.chat-content` and other outer wrappers must not become the effective horizontal overflow sink; clipping at that layer is not an acceptable end state.
5. If markup changes are needed, they should add stable classes or component hooks around fenced code only; do not replace `react-markdown`.
6. A true JavaScript execution surface in chat is a separate feature track and must not be slipped into this bug fix.

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

- `pytest -q`: failing before this bug-fix work; `tests/api/test_api_docs_sync.py::test_api_doc_endpoint_headings_match_openapi` reports that OpenAPI includes `POST /workspaces/{ws_id}/chat/respond/stream` but the docs headings do not
- `npm --prefix apps/web test`: passing
- `npm --prefix apps/web run typecheck`: passing
- manual UI check after the first containment attempt: page-level overflow is reduced, but fenced code inside the hint card is visually clipped because `.chat-content` now uses `overflow: hidden`

Current remaining hotspots:

| File | Lines | Why it still matters |
|---|---:|---|
| `apps/web/styles/tutor.css` | `668` | Owns the chat wrapper chain; `.chat-content` currently uses `overflow: hidden`, which prevents page blowout by clipping the codeblock at the wrong layer. |
| `apps/web/styles/base.css` | `422` | Holds `.markdown-content`, `.markdown-content pre`, and `.markdown-content pre code`; current rules are close but incomplete for width ownership. |
| `apps/web/components/markdown-content.tsx` | `18` | Central markdown renderer; currently exposes no dedicated fenced-code classes or `components` overrides. |
| `apps/web/components/chat-response.tsx` | `115` | Assistant markdown/hint wrapper; may need explicit width containment if grid defaults are participating. |
| `apps/web/features/tutor/components/tutor-timeline.tsx` | `101` | Defines the `.chat-message` to `.chat-content` wrapper path where max width must stay intact. |
| `apps/web/vitest.config.ts` | `14` | Frontend tests run in `node` only, so real layout assertions require either a lightweight new browser path or a manual smoke checklist. |

## Remaining Work Overview

### 1. Width containment ends before the markdown leaf

The chat render path is a nested flex/grid chain:

- `.chat-message`
- `.chat-content`
- `.chat-response`
- `.markdown-content`
- `pre > code`

Only some of those wrappers currently opt out of intrinsic min-content sizing. A very long unbroken code token can still pressure ancestors to grow instead of keeping overflow local to the code frame.

The latest screenshot confirms that the first containment attempt solved the wrong problem at the wrong layer:

- page-level horizontal overflow is reduced
- the codeblock is not clearly owning its own scroll behavior
- the hint-card path now clips the code frame because `.chat-content` is hiding descendant overflow

### 2. The code frame does not fully own horizontal overflow yet

The current `pre` styles already include `overflow-x: auto`, but they do not fully state:

- who owns the scrollport
- how the code frame claims available width
- how the inner `code` element should size relative to the scroll container

That leaves room for the browser to honor max-content width too early in layout.

### 3. Regression coverage is constrained by the current test setup

The web app has only Node-based Vitest coverage today. That is enough for reducers and API client logic, but not for proving real overflow metrics in a browser engine.

The implementation should therefore leave behind:

- an automated regression around any new fenced-code class/markup contract
- a short manual browser reproduction checklist for the actual layout behavior

## Implementation Sequencing

The remaining work should be executed in the order below.

Each slice should end with the best available verification before the next slice starts.

### CB1. Slice 1: Width Containment Audit

Purpose:

- identify the exact wrapper where intrinsic width escapes the chat column and harden the containment chain

Root problem:

- the current outer-wrapper containment is incomplete and partly incorrect: `.chat-content` is clipping overflow, but the underlying max-content pressure is still not fully transferred to the `pre` scroll container

Files involved:

- `apps/web/styles/tutor.css`
- `apps/web/styles/base.css`
- `apps/web/components/chat-response.tsx`

Implementation steps:

1. Trace the width path from `.chat-message` through `.markdown-content` and document which wrappers rely on automatic min-content sizing.
2. Replace the current `.chat-content { overflow: hidden; }` workaround with non-clipping containment rules unless a narrower wrapper-specific rule is proven necessary.
3. Add explicit containment rules such as `min-width: 0` and `max-width: 100%` to intermediate wrappers that still allow width escape.
4. Audit the hint-card path (`.chat-hint-section` and `.chat-hint-content`) so nested assistant markdown does not reintroduce clipping.

What stays the same:

- chat message max width remains `48rem`
- normal prose markdown and user message wrapping remain unchanged
- citation and hint rendering behavior remains unchanged

Verification:

- `npm --prefix apps/web test`
- `npm --prefix apps/web run typecheck`
- manual reproduction with a tutor message containing one extremely long unbroken fenced code line

Exit criteria:

- the chat message stays within its intended max width
- page-level horizontal scrolling is gone for the reproduction case
- outer chat wrappers are no longer clipping the fenced code content

### CB2. Slice 2: Codeblock Scroll Ownership

Purpose:

- make the fenced code frame the only horizontal scroll container for long code lines

Root problem:

- `pre` already scrolls, but its sizing contract is incomplete and can still leak max-content width into ancestor layout

Files involved:

- `apps/web/styles/base.css`
- `apps/web/components/markdown-content.tsx`

Implementation steps:

1. Update fenced-code styles so the scroll container explicitly owns its width, including `width: 100%`, `max-width: 100%`, `min-width: 0`, and `box-sizing: border-box` on the `pre` path if needed.
2. Keep `pre code` non-wrapping and, if required, render it as a block-sized content box so scroll remains local to the `pre`.
3. Verify the same behavior inside nested containers such as the collapsible hint card, not only in the top-level assistant body.
4. If selector specificity or inline-vs-fenced separation becomes ambiguous, add a minimal `ReactMarkdown` component override to attach dedicated fenced-code classes without changing markdown semantics.

What stays the same:

- inline code styling remains distinct from fenced code styling
- KaTeX and normal markdown rendering stay on the existing `MarkdownContent` path

Verification:

- `npm --prefix apps/web test`
- `npm --prefix apps/web run typecheck`
- manual check that the fenced codeblock shows a local horizontal scrollbar for the reproduction case

Exit criteria:

- long code lines scroll inside the code frame only
- bordered code frames do not visually clip or exceed their parent width
- the hint-card reproduction from the screenshot behaves the same as the main assistant body

### CB3. Slice 3: Regression Coverage and Verification

Purpose:

- leave behind repeatable proof for the containment contract even though the repo lacks a real browser test harness today

Root problem:

- current frontend tests run in a Node environment and cannot directly assert browser layout overflow metrics

Files involved:

- `apps/web/components/markdown-content.tsx`
- `apps/web/lib/api/types.ts`
- `apps/web/features/tutor/types.ts`
- `apps/web/vitest.config.ts`

Implementation steps:

1. If CB2 adds dedicated fenced-code classes or markup, add a targeted frontend test that proves the render contract for fenced code versus inline code.
2. Use the smallest viable test path that fits the current repo:
   - preferred: server-render or lightweight component-level assertion using existing tooling
   - only add a browser runner if the change stays small and justified
3. Record a mandatory manual smoke test that validates page containment and local code scrolling on desktop and a narrow mobile viewport.

What stays the same:

- existing reducer/API tests remain untouched unless shared config must expand
- no backend schema or route changes are introduced for this frontend-only fix

Verification:

- `npm --prefix apps/web test`
- `npm --prefix apps/web run typecheck`
- manual browser verification on desktop and narrow viewport widths

Exit criteria:

- automated coverage exists for any new render hook or class contract introduced by the fix
- the manual reproduction recipe is short, repeatable, and matches the implemented behavior

## Execution Order (Update After Each Run)

Start with the highest-priority remaining slices and proceed sequentially. Do not skip ahead unless the current slice is fully verified or explicitly blocked.

1. ~~`CB1` Width Containment Audit~~ ✅ done (reopened and re-fixed: removed outer clipping, added hint-card containment)
2. ~~`CB2` Codeblock Scroll Ownership~~ ✅ done (reopened and verified: explicit width + block code)
3. ~~`CB3` Regression Coverage and Verification~~ ✅ done (reopened: updated smoke checklist with hint-card path)

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

Current note:

- `pytest -q` is already red before this bug-fix work because `tests/api/test_api_docs_sync.py` is out of sync with the streaming chat route docs. Record that failure as pre-existing unless the slice touches API docs.

Slice-specific emphasis:

- `CB1`
  - reproduce the overflow with one long fenced code line
  - verify the chat bubble remains within `48rem`
  - verify removing outer clipping does not reintroduce page-wide scroll
- `CB2`
  - verify only the fenced code frame gains a horizontal scrollbar
  - verify inline code and normal paragraphs still wrap/read normally
  - verify the hint card does not crop the code frame
- `CB3`
  - verify any new fenced-code class or render hook is covered by an automated test
  - verify the manual smoke recipe works on desktop and narrow width

Manual smoke checklist:

1. Send or inject a tutor response containing a fenced codeblock with one very long unbroken line and confirm the overall chat UI does not widen.
2. Confirm the codeblock itself can be horizontally scrolled without clipping its border/background.
3. Repeat the same reproduction inside a collapsible hint section and confirm the nested codeblock is not cropped.
4. Confirm ordinary markdown paragraphs, inline code, hints, and citations still render normally.

## What Not To Do

Do not do the following during the remaining refactor:

- do not change backend schemas or chat payload contracts to solve this CSS bug
- do not wrap or truncate fenced code content to hide the overflow
- do not add JavaScript execution, iframes, or sandboxed runtime behavior as part of this fix

## Removal Ledger

```text
Removal Entry - CB1

Removed artifact
- `.chat-content { overflow: hidden; }` selector property in `apps/web/styles/tutor.css`

Reason for removal
- Clipping at the wrong layer; `.chat-content` was acting as the overflow sink instead of letting each fenced code `pre` frame own its own horizontal scroll via `overflow-x: auto`. This caused fenced code inside hint cards to be visually clipped.

Replacement
- Non-clipping containment via `min-width: 0` on every grid/flex item in the chat wrapper chain (`.chat-content`, `.chat-response`, `.chat-hint-section`, `.markdown-content`, `.markdown-content pre`). The `pre` element's existing `overflow-x: auto` is the sole scroll container.

Reverse path
- Add `overflow: hidden;` back to `.chat-content` in `apps/web/styles/tutor.css`

Compatibility impact
- Internal CSS contract only; no public API or payload change. Minor: if any other content was relying on `.chat-content` clipping, it would now be visible instead.

Verification
- `npm --prefix apps/web test`, `npm --prefix apps/web run typecheck`
- Manual: fenced code in main body AND hint card scrolls locally without clipping
```

## Mandatory Manual Smoke Test (CB3)

Perform these steps in a browser after deploying or running the dev server:

1. Open the tutor chat and send (or inject) a message containing:
   ````
   ```python
   x = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
   ```
   ````
2. **Desktop viewport (≥1200px):** Confirm the chat bubble stays within its 48rem max-width. No page-level horizontal scrollbar should appear.
3. **Narrow viewport (375px, e.g. iPhone SE):** Confirm the same containment holds. The codeblock should show a local horizontal scrollbar inside the `pre` frame.
4. Confirm the codeblock border/background is not visually clipped or overflowing its parent.
5. **Hint-card path:** Inject or trigger a response with a collapsible hint containing the same long fenced codeblock. Expand the hint. Confirm the nested codeblock is **not cropped** and scrolls locally, identical to the main body behavior.
6. Confirm ordinary markdown paragraphs, inline code (`like this`), hints, and citations still render normally.
7. Confirm the local scrollbar inside the codeblock is functional and scrolls the long line.

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

```text
You are working in the CoLearni repo.

STRICT INSTRUCTIONS:

Open and read docs/CODEBLOCKFIX_PLAN.md now. This file is the source of truth.
You MUST implement refactor slices in the EXACT execution order listed there.
You MUST NOT claim a slice is complete until you produce a Verification Block with:
Root cause
Files changed
What changed
Commands run
Manual verification steps
Observed outcome

Before removing or replacing any file, function, route, schema, type, selector, compatibility shim, or docs surface, you MUST document the removal in docs/CODEBLOCKFIX_PLAN.md using the Removal Entry Template.
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

After every 2 slices OR if your context is compacted/summarized, re-open docs/CODEBLOCKFIX_PLAN.md and restate which slices remain.
Work in small commits: chore(refactor): <slice-id> <short desc>.
If you discover a mismatch between current repo behavior and the assumptions in docs/CODEBLOCKFIX_PLAN.md, STOP and update the plan before moving on.

Verification policy for this run:
- Run pytest -q, npm --prefix apps/web test, and npm --prefix apps/web run typecheck at the end of each slice.
- pytest -q is currently expected to fail on tests/api/test_api_docs_sync.py because the streaming chat route docs are out of sync; record that as pre-existing unless you changed that area.

When you finish a slice, include both:
1. The normal Verification Block for the slice
2. A summary of all Removal Entries added during that slice

START:

Read docs/CODEBLOCKFIX_PLAN.md.
Begin with the current slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
Make sure you re-read docs/CODEBLOCKFIX_PLAN.md before every move to the next slice. It can be dynamically updated. Check the latest version and continue.
```
