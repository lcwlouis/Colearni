# Work plan — continue from the existing prototype

Use [Foundation v0.4 WORK_PLAN.md](foundation/v0.4/docs/WORK_PLAN.md), with [repository reconciliation](FOUNDATION_ADOPTION.md).

- **P0:** already recorded as complete, pending review. Preserve its Storybook 10 / Vitest 4 upgrades and historical checks; do not start from an empty scaffold.
- **V0:** one explicitly requested new view at a time. All former mockups are retired; root [VISUAL_SELECTION.md](VISUAL_SELECTION.md) is the live record.
- **P1:** not started; requires visual approval, explicit assignment, and a scoped decision on editor/contract handling.
- **Contract migration:** root v1 remains active. The snapshot's v2 cannot be copied over without migrating fixture/validator/adapter consumers and testing them together in a separately assigned unit.
- **E0/G0/X1/X2:** optional editor, graph, MCP, and decision experiments require separate assignments. No default live provider calls or arbitrary plugin installations.

Later units remain proposals, not work authorised by the import. Earlier sequencing and tooling decisions are preserved in [historical WORK_PLAN.md](history/pre-v0.4/docs/WORK_PLAN.md). Use [RESUME_DESK.md](../prompts/RESUME_DESK.md) for the next assigned unit and preserve root `PROGRESS.md`.
