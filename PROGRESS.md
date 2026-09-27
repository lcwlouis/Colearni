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
| P0 — tooling | Done, pending review (27 Sep 2026) | See P0 entry below; `npm run check` passes after clean `npm ci` |
| P1 — cards/authorship | Not started; gated on selection | — |
| P2 — note context | Not started | — |
| P3 — reviewed plugins | Not started | — |
| P4 — history/undo | Not started | — |
| P5 — composed session | Not started | — |

## P0 entry

**Unit/date:** P0 — tooling and contract baseline, 27 September 2026. Started from an empty orphan branch `desk` in `lcwlouis/Colearni` (no `rebuild` code, docs or history carried over, at the founder's explicit request). The v0.2 pack files sit at the repo root unchanged; the app sits beside them as one package (P03).

**Exact dependency and Node versions:** Node 22.22.2 (`.nvmrc`; `engines` >=22.12.0), npm 10.9.7. Runtime: react 19.3.0, react-dom 19.3.0. Dev: vite 7.3.6, @vitejs/plugin-react 5.2.0, typescript 5.9.3, tailwindcss 4.3.3, @tailwindcss/vite 4.3.3, storybook / @storybook/react-vite / addon-a11y / addon-docs / addon-vitest / eslint-plugin-storybook 9.1.20, vitest / @vitest/browser / @vitest/coverage-v8 3.2.7, playwright 1.56.1 (pinned to match the preinstalled Chromium revision 1194), eslint 9.39.5, @eslint/js 9.39.5, typescript-eslint 8.70.1, eslint-plugin-react-hooks 7.1.1, eslint-plugin-react-refresh 0.5.7, globals 17.12.0, @types/react 19.3.0, @types/react-dom 19.3.0, @types/node 22.20.4. All direct versions are exact in `package.json`; single `package-lock.json`. No generator, `@latest`, `--force` or `--legacy-peer-deps` used; installs raised no peer conflicts.

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
