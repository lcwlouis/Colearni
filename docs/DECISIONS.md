# Decisions, defaults, and open questions

## Accepted in the founder discussion

| ID | Decision | Consequence |
|---|---|---|
| D01 | Greenfield product direction centred on a persistent desk | Do not make the rebuild's graph-and-panel structure or feature parity a constraint. |
| D02 | Manageable, participatory learning is the first attention-related responsibility | Avoid compulsory friction, productivity policing, and verbose defaults. |
| D03 | Teaching adapts to learner and task | Methods and evidence differ across activities; no permanent learner-style labels. |
| D04 | Broad-goal and supplied-material entry both matter | Use shared goals/activity contracts; a paper journey is an appropriate early prototype. |
| D05 | Universal card contract with specialised bodies | The app owns the visual shell; the model produces bounded specifications. |
| D06 | Notes are learner-owned; agent contributions are separate | No agent note-write capability; preserve origin when the learner saves AI material. |
| D07 | Clearly disclosed current-desk note access, with private exceptions | Progressive loading and bounded saved-change excerpts; not full-notebook context. |
| D08 | Small automatic support additions, without focus theft or rearrangement | Replacement of work or major workspace changes requires acceptance. |
| D09 | Before/after revisions and recoverable agent changes | Targeted undo must not roll back later learner notes. |
| D10 | Built-in plugins first, with a path to private generation and reviewed publication | Use the common contract now; public executable-plugin governance is not a launch dependency. |
| D11 | Plain-language outcomes with Bloom used internally where useful | User chooses a capability, not a taxonomy rank. |
| D12 | Sessions can end without a test; revisits can assess what remains | Do not award mastery for consuming content or punish skipping checks. |

Acceptance means conversational agreement. It does not prove usability, security, or market demand.

## Proposed, reversible defaults for this handoff

| ID | Default | Why / review point |
|---|---|---|
| P01 | Workplace-aligned subset: React 19, Vite 7, TypeScript, Tailwind 4, Storybook 9; TanStack Router/Query when needed | The workplace list is supplied by the founder; adopting the subset for Desk is this revision's recommendation. Verify exact installed versions together. |
| P02 | Vitest 3.2+ within 3.x, Storybook 9 checks, Playwright/MSW, ESLint 9 | Align majors while using each tool at its actual boundary; avoid unused dependencies. |
| P03 | A single frontend package in an isolated directory | Avoid both an early monorepo framework and modifying the existing app. |
| P04 | A responsive ordered work area and supporting area, not an infinite canvas | Lower prototype complexity; spatial design remains reviewable. |
| P05 | Bundled `worked-example` and `scalar-function` plugins | Exercise both instructional content and deterministic parameter interaction. |
| P06 | Framework-independent domain types and an adapter boundary | Mock now without making React components depend on a future API vendor. |
| P07 | Object revisions + grouped changes + checkpoints, eventually using PostgreSQL | Full event sourcing, CRDTs, and Git-backed live workspaces are not required now. |
| P08 | Simple controlled Markdown/plaintext note editing initially | Test ownership and context before selecting a rich-text framework. |
| P09 | Synthetic material only in shared stories | Prevent private uploads or notes being bundled into a public Storybook. |
| P10 | Working label “Desk”; selected visual reference before P1 | No final branding. P0 does not invent a UI; compare layouts before visual implementation. |
| P11 | Omit MSAL, Teams SDK, and mandatory Express from the prototype | Workplace-specific integrations are not current product requirements; hosting remains separate. |
| P12 | One owned static/streaming Markdown boundary | Shared typography and content-safety rules, not two divergent systems. |

The workplace inventory is user-supplied context, not evidence of dependency installation or approval of every library for Desk. The adoption matrix, exact default-plugin selection, layout, and numeric context limits remain recommendations. Do not imply the user selected one of the proposed visual directions.

## Questions and implementation gates

| Decision | Needed before | Current treatment |
|---|---|---|
| Final brand and domain | Public marketing/launch | Keep labels centralised; do not buy or register anything. |
| Selected visual direction for learner-facing components | P1 (not P0 tooling) | Compare directions using `VISUAL_BRIEF.md`; record a usable selected reference before visual implementation. |
| Actual launch audience, domain, and source | Real learning pilot | Synthetic paper journey for UI testing only. |
| Hosting, authentication, tenancy, data residency | Real accounts or private uploads | Mock adapter; no production security claims. |
| Backend/service implementation | Real persistence/inference | Python/FastAPI and PostgreSQL remain candidates consistent with project context, not prototype dependencies. |
| Note sync/debounce and context budgets | Real tutor integration | Prototype values are tuning parameters. |
| Measurement/rubric and review quality | Automated progress claims | Separate exposure, assistance, and independent evidence; no mastery percentage from UI events. |
| Third-party engine sandbox and review pipeline | Running externally supplied code | Unknown engines render a fallback. |
| Paper parsing and figure/equation fidelity | Real document uploads | Source fragments are static fixtures. |

Resolve only questions relevant to the next implementation unit. The selected visual reference gates P1; brand, production services, and marketplace questions do not gate P0 or that visual comparison.

## Decision changes

For a change, record the decision ID, old and new rule, rationale, impacted contracts/stories, migration implications, and reviewer. Update the affected specification and tests in the same reviewed increment. Do not allow an implementation convenience to silently rewrite an accepted ownership rule.
