# Desk — repository starting point

**Documentation baseline:** Foundation v0.4, adopted with repository-specific reconciliation on 3 October 2026. **Working name:** Desk. **Implementation:** existing P0 prototype, not a new empty workspace.

Read [FOUNDATION_ADOPTION.md](docs/FOUNDATION_ADOPTION.md) first. It takes precedence over installation/status instructions in the imported snapshot. The complete, unmodified handoff is [docs/foundation/v0.4](docs/foundation/v0.4/README.md); its nested progress and validation files describe the original documentation package, not this repository.

## Reading order

1. [Repository handoff](HANDOFF.md) and [agent rules](AGENTS.md).
2. [Current decisions](docs/DECISIONS.md), [product](docs/PRODUCT.md), and [interaction contract](docs/INTERACTION_CONTRACT.md).
3. [Documentation index](docs/README.md): read only the boundary documents relevant to the assigned unit.
4. [Historical implementation progress](PROGRESS.md), [next-session record](NEXT_SESSION.md), and [work plan](docs/WORK_PLAN.md).
5. [Current visual selection](docs/VISUAL_SELECTION.md) before any visual implementation.

## Do not regress the existing prototype

- Keep the current package manifest, lockfile, Storybook 10 / Vitest 4 upgrades, configurations, code and tests. Do not re-scaffold P0 or downgrade to snapshot defaults.
- Root `contracts/` and `fixtures/` remain the active version-1 prototype vocabulary. Version-2 drafts inside the imported handoff are a migration target, not an applied migration.
- All previous generated mockups remain retired. Design one explicitly requested view at a time; no image or logo is approved by this import.
- Use [prompts/RESUME_DESK.md](prompts/RESUME_DESK.md) for either coding agent. The archive's empty-workspace first-task prompt is not the default instruction for this existing repository.

This import does not authorise implementation of the roadmap, external integrations, a licence change, deployment, or merging a pull request. Each next unit needs its own assignment and review.
