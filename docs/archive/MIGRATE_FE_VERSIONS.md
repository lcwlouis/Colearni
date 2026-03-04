# Frontend Version Migration Plan

Last updated: 2026-02-28

Archive snapshots:
- `docs/archive/MIGRATE_FE_VERSIONS_2026-02-28_initial.md`

## Recommendation

Yes, this codebase can likely move to Next.js 16 without a large app rewrite.

Recommended target:
- `next` 16.x as the end state

Recommended path:
1. Move from `14.2.35` to the latest `15.x` checkpoint with React 19.
2. Migrate linting off `next lint` and stabilize type generation.
3. Move from `15.x` to the latest `16.x`.

Reasoning:
- Official Next.js support policy lists `16.x` as Active LTS, `15.x` as Maintenance LTS, and `14.x` as unsupported.
- The current app is already on the App Router and does not appear to use the main 15.x async request APIs that cause most code churn.
- The main guaranteed migration work for this repo is tooling, not application behavior.

## Branch Isolation Rules

This migration should run on a dedicated branch, not directly on the current working branch.

Preferred branch:
- `codex/fe-next-16-migration`

Safe branch workflow:

1. Check `git status --short` before any edits, installs, or codemods.
2. If the working tree is clean and the current branch is not the migration branch:
   - create and switch to `codex/fe-next-16-migration`
3. If the working tree is already on `codex/fe-next-16-migration`:
   - continue there
4. If the working tree has unrelated uncommitted changes:
   - stop
   - report that branch switching is unsafe until the user commits, stashes, or explicitly allows carrying those changes

Reasoning:
- creating a dedicated branch protects the current line of work from package-lock churn, codemod diffs, and React/Next migration edits
- switching branches with unrelated local changes can either fail or accidentally carry those changes into the migration branch, which defeats the isolation goal

## Research Basis

Primary sources:

- [Next.js support policy](https://nextjs.org/support-policy)
- [Next.js 15 upgrade guide](https://nextjs.org/docs/app/guides/upgrading/version-15)
- [Next.js 16 upgrade guide](https://nextjs.org/docs/app/guides/upgrading/version-16)
- [Next.js codemods guide](https://nextjs.org/docs/app/guides/upgrading/codemods)
- [Next.js 15 release blog](https://nextjs.org/blog/next-15)
- [Next.js blog index with Next.js 16 highlights](https://nextjs.org/blog)
- [AI SDK Next.js App Router quickstart](https://ai-sdk.dev/docs/getting-started/nextjs-app-router)

Research findings that matter here:

1. Next.js 15 requires React 19 for App Router apps and makes `cookies`, `headers`, `draftMode`, `params`, and `searchParams` async in the affected server entrypoints.
2. Next.js 16 requires Node `20.9.0+`, removes `next lint` in favor of the ESLint CLI, and introduces additional 15->16 migration steps such as the `middleware` to `proxy` rename.
3. `next typegen` was introduced in Next.js `15.5`, which matters because this repo currently depends on generated `.next/types`.
4. Next.js 15/16 add platform features that are useful for AI apps, including `after`/stream-followup hooks, observability hooks, improved caching APIs, and React 19.2 support.
5. The AI SDK’s official Next.js quickstart assumes the App Router, a Route Handler, and `useChat`, which is aligned with modern Next usage but not yet how this repo currently serves AI traffic.

## Current Repo Assessment

### Starting point

Current frontend package state in `apps/web/package.json`:

- `next`: `14.2.35`
- `react`: `18.3.1`
- `react-dom`: `18.3.1`
- `eslint-config-next`: `14.2.35`
- `vitest`: `2.1.9`
- `lint` script: `next lint`
- `typecheck` script: `tsc --noEmit`

Current local runtime baseline:

- `node -v`: `v23.11.0`
- `npm -v`: `10.9.2`

Current verification baseline:

- `npm --prefix apps/web test`: passing (`58` tests)
- `npm --prefix apps/web run typecheck`: passing after generated `.next/types` exist
- `npm --prefix apps/web run lint`: passing with `3` pre-existing hook warnings
- `npm --prefix apps/web run build`: passing with the same `3` warnings

### Why this repo is a good candidate for 15/16

The current `apps/web` codebase has a relatively small Next.js surface area:

- App Router pages exist under `apps/web/app/`
- the pages are primarily client components
- there are no local Next Route Handlers under `apps/web/app/api/**`
- there is no `middleware.ts` or `proxy.ts`
- API traffic is mostly delegated to the FastAPI backend through `apps/web/lib/api/client.ts`
- `next/image` usage appears limited to a local static asset in `apps/web/components/global-sidebar.tsx`

This means the repo avoids most of the code patterns that usually make the 14 -> 15 jump painful.

### What will definitely change

1. React 19 adoption
- Next.js 15 requires React 19 for the App Router path.
- That means upgrading `react`, `react-dom`, `@types/react`, and `@types/react-dom`.

2. Lint command migration
- Next.js 16 requires moving away from `next lint`.
- This repo currently hardcodes `next lint` in `apps/web/package.json`, so this is a guaranteed code change.

3. Type generation workflow
- This repo includes `.next/types/**/*.ts` in `apps/web/tsconfig.json`.
- That already means typecheck reliability depends on generated Next type artifacts.
- Next 15.5+ adds `next typegen`, which should be wired into the migration instead of relying on stale `.next` output.

### What looks low-risk in this repo

1. Async Request API breakage
- A repo-wide search did not find current usage of `cookies()`, `headers()`, `draftMode()`, server `params`, or server `searchParams`.
- The official 15.x async-request migration is still relevant, but likely a no-op for the current app code.

2. `middleware` to `proxy`
- The 16.x rename does not look relevant today because this app does not currently define middleware.

3. Image default changes
- The only detected `next/image` usage is a local logo image, so the 16.x image changes look low risk for current behavior.

## AI-App Relevance

Moving to 15/16 is directionally good for AI product work, but the benefit is mostly platform readiness, not an immediate feature unlock for this codebase.

What newer Next versions help with:

- modern App Router patterns used by the AI SDK
- streamed responses and post-stream follow-up work via `after`
- observability integration through `instrumentation.js`
- newer caching primitives such as `updateTag()`, `refresh()`, and Cache Components
- React 19.2 features that can help interactive UIs

What will not happen automatically:

- The app will not suddenly gain better AI UX just by changing Next versions.
- The current frontend still streams and fetches against the FastAPI backend rather than local Next Route Handlers.
- If the long-term direction is to use AI SDK route handlers or more server-side streaming in Next, that needs a separate architecture change after the framework migration.

Inference from sources and current code:
- Upgrading to 16.x is worth doing because 14.x is unsupported and 16.x is Active LTS.
- The direct AI-product value is future compatibility and better platform options, not an immediate user-facing improvement for the existing architecture.

## Recommendation Detail

Preferred outcome:
- land on `next` 16.x
- keep `react` and `react-dom` aligned with the version line required by the Next upgrade
- replace `next lint` with the ESLint CLI
- make type generation explicit before `tsc --noEmit`

Why not stop at 15.x:
- `15.x` is already in Maintenance LTS
- `16.x` is the actively developed LTS line
- if the repo is going to absorb React 19 and lint migration anyway, stopping at 15.x only postpones the remaining mandatory work

Why not jump directly in one blind step:
- the cleanest execution order is still `14 -> 15 -> 16`, even if done in one branch
- the official upgrade guides and codemods are version-specific
- this preserves smaller review slices and clearer rollback points

## Ordered Migration Slices

Use these stable IDs in commits and reports.

### FEVER-01: Preflight and codemod dry run

Purpose:
- confirm the current baseline, stage the version-specific codemods, and document expected no-op areas before changing runtime dependencies

Files involved:
- `apps/web/package.json`
- `apps/web/tsconfig.json`
- `docs/MIGRATE_FE_VERSIONS.md`

Implementation steps:
1. Enforce the branch-isolation rules in this file and switch to `codex/fe-next-16-migration` if safe.
2. Capture clean baselines for `test`, `typecheck`, `lint`, and `build`.
3. Dry-run the official codemods:
   - `npx @next/codemod@canary upgrade 15`
   - `npx @next/codemod@latest next-async-request-api .`
   - `npx @next/codemod@canary next-lint-to-eslint-cli .`
4. Record which codemods are true no-ops and which ones will actually touch the repo.

Exit criteria:
- work is isolated on `codex/fe-next-16-migration`, or a git-safety blocker is explicitly reported before any migration edits
- the exact baseline and expected migration touchpoints are documented
- no hidden blockers appear in the codemod dry run

### FEVER-02: Upgrade to Next 15 and React 19

Purpose:
- land the required 14 -> 15 framework and React jump with the smallest possible app diff

Files involved:
- `apps/web/package.json`
- `apps/web/package-lock.json`
- any source file touched by the React 19 or async-request codemods

Implementation steps:
1. Upgrade `next`, `react`, `react-dom`, `eslint-config-next`, `@types/react`, and `@types/react-dom` to the correct 15-era compatible versions.
2. Apply the 15 upgrade codemod and the async-request codemod.
3. Review source diffs manually and remove any codemod churn that does not apply to this repo.
4. Re-run the full frontend verification matrix.

Exit criteria:
- the app is running on 15.x with React 19
- no current route, auth, chat, graph, or KB flow regresses
- any async-request changes are either no-op or fully verified

### FEVER-03: Tooling migration for 16 readiness

Purpose:
- handle the repo-specific changes that are guaranteed before the 15 -> 16 jump

Files involved:
- `apps/web/package.json`
- `apps/web/tsconfig.json`
- `apps/web/eslint.config.mjs` or equivalent flat-config file
- `apps/web/README.md`

Implementation steps:
1. Replace `next lint` with the ESLint CLI using the official codemod or an equivalent manual migration.
2. Preserve the current Next ruleset in the new ESLint config.
3. Update the `typecheck` workflow to explicitly generate Next types before running `tsc --noEmit`.
4. Document the new lint and typecheck expectations in `apps/web/README.md`.

Exit criteria:
- the repo no longer depends on `next lint`
- `typecheck` is reliable without needing a prior manual build
- lint output is at baseline or better

### FEVER-04: Upgrade from 15 to 16

Purpose:
- move from the maintenance line to the current Active LTS line

Files involved:
- `apps/web/package.json`
- `apps/web/package-lock.json`
- `apps/web/next.config.mjs`
- any source/config file touched by the 16 codemods

Implementation steps:
1. Upgrade `next` to the target 16.x version and align remaining peer dependencies.
2. Apply the official 16 upgrade guidance and only accept codemod changes that apply to this repo.
3. Validate `next.config.mjs`, especially the existing `/api/:path*` rewrite and `proxyTimeout` usage.
4. Re-run build, lint, typecheck, tests, and manual smoke flows.

Exit criteria:
- the repo runs cleanly on 16.x
- the rewrite proxy and current page routes still behave the same
- no 16.x deprecations remain in the active frontend path

### FEVER-05: Optional AI-platform follow-up

Purpose:
- decide whether to adopt the newer platform capabilities after the framework migration, without mixing them into the version bump itself

Files involved:
- future-only; do not bundle into the version migration by default

Implementation steps:
1. Decide whether the frontend should keep delegating AI traffic to FastAPI or adopt Next Route Handlers for selected chat/streaming paths.
2. If staying with FastAPI, keep the migration limited to framework support and dev tooling.
3. If moving AI serving closer to Next later, evaluate:
   - Route Handlers for streaming
   - AI SDK `useChat`
   - `after` for post-stream logging or persistence
   - `instrumentation.js` for frontend/server observability
   - Cache Components and `updateTag()` only where server-side data flow justifies it

Exit criteria:
- AI architecture decisions are explicit instead of being implicitly coupled to the Next upgrade

## Verification Matrix

Run after every non-doc slice:

```bash
npm --prefix apps/web test
npm --prefix apps/web run typecheck
npm --prefix apps/web run lint
npm --prefix apps/web run build
```

Run additionally when changing dependency versions:

```bash
npm audit
npm --prefix apps/web ls next react react-dom eslint-config-next eslint vite vitest
```

Manual smoke checklist:

1. Open `/login` and verify auth redirect and login form behavior.
2. Open `/tutor` and verify chat load plus SSE streaming behavior.
3. Open `/graph` and verify graph render plus zoom/reset behavior.
4. Open `/kb` and verify knowledge-base list and upload flow.
5. Confirm `/api/*` requests still rewrite correctly through `BACKEND_BASE_URL`.

## Risks

### High-confidence required changes

- `next lint` removal will force a lint-script and config migration for 16.
- React 19 will require dependency and typings updates.

### Medium-risk changes

- lint rule ordering or warnings may shift after the ESLint migration
- React 19 type tightening may surface small hook or event typing issues
- the current `typecheck` command may need a script-level change to generate Next types first

### Lower-risk changes for this repo

- async request API migration
- middleware/proxy rename
- image defaults

## Do Not Mix Into This Migration

- do not redesign the frontend architecture during the framework bump
- do not replace the FastAPI backend integration as part of the same migration PR
- do not fold unrelated UI cleanup into the version upgrade slices
- do not “improve AI support” by adding AI SDK or Route Handlers in the same change unless the scope is explicitly widened

## Final Call

Based on the current codebase and the official upgrade guidance:

- moving to Next 15 is feasible
- moving to Next 16 is also feasible
- Next 16 is the better target
- the repo’s real migration work is tooling and React alignment, not major app rewrites
- the AI-related upside is mostly future platform support; it is not an immediate product-level gain unless the frontend later adopts more Next-native AI patterns

## Suggested Kickoff Prompt

```text
You are working in the CoLearni repo on the Next.js frontend migration.

Read docs/MIGRATE_FE_VERSIONS.md first and treat it as the source of truth.

Before making any changes:
1. Run `git status --short`.
2. If the worktree is clean and the current branch is not `codex/fe-next-16-migration`, create and switch to `codex/fe-next-16-migration`.
3. If already on `codex/fe-next-16-migration`, continue.
4. If the worktree has unrelated uncommitted changes, stop and report that switching branches safely is blocked. Do not carry unrelated changes into the migration branch unless the user explicitly asks for that.

Then execute the migration slices in order:
1. FEVER-01
2. FEVER-02
3. FEVER-03
4. FEVER-04
5. FEVER-05 only if explicitly widening scope

For each slice:
- check official Next.js breaking changes against the current codebase
- mark each relevant breaking change as applies or does not apply
- run the verification matrix from docs/MIGRATE_FE_VERSIONS.md
- do not proceed to the next slice until the current slice is verified
```
