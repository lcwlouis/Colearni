# Repository adoption notice — 3 October 2026

Read [docs/FOUNDATION_ADOPTION.md](docs/FOUNDATION_ADOPTION.md) and [START_HERE.md](START_HERE.md) first. This is the existing `desk` prototype: P0 is recorded as complete, Storybook 10 / Vitest 4 upgrades remain in force, and root v1 contracts/fixtures are not replaced by imported v2 drafts. Use [prompts/RESUME_DESK.md](prompts/RESUME_DESK.md), not an archived empty-workspace setup.

Foundation v0.4 under `docs/foundation/v0.4/` supplies product/design requirements subject to that adoption record. Older rules below remain applicable except where the adoption record explicitly supersedes setup/status, version targets or visual workflow. Work only on the assigned unit. No old mockup is approved; one requested view per visual review. Root `docs/VISUAL_SELECTION.md` is the live approval record.

Preserve existing work and progress. One agent owns a unit, another reviews; no racing on contracts, lockfiles, navigation or tokens. The founder's request authorises this documentation-update branch/PR only, not merging, deployment, future implementation, provider activation or licence adoption. Future commits/pushes still require explicit authorisation for their unit.

---

# Agent working contract — new Desk prototype

Scope: this new prototype directory only. It does not authorise editing the live CoLearni repository or superseding higher-level instructions.

Read `START_HERE.md`, `docs/PRODUCT.md`, `docs/DECISIONS.md`, and the assigned unit in `docs/WORK_PLAN.md`. Read additional boundary documents only as needed. Accepted decisions outrank convenience. Proposed defaults may be revised with an explicit rationale; unresolved product choices must not be silently invented.

## Work rules

- Implement only the assigned unit. The v0.2 first prompt covers P0 only. P1 requires an accessible selected visual reference and recorded founder approval; it has a separate prompt.
- Preserve learner-owned notes, source attribution, read privacy, and targeted undo rules.
- Use synthetic fixtures and a mock adapter. No real models, private uploads, live credentials, auth/billing, arbitrary code execution, or marketplace.
- Keep UI rendering, domain validation/state, and adapters separate. Built-in teaching plugins use the host contract; do not bypass it for demos.
- Include state stories and tests for failure and permission cases, not only appearance.
- Do not change final brand or invent a desk layout before the visual gate. P0 is tooling only; after selection, implement only the approved P1 slice and shared tokens, not broad application navigation.
- Follow the workplace-aligned major targets and current peer/engine/security checks in FRONTEND.md. No unqualified @latest drift, employer source reuse, forced dependency resolution, or unapproved enterprise integrations. Retain one lockfile.
- Treat TypeScript types as compile-time help, not input validation or authorisation.
- Update `PROGRESS.md` with actual evidence and remaining limitations.
- Do not `git add`, commit, amend, push, deploy, install integrations into accounts, or buy domains without explicit approval.
- If browser inspection or a command is unavailable, report it. Never claim verification that was not performed.

## First-task stopping condition

P0 is checked, or a concrete environment blocker is documented. Summarise actual setup/tests and the pending visual selection; stop before P1. After explicit P1 assignment, stop again after the card/notes slice for review. Never claim a mockup or screenshot exists unless accessible.
