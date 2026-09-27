# Frontend architecture — workplace-aligned proposal

## Workplace reference and Desk scope

The founder reports React 19, Vite 7, Tailwind 4, TanStack Router and Query; Radix UI, shadcn-style cva/tailwind-merge, MSAL browser/react, Teams JS SDK, framer-motion, lucide, react-markdown, streamdown, and sonner; Express serves the built app. Testing uses Vitest 3, Storybook 9, Playwright, MSW, and ESLint 9.

That is the workplace reference, not a requirement to import enterprise integrations or company code into Desk. Use independently written code and permitted public packages; do not bring employer source, fixtures, credentials, or internal branding into this prototype.

## Proposed adoption matrix

| Layer | Desk recommendation | Timing |
|---|---|---|
| UI/build | React 19 + matching react-dom, Vite 7, TypeScript | P0 |
| Styling | Tailwind 4 and its Vite integration; one shared CSS entry | P0 setup; approved design tokens at P1 |
| Primitives | Radix with owned wrappers; cva, tailwind-merge; lucide-react | P1 as components require them |
| Routing | TanStack Router for workspace/location/search state | P5 composition; do not build an app navigation system in P0 |
| Server state | TanStack Query for adapter-backed saved records and async status | Network-backed work when needed; not each keystroke |
| Component review | Storybook 9 with compatible React/Vite framework and addons | P0 |
| Tests | Vitest 3.2+ within 3.x; Playwright; MSW; ESLint 9 | Configure core tests at P0, add browser/network cases by unit |
| Markdown | One owned MarkdownContent boundary; react-markdown for static material, Streamdown when streaming is demonstrated | Introduce incrementally, not two unrelated rendering policies |
| Motion/feedback | framer-motion and sonner are allowed choices, not mandatory dependencies on every component | Only for a defined interaction; reduced-motion and accessible feedback |
| Microsoft integrations | Do not include MSAL or Teams SDK yet | Only if a future authentication/integration requirement calls for them |
| Static serving | Express is an optional way to serve built files, not the domain backend | Hosting decision later; no server.js required for Storybook |
| Domain services | Keep Python/FastAPI + PostgreSQL viable | Real service integration later, separate from frontend deployment |

Radix provides unstyled, customisable primitives; it does not impose a visual identity. TanStack Router provides routing and loading features; Query manages server-state fetching/caching. Our separation of state below is a design rule. [R16, R17, R18]

MSAL concerns authentication and token acquisition; TeamsJS supports Microsoft-hosted app experiences. These are not requirements for a standalone desk. Express can serve static files; this does not imply moving tutoring/business logic into Express. [R19, R20, R21]

## Version discipline

This is a compatibility target, not an installed lockfile or a claim that the workplace majors are the latest releases.

- Stay within React 19, Vite 7, Tailwind 4, Storybook 9, Vitest 3, and ESLint 9 unless an incompatibility or security issue requires an explicitly reviewed exception. Other library majors were not supplied; inspect their published peer requirements before choosing them.
- Vite 7 supports Vitest from 3.2 onward. Do not install arbitrary Vitest 3.0/3.1 alongside it. Vite 7's documented Node minima are 20.19 or 22.12 on the corresponding major lines; choose a currently supported, patched Node release satisfying all selected package engine constraints. A historical minimum is not a security recommendation. [R12]
- Storybook 9's guide requires Vite 5+, Vitest 3+, and TypeScript 4.9+. Its Vitest addon has its own setup requirements. These minimums are necessary information, not proof that every package combination works. Use matching Storybook core/framework/addon releases. [R13, R14, R15]
- Do not copy unqualified `@latest` scaffold commands from v0.1 or rolling documentation. Select a compatible generator and inspect the generated manifest; a generator version does not by itself prove the resulting runtime versions.
- Record exact resolved versions and retain one lockfile. Use reproducible clean installs in verification. Review published advisories for the resolved direct and transitive dependencies; do not suppress peer conflicts using `--force` or `--legacy-peer-deps`.
- Use Tailwind 4's documented Vite integration, not Tailwind 3 setup snippets. Verify tailwind-merge support for the selected Tailwind version. [R4]
- Use Storybook 9/Vitest 3 documentation for addon imports and browser-test configuration. Do not mix examples for a different major. Do not install every library in the reference table before it has a consumer.

No dependency installation or integration verification has been performed for this package.

## State ownership

| State | Owner |
|---|---|
| Which desk/source is open; shareable location | Router |
| Saved notes/cards, server revision, request status | Query + API/adapter when integrated |
| Unsaved note text, focus, selection, temporary control values | Local controlled state / domain reducer |
| Plugin saved state, permitted commands, changes and reversals | Domain services behind DeskAdapter |
| Tutor context and read permissions | Trusted context service eventually; deterministic mock now |

Never replace an actively edited note with a Query refetch result. Detect dirty drafts and revision conflicts, preserve user text, and reconcile saved state explicitly. Cache state is not an authorisation boundary or a substitute for revision history.

Do not send every slider movement, scroll, or keystroke to a model. The notes-context rules remain in `NOTES_CONTEXT.md`.

## Component and adapter boundaries

UI components receive validated data and explicit callbacks. They do not fetch private documents, infer mastery, hold API keys, or grant permissions. Keep domain vocabulary independent of Router, Query, Storybook, and motion libraries.

```text
Storybook fixtures / MSW when HTTP behaviour matters
                    |
                    v
DeskAdapter ------> future trusted API adapter
                    |
                    v
Domain validation, revisions, reducers, context selection
                    |
                    v
Approved layout -> shared card shell -> registered renderer
                    |
                    v
Learner semantic events (not automatic mastery)
```

Use an in-memory adapter for early components. Introduce MSW at the network boundary when demonstrating loading, errors, delays, cancellations, and conflicts. Storybook documents MSW integration. Avoid mocking Query internals or weakening production component contracts for tests. [R22]

## Suggested layout (single frontend package)

```text
src/
  app/                 # provider composition; minimal routes at P5
  components/ui/       # owned Radix wrappers and approved variants
  components/cards/    # shared CardShell and provenance controls
  features/
    desk/
    notes/
    context-preview/
    history/
  domain/              # serialisable types, validation, reducers, selectors
  adapters/            # DeskAdapter; deterministic mock; later HTTP adapter
  teaching-plugins/    # shared host, explicit registry, bundled reviewed plugins
  content/             # owned MarkdownContent renderer and URL policy
  fixtures/            # synthetic material and stable event sequences
  styles/              # semantic tokens and Tailwind entry
.storybook/
tests/                 # composed/browser scenarios when required
```

Co-locate stories and unit tests with components. Do not create a monorepo framework or publish an SDK just for one consumer. Both app and Storybook import identical approved tokens/styles.

## Rendering and motion rules

Static and streaming Markdown must share typography, code/math conventions, link policy, external-image restrictions, and sanitisation tests. Generated Markdown is not permission to execute HTML or JavaScript. Streamdown supports streaming Markdown and configurable security; do not assume defaults match Desk's privacy needs or preserve sanitisation when replacing plugin arrays. [R23, R24]

A text renderer is not a code execution engine, and code highlighting is not verified program output. A future code-diff component belongs behind its own reviewed renderer contract.

Use cva for enumerated, owned variants, not agent-supplied classes. Keep styles in the host; no payload CSS. Motion must not steal focus, rearrange user work, or continuously animate generated text. A sonner toast may supplement feedback, never be the only home for an important save error, history record, privacy change, or recovery action.

## Visual review and tests

See `VISUAL_BRIEF.md` and `VISUAL_SELECTION.md`. P0 is non-design setup; P1 is gated on a selected visual reference. Mockups are directional references, not evidence of accessibility or exact pixel specifications. Test chosen designs with real components, long content, keyboard navigation, reduced motion, and narrow viewports.

Use Vitest for pure invariants; Storybook 9 interaction/accessibility checks for components; Playwright for composed behaviour and later screenshot regression. Establish screenshot baselines from reviewed browser renders, not generated mockup pixels. Pin browser/environment and stabilise fixtures for repeatable comparisons. [R15, R25]

## Secrets and production boundaries

No real model calls, private uploads, credentials, or employer materials in stories. `VITE_*` variables are client-visible, not a place for secrets. Public Storybook builds bundle their fixtures. [R11]

An optional Express static server needs separate production work for routing fallback, caching, headers, and deployment. It is not in P0. No production authentication, secure sandbox, ingestion, or learning-effectiveness claim follows from this frontend prototype.
