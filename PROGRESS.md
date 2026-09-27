# Progress tracker

## Current state

P0 tooling done on branch `desk` (see P0 entry). The rest of this paragraph is the v0.2 package's original state note.


Documentation v0.2 prepared on 27 September 2026. Workplace stack and visual review gates are documented. No application dependencies installed, project scaffolded, mockup image generated, visual selection made, Storybook built, or browser inspected by this revision. Existing draft contract and fixture are preserved unchanged. Do not infer work done elsewhere by Claude; inspect that workspace before changing it.

| Unit | State | Evidence |
|---|---|---|
| v0.1 baseline | Preserved | Previous contract, product boundaries, synthetic fixture |
| v0.2 docs and handoff | Prepared | Adoption matrix, version notes, visual brief, staged prompts |
| V0 — mockup comparison | Not started | Brief only; no images |
| V1 — visual selection | Pending | VISUAL_SELECTION.md explicitly unapproved |
| P0 — tooling | Done, pending review (27 Sep 2026; Vitest 4 and Storybook 10 follow-ups) | See P0 entry below; `npm run check` passes after clean `npm ci` |
| P1 — cards/authorship | Not started; gated on selection | — |
| P2 — note context | Not started | — |
| P3 — reviewed plugins | Not started | — |
| P4 — history/undo | Not started | — |
| P5 — composed session | Not started | — |

## P0 entry

**Unit/date:** P0 — tooling and contract baseline, 27 September 2026. Started from an empty orphan branch `desk` in `lcwlouis/Colearni` (no `rebuild` code, docs or history carried over, at the founder's explicit request). The v0.2 pack files sit at the repo root unchanged; the app sits beside them as one package (P03).

**Exact dependency and Node versions:** Node 22.22.2 (`.nvmrc`; `engines` >=22.12.0), npm 10.9.7. Runtime: react 19.3.0, react-dom 19.3.0. Dev: vite 7.3.6, @vitejs/plugin-react 5.2.0, typescript 5.9.3, tailwindcss 4.3.3, @tailwindcss/vite 4.3.3, storybook / @storybook/react-vite / addon-a11y / addon-docs / addon-vitest / eslint-plugin-storybook 10.6.0 (was 9.1.20; see follow-ups), vitest / @vitest/browser-playwright / @vitest/coverage-v8 4.1.11 (was 3.2.7; see follow-up), playwright 1.56.1 (pinned to match the preinstalled Chromium revision 1194), eslint 9.39.5, @eslint/js 9.39.5, typescript-eslint 8.70.1, eslint-plugin-react-hooks 7.1.1, eslint-plugin-react-refresh 0.5.7, globals 17.12.0, @types/react 19.3.0, @types/react-dom 19.3.0, @types/node 22.20.4. All direct versions are exact in `package.json`; single `package-lock.json`. No generator, `@latest`, `--force` or `--legacy-peer-deps` used; installs raised no peer conflicts.

**Files changed:** `package.json`, `package-lock.json`, `.nvmrc`, `.gitignore`, `index.html`, `tsconfig*.json`, `vite.config.ts` (Vitest projects `unit` + `storybook`), `eslint.config.js` (also bans `eval`/`new Function`), `.storybook/{main,preview,vitest.setup}.ts`, `src/styles/index.css` (shared Tailwind entry, no tokens), `src/app/{main,App}.tsx` (placeholder), `src/components/smoke/ToolingSmoke{,.stories}.tsx`, `src/domain/validate{,.test}.ts`, `src/adapters/{deskAdapter,mockDeskAdapter,mockDeskAdapter.test}.ts`, `README.md`, this file. `contracts/` and `fixtures/` are unchanged.

**Commands actually run/results:**
- `npm ci` from a deleted `node_modules`: OK.
- `npm run check` (typecheck → lint → `vitest run` → `vite build` → `storybook build`): all pass. 14 tests: 13 unit (fixture validates, private note absent from expected context, excerpts untrusted and match the note, duplicate ids / cross-desk / bad revisions / unknown origin, sharing or contract version / plugin version ranges / non-JSON plugin data rejected, adapter returns copies and rejects unknown desks) + 1 Storybook interaction story in headless Chromium.
- The smoke interaction test demonstrably executes: changing its expected text made it fail; restored.
- The a11y gate (`a11y.test: 'error'`) demonstrably fails a story: a temporary story with an unnamed button failed with axe `button-name`; removed.
- `npm audit`: **14 moderate advisories, one root cause** (see limitations).

**Selected visual reference and approval, when required:** None. `docs/VISUAL_SELECTION.md` remains PENDING. P1 not started.

**Browser states actually inspected:** None by eye. Headless Chromium ran the Storybook story test only; no screenshots taken.

**Known limitations:**
- **Security exception for review:** GHSA-82fw-gwwq-j7x9 (Vitest `@vitest/mocker` redirect-mock path traversal, dev/test server only) affects every Vitest 3.x and the copy bundled in Storybook 9.1.20. The fix is only in Vitest ≥4.1.11, which breaks the Vitest 3 target, and Storybook 9's `addon-vitest` pairs with `@vitest/browser-playwright` only for Vitest 4. Proposed exception: keep Vitest 3.2.7 / Storybook 9.1.20 for the local prototype, never expose the Vite/Storybook dev servers beyond localhost, and review a move to Vitest 4 (and possibly Storybook 10) as an explicit decision change to P02. Nothing was forced.
- ESLint 9.39.5 prints a deprecation notice (ESLint 10 is current); kept per the ESLint 9 target.
- Storybook logs a harmless `markdown-to-jsx` optimizeDeps warning from its own internals.
- `storybook build` warns about a large chunk; not addressed at P0.
- Validation covers the fields P0/P1 need; plugin `input`/`savedState` are checked only as plain JSON until P3 schemas exist. TypeScript types remain compile-time only.
- Router, Query, Radix, cva, tailwind-merge, lucide, Markdown, motion, toasts, MSW and a standalone Playwright suite are intentionally not installed yet.

**Decision/contract changes:** None.

**Next review question:** Accept the Vitest 3 advisory exception (or approve moving to Vitest 4)? Then select and record a visual reference so P1 can start.

**Commit/deploy status:** Committed and pushed to `origin/desk` (orphan branch, requested by the founder). No deploy.

## P0 follow-up — Vitest 4 (27 September 2026)

**Decision change:** P02 Vitest 3.x → 4 at the founder's direction, recorded in `docs/DECISIONS.md` and `docs/FRONTEND.md`.

**Versions:** vitest, @vitest/browser-playwright, @vitest/coverage-v8 4.1.11 (brings @vitest/browser and @vitest/mocker 4.1.11). Removed the direct `@vitest/browser` dependency. Everything else unchanged. No peer conflicts; no overrides or `--force`.

**Files changed:** `package.json`, `package-lock.json`, `vite.config.ts` (`provider: playwright()`), `tsconfig.app.json` (dropped the Vitest 3 provider types), `docs/DECISIONS.md`, `docs/FRONTEND.md`, this file.

**Commands actually run/results:** clean `npm ci`, then `npm run check`: all pass, 14 tests. Re-ran the negative checks under Vitest 4: a broken story assertion fails, and a story with an unnamed button fails axe `button-name`. Both were reverted.

**Remaining advisory:** `npm audit` drops from 14 to 11 moderate findings, all one root cause: `storybook@9.1.20` bundles `@vitest/mocker` 3.2.4. Vitest's own mocker is now patched. Clearing the rest needs Storybook ≥10.1 (off the Storybook 9 target) or a forced override (disallowed by `AGENTS.md`). Interim rule: keep Storybook's dev server on localhost only.

**Next review question:** Move to Storybook 10 to clear the remaining finding, or accept it for the local prototype? Visual selection is still pending for P1.

## P0 follow-up — Storybook 10 (27 September 2026)

**Decision change:** P01/P02 Storybook 9 → 10 at the founder's direction, recorded in `docs/DECISIONS.md`, `docs/FRONTEND.md` and `docs/WORK_PLAN.md`.

**Versions:** storybook, @storybook/react-vite, @storybook/addon-vitest, @storybook/addon-a11y, @storybook/addon-docs, eslint-plugin-storybook: all 10.6.0. Storybook 10 no longer bundles `@vitest/mocker`; the only copy is Vitest's 4.1.11. The in-place upgrade hit an ERESOLVE against the old 9.x set, so the 9.x packages were uninstalled and 10.6.0 installed together. No `--force`, `--legacy-peer-deps` or overrides.

**Files changed:** `package.json`, `package-lock.json`, the docs listed above, this file. No config or story changes were needed.

**Commands actually run/results:** clean `npm ci`: 0 vulnerabilities. `npm run check`: all pass, 14 tests, both builds. Negative checks re-run on Storybook 10: a broken story assertion fails; a story with an unnamed button fails axe `button-name`; both reverted.

**Security status:** `npm audit` reports **0 vulnerabilities**. GHSA-82fw-gwwq-j7x9 is resolved; the earlier localhost-only interim rule is no longer needed for that advisory.

**Remaining limitations:** ESLint 9 deprecation notice and the Storybook large-chunk build warning remain. No browser inspection by eye.

**Next review question:** Select and record a visual reference (`docs/VISUAL_SELECTION.md`) so P1 can start.

## Update template

**Unit/date:**  
**Exact dependency and Node versions:**  
**Files changed:**  
**Commands actually run/results:**  
**Selected visual reference and approval, when required:**  
**Browser states actually inspected:**  
**Known limitations:**  
**Decision/contract changes:**  
**Next review question:**  
**Commit/deploy status:** Not performed unless explicitly authorised.
