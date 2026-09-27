# Storybook-first work plan

The v0.2 first handoff authorises P0 only in an explicitly selected isolated prototype directory. Visual exploration V0 and selection V1 run separately using `VISUAL_BRIEF.md`. P1 requires a usable approved reference recorded in `VISUAL_SELECTION.md`. Later units are described for planning, not authorised as one large build. Do not discard P1 work already begun under v0.1; inspect and review it before continuing.

Follow: read the relevant specification → state the small change → implement → test → inspect → report diff and limitations → update progress → stop at the agreed boundary. This adapts Ghost's verified-increment workflow, not its exact folder count. [R2]

## P0 — Tooling and contract baseline

Prepare the React 19 / Vite 7 / TypeScript application tooling, Tailwind 4 integration, and Storybook 9 React/Vite configuration using `FRONTEND.md`. Configure ESLint 9, typecheck, Vitest 3.2+ within 3.x, and compatible Storybook interaction/accessibility tooling. Use a minimal smoke story, not an invented desk or visual design system. Record actual versions, Node choice, and commands. Router, Query, MSW, and Playwright belong at their appropriate testing/composition boundaries; do not build unused scaffolding for the entire workplace inventory.

Use the supplied contract seed as a draft, resolving only fields needed for P1. Add a tiny mock adapter; do not write backend endpoints. Install no model SDK or execution sandbox.

**Acceptance:** app and Storybook smoke builds; typecheck/lint pass; one smoke interaction test demonstrably executes; reproducible lockfile records the requested majors; no secrets or live private data; setup has not overwritten the old app. Report any unavailable browser/tooling honestly. Stop here until the visual gate is satisfied; do not invent a final screen just to fill the app.

## P1 — Card and authorship foundation

**Prerequisite:** an explicitly approved primary visual reference and recorded selection. Use `prompts/CLAUDE_P1_AFTER_VISUAL_REVIEW.md`.

Build the shared `CardShell`, source/provenance display, a simple learner-owned note editor, and a clearly separate tutor-contribution component. The learner can toggle tutor-read sharing and edit their note. A tutor contribution can be saved only through an explicit learner action preserving origin. Agent actions cannot write the note body or change sharing.

Create these stories:

| Story | Assertion / review |
|---|---|
| `CardShell/SourceExcerpt` | Source origin and locator stay visible. |
| `CardShell/TutorContribution` | Clearly distinguished from learner-authored work. |
| `LearnerNote/Shared` | Learner can edit; read-sharing is disclosed. |
| `LearnerNote/Private` | No content/index entry appears in mock tutor context. |
| `LearnerNote/AgentWriteDenied` | A submitted forbidden command is rejected without state mutation. |
| `CardShell/LoadingErrorUnsupported` | Error/fallback preserves the surrounding shell. |
| `CardShell/LongContentNarrowViewport` | Text/controls remain usable; no ownership ambiguity. |

**Acceptance:** editable learner note remains separate from agent text; keyboard names/focus work; fallback states render; tests exercise forbidden commands; app and Storybook use the same approved styles. Inspect real stories against the selected reference at desktop and narrow widths. Capture browser screenshots if available and report what was actually inspected. A generated mockup is not a pixel-test baseline; establish that baseline from a reviewed real render. Stop for review after P1.

## P2 — Progressive notes and semantic guidance

Build deterministic shared-note indexing, saved-block deltas, and a context-preview panel using mock data. Add revision-bound semantic highlighting. No model calls and no continuous keystroke surveillance.

**Stories:** three-paragraph saved addition; rapid edits coalesced; oversized delta truncated with read option; private note excluded; revocation clears queued/derived data; stale update ignored; stale highlight rejected.

**Acceptance:** context respects scope, sharing, revision, and budget in every path; edit/save remains responsive; seeing the preview does not imply anything was actually sent to a tutor.

## P3 — Reviewed teaching plugins

Implement the explicit registry and the worked-example/scalar-function plugins from `PLUGINS.md`, both using the same host shell, semantic targets, and state protocol.

**Stories:** step reveal/highlight; scalar parameter change; reset; readable table alternative; invalid input; unknown engine version; renderer failure; reduced-motion/keyboard path.

**Acceptance:** no `eval`, executable user strings, arbitrary imports, or network plugin fetching; known numeric cases pass; plugin version/input/state restore without generation. Plot manipulation emits interaction evidence only, not mastery.

## P4 — Grouped changes and selective undo

Create pure command validation and a mock revision/change-set store. Enforce permissions, revision preconditions, and duplicate-command idempotency. Real authentication and server enforcement are still out of scope.

**Stories:** tutor adds support while note is being typed; undo removes only the support; newer learner edit causes conflict; duplicate action is ignored; multi-object rejection leaves all state unchanged; recovery preview preserves current privacy rules.

**Acceptance:** all-or-nothing mock updates; later notes never disappear on agent undo; focus and scroll are not stolen; conflicting work is not overwritten; history distinguishes author from approving actor.

## P5 — One composed learning session

Connect existing components to the synthetic source journey using the selected layout. Introduce minimal TanStack Router composition and TanStack Query only for saved/async adapter data; keep unsaved notes local. Use MSW for network error/conflict stories and Playwright for the composed flow. No new live backend is required. Connect existing components to the synthetic source journey. This is one scenario, not a full navigation system. Goal selection, source excerpt, brief assistance, learner note, reviewed tool, optional check, and return point should feel coherent. Include a plain-language broad-goal entry variant that reuses the goal component.

**Acceptance:** no lengthy mandatory onboarding or diagnostic; short help can be expanded; all interactions are clearly scripted; demonstrated source citations refer to fixtures; learner can pause and return to preserved mock state.

Mock storage persistence may be added behind the adapter at this point, with an explicit demo-only label. It must not be described as secure real-user storage.

## Review gate before real integration

Review the whole session with the founder and a few representative learners. Record whether the workspace is understandable, help is useful, ownership is clear, and navigation preserves attention. Decide actual source/domain, architecture, privacy, and evaluation boundaries before real ingestion or inference. Do not infer learning gains from visual enthusiasm.

## Work allocation

Parallelise only after the shared contract/tokens are reviewed. Separate tasks can then implement plugin fixtures/tests and note-context fixtures/tests against a pinned contract. One owner integrates shared state and layout. Do not allow several coding agents to independently rename core fields or build competing shells.

## Evidence of done

For every unit record changed files, tests and commands actually run, browser states actually inspected, limitations, contract changes, and next review question. A screenshot is not a test result; a successful build is not a visual audit; scripted tutoring is not working AI. Keep these distinctions explicit. Do not commit or push without approval. [R1]
