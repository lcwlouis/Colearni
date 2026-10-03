# Source ledger and evidence status

**Updated 30 September 2026.** Product decisions are from the conversation and are not external evidence of effectiveness. The v0.4 section at the end records this update's checks. MCP/storage/licensing references below were inspected for the previous 29 September handoff, not reverified wholesale in this update. SDK/website statements do not establish that Desk has implemented or tested them. References are linked for attribution; no vendor source or skill text is redistributed in full.

## v0.3 MCP Apps sources — retained history

- **M1 — MCP Apps overview.** Tool-linked interactive HTML, isolated host rendering and framework-neutral approach. https://modelcontextprotocol.io/extensions/apps/overview
- **M2 — Build an MCP App.** Server/UI distinction, Vite example, optional official coding-agent skill and example testing. https://modelcontextprotocol.io/extensions/apps/build
- **M3 — Linked specification, 2026-01-26 path.** Tool/resource metadata, app/model visibility, messages and host requirements. Path is the linked reference, not a claim that every client supports the same latest revision. https://github.com/modelcontextprotocol/ext-apps/blob/main/specification/2026-01-26/apps.mdx
- **M4 — AppBridge API.** Host communication, lifecycle and sandbox-proxy interfaces. https://apps.extensions.modelcontextprotocol.io/api/classes/app-bridge.AppBridge.html
- **M5 — McpUiUpdateModelContextRequest.** Latest view context replacement without an automatic follow-up; typically deferred to next user message. https://apps.extensions.modelcontextprotocol.io/api/interfaces/app.McpUiUpdateModelContextRequest.html
- **M6 — McpUiHostContext.** Host styles/theme, dimensions, device and display information. https://apps.extensions.modelcontextprotocol.io/api/interfaces/app.McpUiHostContext.html
- **M7 — McpUiResourceCsp.** Declared asset/network/frame/base origins and host enforcement context. https://apps.extensions.modelcontextprotocol.io/api/interfaces/app.McpUiResourceCsp.html

## v0.3 storage and licensing sources — retained history

- **D1 — Docker Compose application model.** Services, networks and volumes in a bundled configuration. https://docs.docker.com/compose/intro/compose-application-model/
- **D2 — Docker volumes.** Docker-managed storage and independent container lifecycle. https://docs.docker.com/engine/storage/volumes/
- **D3 — Docker bind mounts.** Host-visible folders, write access risks and Docker-host/client distinction. https://docs.docker.com/engine/storage/bind-mounts/
- **D4 — PostgreSQL SQL dump.** Consistent database snapshot; external assets remain an application backup responsibility. https://www.postgresql.org/docs/current/backup-dump.html
- **L1 — Open Source Initiative definition.** Commercial-field restrictions are inconsistent with the definition. https://opensource.org/osd
- **L2 — MIT licence text.** Broad permissions and notice condition. https://opensource.org/license/mit
- **L3 — GitHub Open Source Guides, legal side.** Licensing, contribution and dependency considerations. https://opensource.guide/legal/

## Earlier references retained from v0.2

These were supplied in the preceding pack. They were not all independently reopened for v0.3. R4 and R14 were reopened; R12 refetch failed in this pass. Do not treat the inherited ledger as a fresh package-security or compatibility audit. Exact software choices require current checks during installation. Repository references describe the previous project context, not a newly audited implementation. No full video transcript or new learning-science verification is claimed.

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

## v0.4 checked references — 30 September 2026

These entries support narrow technical facts, not implementation, legal advice, model quality or interface approval. Prior sections remain historical; they were not all reverified for this revision. No private project source was replaced by a public search result.

- **G1 — CoLearni rebuild graph rules.** GitHub `lcwlouis/Colearni`, `rebuild/docs/GRAPH.md`, blob `299996d48c61252ad7f67bfdff7eb02b899e15e2`, fetched through the connected GitHub read action. Four explicit concept levels and the prerequisite/contains/application/related vocabulary; level is not an edge; budgeted traversal and focused graph presentation. https://github.com/lcwlouis/Colearni/blob/rebuild/docs/GRAPH.md
- **U1 — MDN Selection API.** Browser selection access/events; does not promise arbitrary OS-native context-menu entries. Device behaviour remains to be tested. https://developer.mozilla.org/en-US/docs/Web/API/Selection_API
- **U2 — W3C WCAG 2.2 target size (minimum).** Distinguish the standard and its exceptions from our proposed larger touch-target design aim. https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- **U3 — W3C contrast minimum.** Contrast must be measured on actual foreground/background pairs, not inferred from mockups. https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
- **S1 — TypeSafe AI official site and provider introduction.** Primary indexed provider content identifies Jev as a System One decision model. Provider accuracy/calibration/latency marketing is not a Desk benchmark. A complete primary SDK/API contract was not verified; direct retrieval of the introduction was inconsistent. https://typesafe.ai/ and https://typesafe.ai/blog/introducing-system-one-models-and-jev
- **S2 — Official Ollama Python README.** Connected GitHub fetch of `ollama/ollama-python/main/README.md`, blob `9f72ba63cef720c6881d9948ef50b6e041d764c1`. System One API section supplies the route, compatible local model/runtime requirement, typed outputs and caution about confidence. Snapshot is not an installed version. https://github.com/ollama/ollama-python/blob/main/README.md
- **S3 — Official OpenAI Structured Outputs guide.** Reference for a conventional schema-output baseline; not evidence of the new Decisions API contract. https://developers.openai.com/api/docs/guides/structured-outputs
- **S4 — Official OpenAI API changelog.** Checked as a primary discovery source; accessible material did not verify the named Decisions endpoint or request/response schema. Absence here is not proof of nonexistence. https://developers.openai.com/api/docs/changelog
- **S5 — OpenAI Developer Community, DevDay 2026 announcements and developer resources.** Post by `N2U`, dated 29 September 2026, mentions Decisions API. **Discovery lead only, not verified primary API documentation.** Do not use it to invent integration details, eligibility, pricing or model IDs. https://community.openai.com/t/devday-2026-announcements-and-developer-resources/1402006

No school photo or national furniture-colour specification was inspected for v0.4. The Singapore school-table reference is the founder's visual direction and remains unselected. No image is embedded or distributed in this package.
