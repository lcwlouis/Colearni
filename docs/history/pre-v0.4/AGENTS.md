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
