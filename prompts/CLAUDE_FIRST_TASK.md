# First Claude task — Desk v0.2 tooling and contract readiness

Use the full accompanying v0.2 package, not this prompt alone. Work in an explicitly selected isolated prototype directory. Do not overwrite or refactor CoLearni's `rebuild`, and do not import employer code or private fixtures. If previous Desk prototype work exists, inspect and preserve it; do not re-scaffold over it.

Read `AGENTS.md`, `START_HERE.md`, `docs/PRODUCT.md`, `docs/DECISIONS.md`, `docs/INTERACTION_CONTRACT.md`, `docs/FRONTEND.md`, and P0 of `docs/WORK_PLAN.md`.

Implement **P0 only**, without inventing the visual design. v0.2 supersedes the old P0-plus-P1 prompt: the founder wants visual comparison before committing learner-facing components to a direction. `docs/VISUAL_SELECTION.md` is currently pending.

Target React 19 + matching react-dom, Vite 7, TypeScript, Tailwind 4, Storybook 9, Vitest 3.2+ within 3.x, and ESLint 9. Verify generator output and all peer/engine requirements. No unqualified @latest scaffolding that silently changes majors. Choose a currently supported, patched Node version satisfying those requirements; record all exact installed versions and one lockfile. Never bypass conflicts with force/legacy-peer-deps. If a secure compatible resolution is unavailable, describe the blocker and propose a minimal reviewed exception.

Set up app/Storybook smoke builds, shared CSS entry points, lint/typecheck, and compatible test tooling. One simple semantic smoke story is enough; do not build an imaginary desk, generic dashboard, or invented design system. Check the supplied contract vocabulary and synthetic fixture with small pure tests. TypeScript alone is not runtime validation.

TanStack Router/Query are the intended navigation and saved-data choices but do not require a broad navigation system now. Radix, cva, tailwind-merge, lucide, static/streaming Markdown, motion, toasts, MSW, and Playwright should be introduced when the defined unit needs them. Do not install MSAL, Teams SDK, model SDKs, or an execution sandbox. No Express server is needed for this tooling task.

Do not generate a brand, fill a canvas with cards, change note ownership rules, add real sources/model calls, or proceed to P1 without a usable approved visual reference. If P1 work already exists, document it for review rather than deleting it.

Provide runnable scripts, run the smoke builds/tests you can actually execute, and update `PROGRESS.md` with versions, files changed, commands/results, limitations, and the state of the visual gate. No claimed screenshots or accessibility results unless actually obtained. Stop after P0. Do not commit, push, deploy, or continue automatically.
