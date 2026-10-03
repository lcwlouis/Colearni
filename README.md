# Desk prototype

A frontend prototype for Desk, a calm learning workspace. The image-free **Desk Foundation v0.4** is included at [docs/foundation/v0.4](docs/foundation/v0.4/README.md). Start with [START_HERE.md](START_HERE.md); coding agents follow [AGENTS.md](AGENTS.md).

Status: P0 tooling is recorded as complete, pending review. This documentation update does not reset that work or implement P1. Learner-facing UI still requires an approved reference in [docs/VISUAL_SELECTION.md](docs/VISUAL_SELECTION.md). See [PROGRESS.md](PROGRESS.md) for historical implementation evidence and [the adoption record](docs/FOUNDATION_ADOPTION.md) for how v0.4 applies here.

## Commands

Requires Node 22.12+ (`.nvmrc`: 22.22.2). Preserve the repository's approved Storybook 10 and Vitest 4 baseline, not the older targets inside the imported snapshot.

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

All runtime fixtures are synthetic. No model calls, uploads, credentials or backend are introduced by the documentation update. No images or final licence are added.
