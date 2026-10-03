# Claude task — P1 after explicit visual selection

Use the complete v0.4 package. Read AGENTS.md, START_HERE.md, docs/VISUAL_SELECTION.md, the selected actual image, docs/INTERACTION_CONTRACT.md, docs/NOTES_AND_ACTIVITIES.md, docs/FRONTEND.md, docs/TEST_PLAN.md and P1 in docs/WORK_PLAN.md.

Precondition: founder selection is recorded and accessible; P0 has been inspected. If selection is still pending, report that specific blocker rather than inventing a UI or treating every concept board as authoritative. Preserve existing work. Do not implement reference-image errors that contradict ownership, source accuracy or permissions.

Build only a shared CardShell, source/provenance display, learner-owned note editor and separate tutor contribution. Include private/shared read disclosure, saved/draft/error/conflict states and an explicit “Check my explanation” mock. Reuse the selected editor foundation; do not choose a major framework without the E0 comparison or an explicit reviewed decision. Keep the contract ready for worksheet-response use without implementing a whole curriculum.

Use synthetic fixtures and an in-memory adapter. Test formatting/keyboard input, save without focus/caret loss, denied note mutation, and origin retained when a learner explicitly saves a contribution. No real models, source ingestion, multiplayer, app installation or backend. MCP view implementation is not part of this task.

Run interaction/type/lint/build checks and inspect actual browser renderings at reviewed sizes where tools are available. Record unperformed checks honestly. Show the resulting diff and limitations, update PROGRESS.md, and stop after the slice. No commit/push/deploy or automatic next unit.

## v0.4 additional gate

All previous mockups are retired and absent. P1 requires a newly approved reference for this exact scope. Review GRAPH_MODEL, NAVIGATION_AND_BRAND, MOBILE_INTERACTION and THEME_BRIEF. Do not import a logo/nav/tab list from memory. The mobile note editor uses selection-based controls plus fallback, not a persistent desktop bar. No new images are generated as part of this coding assignment.
