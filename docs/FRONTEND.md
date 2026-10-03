# Frontend — current repository baseline

The current product/frontend specification is [Foundation v0.4 FRONTEND.md](foundation/v0.4/docs/FRONTEND.md), subject to [the adoption exceptions](FOUNDATION_ADOPTION.md).

**Retain the existing Storybook 10 / Vitest 4 implementation**, package manifest, lockfile, Node configuration, smoke story, validators and adapters. Do not downgrade to 9/3 or re-scaffold P0. Full earlier configuration rationale is preserved in [historical FRONTEND.md](history/pre-v0.4/docs/FRONTEND.md) and [PROGRESS.md](../PROGRESS.md).

Root contracts/fixtures are active v1. Snapshot v2 documents, fixtures and types are an explicitly separate design target. A future migration must update validators/adapters/tests together. P1 requires the live [visual selection](VISUAL_SELECTION.md) and a scoped editor/contract decision; importing documentation does not approve design or install dependencies.
