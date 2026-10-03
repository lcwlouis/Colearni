# Repository handoff — Desk Foundation v0.4

Start with [START_HERE.md](START_HERE.md) and [the adoption record](docs/FOUNDATION_ADOPTION.md). The original, complete handoff is [here](docs/foundation/v0.4/HANDOFF.md).

## Current state

The `desk` branch has a P0 frontend/tooling prototype and recorded founder-approved Storybook 10 / Vitest 4 upgrades. Source inspection for this import used commit `35bb4f3c9d9c958e79d58f88a915387f3f14c922`. This update changes documentation only; it does not re-run or reset P0, migrate runtime contracts, implement a backend, or approve visuals.

## Product direction now available in the repository

An intention-centred learning desk with learner-owned reusable notes, worksheet responses, separate tutor contributions, quiet permission-scoped context, bounded research, revisions and selective undo. Retain umbrella/topic/subtopic/granular graph classification separately from edge relationships and learning evidence. PostgreSQL and bundled Docker Compose are accepted directions. MCP Apps and decision models remain separately assigned experiments; licensing language remains intent, not an operative licence.

## How to resume

Use [the shared resume prompt](prompts/RESUME_DESK.md). Inspect actual files and dirty work, read the relevant specs, and work only on the assigned unit. P1 requires a newly approved visual reference and an explicit editor/contract decision. Do not run an optional spike simply because its prompt is present.

Codex and Claude Code should use one implementation owner per unit and one reviewer. Do not race on contracts, lockfiles, shared design tokens, or navigation. Preserve `PROGRESS.md`; append observed results and update `NEXT_SESSION.md` after each assigned unit. No automatically implied next task, commit, push, merge or deployment.
