# Desk prototype

A frontend prototype for Desk, a calm learning workspace. It is built from the Desk foundation v0.2 pack; start with `START_HERE.md`, and agents follow `AGENTS.md`.

Status: P0 tooling only. Learner-facing UI waits for a selected visual reference (`docs/VISUAL_SELECTION.md`). See `PROGRESS.md`.

## Commands

Requires Node 22.12+ (`.nvmrc`: 22.22.2).

```bash
npm ci
npm run dev              # Vite app (placeholder)
npm run storybook        # Storybook on :6006
npm run typecheck
npm run lint
npm test                 # unit tests (Node)
npm run test:storybook   # story interaction + a11y tests in headless Chromium
npm run check            # everything, including app and Storybook builds
```

All data is synthetic (`fixtures/`). No model calls, uploads, credentials or backend.
