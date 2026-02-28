# Frontend Package Update Plan

Last updated: 2026-02-28

Archive snapshots:
- `docs/archive/UPDATE_FE_PACKAGE_2026-02-28_initial.md`

Template usage:
- This file is the active execution plan for the frontend security and dependency update pass.
- Archive the previous active version of this file before rewriting it.
- Keep the final `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)` section intact.

## Plan Completeness Checklist

This plan is ready to execute because it includes:

1. archive snapshot path(s)
2. current verification status
3. ordered slice list with stable IDs
4. verification block template
5. removal entry template
6. final section named `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`

## Non-Negotiable Run Rules

1. Re-open and re-read this file:
   - at the start of the run
   - after every 2 completed slices
   - after any context compaction or summary boundary
   - before marking a slice complete
2. Do not use `npm audit fix --force` as the implementation strategy.
3. Keep slices narrow:
   - prefer one dependency family at a time
   - keep manual source edits reviewable and isolate lockfile churn
4. Every completed slice must produce a `Verification Block`.
5. If clearing an advisory requires a wider jump than this plan assumes, stop and update this file before widening scope.
6. This plan is for package/security maintenance only. Do not mix in unrelated frontend or backend feature work.
7. The plan is incomplete unless it ends with `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)` followed by exactly one fenced code block.

## Purpose

This document is the active execution plan for the `apps/web` dependency upgrade pass triggered by the 2026-02-28 `npm audit` report.

Earlier repo planning docs in `docs/REFACTOR_PLAN.md`, `docs/PLAN.md`, and related archive files are broader backend/refactor workstreams. This new plan exists because the current task is narrower: remove the known frontend advisories without widening scope into unrelated architecture changes.

## Inputs Used

This plan is based on:

- `docs/prompt_templates/refactor_plan.md`
- `docs/CODEX.md`
- `docs/ARCHITECTURE.md`
- `docs/PRODUCT_SPEC.md`
- `docs/GRAPH.md`
- the user-provided `npm audit` report captured on 2026-02-28
- current repository layout and verification status as of 2026-02-28
- `apps/web/package.json`
- `apps/web/package-lock.json`
- `apps/web/next.config.mjs`
- `apps/web/vitest.config.ts`
- local dependency tree inspection from `npm --prefix apps/web ls next eslint-config-next vitest vite esbuild @next/eslint-plugin-next glob minimatch @typescript-eslint/parser @typescript-eslint/typescript-estree`

## Executive Summary

The frontend app is already in stable working shape: tests pass, the typecheck passes, lint passes with only existing warnings, and the production build succeeds. The remaining issue is that `apps/web` pins exact package versions that resolve to known-vulnerable `next`, `vite`/`esbuild`, `glob`, and `minimatch` chains.

The upgrade should stay narrow because the app surface is small and the risk comes from pinned framework/tooling versions, not from product logic. The main job is to move to the smallest safe dependency set, keep `next` and `eslint-config-next` aligned, and verify that the existing `/api/*` rewrite, build output, and Vitest suite still behave the same.

The main unfinished areas are:

1. direct dependency pins in `apps/web/package.json` lag the security-fixed versions suggested by the audit
2. transitive lint/test dependencies may still need targeted cleanup after the direct version bump
3. framework/toolchain patch updates still need runtime and build verification against the current app behavior

## Non-Negotiable Constraints

These constraints apply to every remaining slice:

1. Preserve current user-visible behavior for the Next app routes, the `/api/:path*` proxy rewrite, and the existing Vitest suite.
2. Prefer the smallest version moves that clear advisories within the current major lines before considering broader upgrades.
3. Keep `next` and `eslint-config-next` on matching versions unless a documented upstream incompatibility forces a different choice.
4. Treat the existing lint warnings in `apps/web/components/concept-graph.tsx` and `apps/web/lib/auth/auth-context.tsx` as baseline; do not hide them or misclassify them as upgrade regressions.
5. Run the verification commands in this file after every non-docs slice before moving on.

## Completed Work (Do Not Reopen Unless Blocked)

These areas are considered complete enough for this phase:

- `FEPKG-BASE-01` mapped the audit report to the current installed tree: `next@14.2.5`, `vitest@2.1.8 -> vite@5.4.21 -> esbuild@0.21.5`, `eslint-config-next@14.2.5 -> @next/eslint-plugin-next@14.2.5 -> glob@10.3.10`, and `@typescript-eslint/typescript-estree@7.2.0 -> minimatch@9.0.3`
- `FEPKG-BASE-02` captured the pre-upgrade verification baseline: `pytest -q`, `npm --prefix apps/web test`, `npm --prefix apps/web run typecheck`, `npm --prefix apps/web run lint`, and `npm --prefix apps/web run build`

These slices are not execution targets anymore unless a remaining slice directly depends on them.

## Remaining Slice IDs

Use these stable IDs in commits, reports, and verification blocks:

- `FEPKG-01` direct package bump and lockfile refresh
- `FEPKG-02` transitive advisory cleanup and override minimization
- `FEPKG-03` compatibility fixes, smoke verification, and closeout

## Decision Log For Remaining Work

These decisions are already made for the remaining phase:

1. Do not run `npm audit fix --force`; make explicit version changes instead.
2. Attempt a same-major remediation first:
   - `next` and `eslint-config-next` stay on the 14.2.x line unless that line cannot clear the advisories
   - `vitest` stays on the 2.1.x line unless the audit tree proves that line cannot clear the `vite`/`esbuild` issue
3. Use `package.json` changes first and add `overrides` only when a vulnerable transitive dependency cannot be cleared by a compatible direct upgrade.
4. Only touch `apps/web/next.config.mjs`, `apps/web/vitest.config.ts`, or app/test source files if the package bump causes a concrete compatibility break.
5. Keep rollback simple:
   - each slice should be independently revertible
   - any temporary override or compatibility shim must be documented in the removal ledger before later deletion

## Removal Safety Rules

These rules apply whenever a remaining slice removes, replaces, inlines, or archives code:

1. Do not remove a file, function, script, config option, package override, or compatibility shim without recording:
   - what is being removed
   - why removal is safe
   - what replaces it
   - how to restore it if rollback is needed
2. Prefer staged removal over hard deletion:
   - add override or shim
   - migrate or verify callers
   - delete only when no longer needed
3. For deletions larger than trivial dead code, capture:
   - previous import, call, or config sites
   - replacement path or version
   - tests or checks proving parity
4. If a script contract changes, include a compatibility note and rollback path in the slice verification block.
5. Maintain a removal ledger in this file during implementation.

## Removal Entry Template

Use this exact structure for every meaningful removal:

```text
Removal Entry - <slice-id>

Removed artifact
- <file / function / route / schema / selector / override / script>

Reason for removal
- <why it was dead, duplicated, or replaced>

Replacement
- <new file/module/path/version or "none" if true deletion>

Reverse path
- <exact steps to restore or revert>

Compatibility impact
- <public/internal, none/minor/major>

Verification
- <tests or manual checks proving the replacement works>
```

## Current Verification Status

Current repo verification status:

- `pytest -q`: passing
- `npm --prefix apps/web test`: passing (`54` tests across `9` Vitest files); emits a Vite CJS Node API deprecation warning on `vitest@2.1.8`
- `npm --prefix apps/web run typecheck`: passing

Additional frontend baseline:

- `npm --prefix apps/web run lint`: passing with `3` existing `react-hooks/exhaustive-deps` warnings
- `npm --prefix apps/web run build`: passing; static routes `/`, `/_not-found`, `/graph`, `/kb`, `/login`, and `/tutor` build successfully with the same `3` warnings

Current remaining hotspots:

| File | Lines | Why it still matters |
|---|---:|---|
| `apps/web/package.json` | `46` | Pins the direct dependency versions that force the audit remediation work. |
| `apps/web/package-lock.json` | `8397` | Encodes the vulnerable transitive tree and will carry most of the upgrade diff. |
| `apps/web/next.config.mjs` | `14` | Holds the `/api/:path*` rewrite and `experimental.proxyTimeout` config that must still validate after the Next update. |
| `apps/web/vitest.config.ts` | `17` | Owns the Vitest/Vite configuration that may need a compatibility tweak if the test runner chain changes. |
| `apps/web/components/concept-graph.tsx` | `446` | Contains two existing hook warnings surfaced by both lint and build; these are baseline, not part of the security fix. |
| `apps/web/lib/auth/auth-context.tsx` | `153` | Contains one existing hook warning surfaced by both lint and build; this is baseline, not part of the security fix. |

## Remaining Work Overview

### 1. Direct dependency pins are behind the secure patch line

`apps/web/package.json` uses exact versions for `next`, `eslint-config-next`, and `vitest`. That makes `npm audit` recommend `--force` jumps because the manifest itself forbids safer patch versions. The first slice must move those direct pins and regenerate the lockfile before any deeper cleanup is attempted.

### 2. The lint and test toolchain still has transitive advisory risk

Even after the direct bump, `glob`, `minimatch`, `vite`, and `esbuild` need to be re-checked in the resolved tree. The second slice exists so that any remaining transitive issue is handled deliberately instead of forcing a framework-major upgrade into the same PR.

### 3. Security patches still need compatibility proof

The current frontend depends on a small amount of framework configuration:

- a Next rewrite proxy in `apps/web/next.config.mjs`
- image usage via `next/image`
- Vitest config in `apps/web/vitest.config.ts`

Patch updates in these toolchains can still alter validation or runtime behavior, so the final slice is a compatibility and smoke pass rather than a version bump only.

## Implementation Sequencing

The remaining work should be executed in the order below.

Each slice should end with green tests before the next slice starts.

### FEPKG-01. Slice 1: Direct package bump and lockfile refresh

Purpose:

- move the declared frontend dependencies to the smallest safe patch versions that can clear the known `next` and `esbuild`-chain advisories

Root problem:

- exact manifest pins currently lock the app onto vulnerable versions and force `npm audit` to suggest wider `--force` upgrades than the repo needs

Files involved:

- `apps/web/package.json`
- `apps/web/package-lock.json`
- `apps/web/README.md` (only if command or setup guidance must change)

Implementation steps:

1. Update `next` and `eslint-config-next` together to the smallest available secure version on the intended line, and update `vitest` to the smallest secure patch that resolves the `vite`/`esbuild` chain.
2. Regenerate `apps/web/package-lock.json` from the updated manifest and capture the before/after resolved versions with `npm --prefix apps/web ls`.
3. Re-run the frontend verification commands and compare results against the baseline warnings and build output.

What stays the same:

- the existing `apps/web` route structure and user flows
- the `/api/:path*` rewrite contract in `apps/web/next.config.mjs`
- the existing script surface in `apps/web/package.json` unless a tool upgrade proves that a script must change

Verification:

- `pytest -q`
- `npm --prefix apps/web test`
- `npm --prefix apps/web run typecheck`
- `npm --prefix apps/web run lint`
- `npm --prefix apps/web run build`
- `npm --prefix apps/web ls next eslint-config-next vitest vite esbuild`
- `npm audit`

Exit criteria:

- direct package pins are updated and the lockfile is regenerated cleanly
- the `next` and `esbuild` advisories are cleared or reduced to a smaller documented residual set
- no new lint warnings or build failures appear

### FEPKG-02. Slice 2: Transitive advisory cleanup and override minimization

Purpose:

- remove any remaining `glob` or `minimatch` advisories without widening scope into an unnecessary framework-major or lint-system migration

Root problem:

- the advisory tree includes transitive packages under the Next ESLint and TypeScript parser chains, and those may need targeted cleanup even after the direct version bump

Files involved:

- `apps/web/package.json`
- `apps/web/package-lock.json`
- `docs/UPDATE_FE_PACKAGE.md` (for removal ledger or plan updates if the approach changes)

Implementation steps:

1. Inspect the post-slice-1 dependency tree with `npm --prefix apps/web ls glob minimatch @next/eslint-plugin-next @typescript-eslint/parser @typescript-eslint/typescript-estree`.
2. Prefer compatible upstream package bumps first; if the remaining issue is purely transitive, add the narrowest possible `overrides` entry and document why it is safe.
3. Re-run `npm audit`, `lint`, and `build`, and update the removal ledger if an override or temporary shim is introduced.

What stays the same:

- the existing `next lint`-based lint entrypoint unless the upgraded toolchain makes it impossible to keep
- the current lint warning baseline and ESLint rule coverage

Verification:

- `pytest -q`
- `npm --prefix apps/web test`
- `npm --prefix apps/web run typecheck`
- `npm --prefix apps/web run lint`
- `npm --prefix apps/web run build`
- `npm --prefix apps/web ls glob minimatch @next/eslint-plugin-next @typescript-eslint/parser @typescript-eslint/typescript-estree`
- `npm audit`

Exit criteria:

- `glob` and `minimatch` advisories are cleared, or any residual issue is documented with exact upstream blocker details
- any `overrides` entry is narrowly scoped, justified, and rollback-ready
- the lint and build outputs remain at baseline or better

### FEPKG-03. Slice 3: Compatibility fixes, smoke verification, and closeout

Purpose:

- resolve any config fallout caused by the dependency updates and finish with a reproducible, documented frontend verification pass

Root problem:

- even patch-level updates can change Next config validation, rewrite behavior, image handling, or Vitest defaults, so the dependency work is not done until the app is smoke-checked

Files involved:

- `apps/web/next.config.mjs` (only if compatibility fixes are required)
- `apps/web/vitest.config.ts` (only if compatibility fixes are required)
- `apps/web/README.md`
- `docs/UPDATE_FE_PACKAGE.md`
- any directly impacted test file if a runner compatibility fix is needed

Implementation steps:

1. Apply the smallest config or test adjustments required to keep the existing routes, rewrite behavior, and Vitest suite working after the package updates.
2. Update `apps/web/README.md` only if setup, commands, or environment assumptions changed during the upgrade.
3. Run the full verification matrix plus manual smoke steps and record the final resolved versions, warnings, and any temporary follow-up notes in this plan or the implementation report.

What stays the same:

- app routes and page responsibilities
- backend API contracts and FastAPI route behavior
- current user-visible frontend flows for `/login`, `/tutor`, `/graph`, and `/kb`

Verification:

- `pytest -q`
- `npm --prefix apps/web test`
- `npm --prefix apps/web run typecheck`
- `npm --prefix apps/web run lint`
- `npm --prefix apps/web run build`
- `npm --prefix apps/web ls next eslint-config-next vitest vite esbuild glob minimatch`
- `npm audit`

Exit criteria:

- all planned dependency updates are verified with no unresolved regression
- the final audit state is captured with exact package versions
- docs and rollback notes are current, and any temporary compatibility measure is explicitly called out

## Execution Order (Update After Each Run)

Start with the highest-priority remaining slices and proceed sequentially. Do not skip ahead unless the current slice is fully verified or explicitly blocked.

1. `FEPKG-01` direct package bump and lockfile refresh
2. `FEPKG-02` transitive advisory cleanup and override minimization
3. `FEPKG-03` compatibility fixes, smoke verification, and closeout

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
npm --prefix apps/web run lint
npm --prefix apps/web run build
npm --prefix apps/web ls next eslint-config-next vitest vite esbuild glob minimatch @next/eslint-plugin-next @typescript-eslint/parser @typescript-eslint/typescript-estree
npm audit
```

Slice-specific emphasis:

- `FEPKG-01`
  - compare `npm ls` output against the baseline vulnerable chain
  - confirm no new build or lint warnings were introduced
- `FEPKG-02`
  - prove any `overrides` entry is necessary, minimal, and reversible
  - verify the `glob` and `minimatch` chains specifically
- `FEPKG-03`
  - confirm the `/api/:path*` rewrite still works against `BACKEND_BASE_URL`
  - smoke `/login`, `/tutor`, `/graph`, and `/kb`

Manual smoke checklist:

1. Run `npm --prefix apps/web run dev` and open `/login`, `/tutor`, `/graph`, and `/kb`.
2. With the backend available, confirm browser calls to `/api/*` still proxy correctly through `BACKEND_BASE_URL`.
3. In `/tutor`, verify the chat load path still works and streaming behavior has not regressed.
4. In `/graph`, verify the graph renders and zoom/reset still work.

## What Not To Do

Do not do the following during the remaining package-upgrade work:

- do not run `npm audit fix --force` and accept its major-version jumps without review
- do not upgrade to Next 15/16, React 19, or a new ESLint config system unless the same-major path is proven impossible and this plan is updated first
- do not fold existing hook-warning cleanup or unrelated UI work into these slices

## Removal Ledger

No entries yet.

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)
```text
You are working in the CoLearni repo.

STRICT INSTRUCTIONS:

Open and read docs/UPDATE_FE_PACKAGE.md now. This file is the source of truth.
You MUST implement package-upgrade slices in the EXACT execution order listed there.
You MUST NOT claim a slice is complete until you produce a Verification Block with:
Root cause
Files changed
What changed
Commands run
Manual verification steps
Observed outcome

Before removing or replacing any file, function, script, config option, package override, compatibility shim, or docs surface, you MUST document the removal in docs/UPDATE_FE_PACKAGE.md using the Removal Entry Template.
For every removal, include:
Removed artifact
Reason for removal
Replacement
Reverse path
Compatibility impact
Verification

Removal policy:
- Prefer reversible staged removals over hard deletes.
- If rollback would be difficult, stop and introduce a facade, shim, or override instead of deleting immediately.
- Do not delete public or team-facing contracts without a compatibility note and rollback path.
- Do not claim a removal is complete until the replacement behavior is verified.

After every 2 slices OR if your context is compacted or summarized, re-open docs/UPDATE_FE_PACKAGE.md and restate which slices remain.
Work in small commits: chore(refactor): <slice-id> <short desc>.
If you discover a mismatch between current repo behavior and the assumptions in docs/UPDATE_FE_PACKAGE.md, STOP and update the plan before moving on.

When you finish a slice, include both:
1. The normal Verification Block for the slice
2. A summary of all Removal Entries added during that slice

START:

Read docs/UPDATE_FE_PACKAGE.md.
Begin with the current slice in execution order exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
Make sure you re-read docs/UPDATE_FE_PACKAGE.md before every move to the next slice. It can be dynamically updated. Check the latest version and continue.
```
