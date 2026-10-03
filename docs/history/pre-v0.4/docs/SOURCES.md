# Source ledger

Source ledger for 27 September 2026. R1–R11 are retained from v0.1; R12–R25 were consulted for this update. The original references are not claimed to have been independently reverified here. References support specific technical facts and process descriptions. They do not validate Desk's proposed pedagogy, product-market fit, security design, or dependency integration. User decisions come from the accompanying conversation; they are not external research findings. No full video transcript is reproduced or relied on as independently verified scientific evidence in this pack.

- **R1 — CoLearni repository instructions.** GitHub, `lcwlouis/Colearni`, `rebuild/AGENTS.md`; blob `a2789357c7bd8c6b3d6890c0f5ab84469fdd7ede`. Documents are authoritative for the existing implementation; preserve review, bounded changes, provenance, and no-commit-without-approval expectations. https://github.com/lcwlouis/Colearni/blob/rebuild/AGENTS.md
- **R2 — Ghost development workflow.** GitHub, `adrianhajdin/ghost-ai`, `context/ai-workflow-rules.md`; blob `216e832c72e02b92c847aa32c5d0b3b481281dd6`. Specification-led work, scoped implementation units, verified completion, and synchronised progress. https://github.com/adrianhajdin/ghost-ai/blob/main/context/ai-workflow-rules.md
- **R3 — Vite getting started.** Official template/scaffold and environment requirements. Exact compatible package versions still need verification when installing. https://vite.dev/guide/
- **R4 — Tailwind with Vite.** Official `@tailwindcss/vite` integration and shared CSS import. https://tailwindcss.com/docs/installation/using-vite
- **R5 — Storybook React/Vite.** Official framework integration. https://storybook.js.org/docs/get-started/frameworks/react-vite
- **R6 — Storybook interaction tests.** Scripted interaction and assertion support. https://storybook.js.org/docs/writing-tests/interaction-testing
- **R7 — Storybook accessibility tests.** Automated accessibility checking as part of component work, not complete accessibility certification. https://storybook.js.org/docs/writing-tests/accessibility-testing
- **R8 — Storybook network mocking.** MSW integration for later network-boundary stories; not required for initial pure fixtures. https://storybook.js.org/docs/writing-stories/mocking-data-and-modules/mocking-network-requests
- **R9 — OWASP LLM prompt-injection prevention.** External/task content is untrusted; structured separation, permission checks, and layered controls are relevant defences. This is not a proof that prompts alone can secure a system. https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html
- **R10 — TypeScript handbook, everyday types.** Type assertions/type annotations are not runtime validation; actual boundaries need runtime checks. https://www.typescriptlang.org/docs/handbook/2/everyday-types.html
- **R11 — Vite environment variables.** `VITE_*` values enter the client bundle and must not contain secrets. https://vite.dev/guide/env-and-mode


## v0.2 technical references

- **R12 — Vite 7 announcement.** Node minima and Vite 7 support from Vitest 3.2. These are compatibility statements, not secure-version certification. https://vite.dev/blog/announcing-vite7
- **R13 — Storybook 9 migration guide.** Major-version requirements, package consolidation, and the Vitest addon. Do not copy rolling latest commands when targeting 9.x. https://storybook.js.org/docs/9/releases/migration-guide
- **R14 — Storybook 9 React/Vite framework.** Integration and base requirements. https://storybook.js.org/docs/9/get-started/frameworks/react-vite
- **R15 — Storybook 9 Vitest addon.** Component tests and browser-test integration. https://storybook.js.org/docs/9/writing-tests/integrations/vitest-addon
- **R16 — TanStack Router overview.** Routing, typed location/search state, data-loading integration. https://tanstack.com/router/latest/docs/overview
- **R17 — TanStack Query overview.** Server-state fetching, caching, and update lifecycle. https://tanstack.com/query/latest/docs/framework/react/overview
- **R18 — Radix Primitives introduction.** Unstyled, customisable accessible primitives; not a visual design imposed on Desk. https://www.radix-ui.com/primitives/docs/overview/introduction
- **R19 — Microsoft MSAL React getting started.** Authentication and access-token integration. https://learn.microsoft.com/en-us/entra/msal/javascript/react/getting-started
- **R20 — Microsoft Teams JavaScript client library.** Microsoft-hosted app experiences; not a standalone learning-app requirement. https://learn.microsoft.com/en-us/microsoftteams/platform/tabs/how-to/using-teams-client-library
- **R21 — Express static files.** Static middleware for serving files; not a recommendation to replace Python domain services. https://expressjs.com/en/starter/static-files/
- **R22 — Storybook 9 network mocking.** MSW at the network boundary. https://storybook.js.org/docs/9/writing-stories/mocking-data-and-modules/mocking-network-requests
- **R23 — Streamdown usage.** Streaming Markdown and configurable content plugins. https://streamdown.ai/docs/usage
- **R24 — Streamdown security.** Sanitisation/URL controls and implications of replacing default plugins. Configuration and tests remain required. https://streamdown.ai/docs/security
- **R25 — Playwright visual comparisons.** Browser screenshot comparisons and environment-sensitive baselines. https://playwright.dev/docs/test-snapshots
