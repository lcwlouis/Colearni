# Desk — product, design and engineering foundation

**Version 0.4 · 30 September 2026 · Text-only handoff · Working name: Desk**

This is a complete documentation handoff for Codex and Claude Code, not an application. It retains the v0.3 product, notes, research, MCP Apps, storage and business plan, adds the graph/mobile/theme corrections, and evaluates an optional fast decision layer.

## Authority and import

Start with [HANDOFF.md](HANDOFF.md). Adopt this package only inside an explicitly selected new Desk workspace. It supersedes earlier handoff versions there; it does not silently replace existing repository rules or erase prior work. Inspect any implementation before changing it. Accepted decisions are not scientific validation, draft types are not runtime security, and design proposals are not founder approvals.

**No images are included or approved.** All prior generated mockups are retired. No image generation occurs as part of this update. One requested screen/state is reviewed before any subsequent visual is produced.

## Give the coding agent this directory

Extract the ZIP. Use `prompts/CODEX_FIRST_TASK.md` or `prompts/CLAUDE_FIRST_TASK.md`; both point to the same [P0 instruction](prompts/FIRST_TASK.md). The consolidated document is an alternative reading copy, not an additional required file.

P0 authorises tooling and contract readiness only. P1 visual implementation waits for a new accepted reference and a scoped assignment. Optional experiments have separate prompts and are never automatically run as part of P0.

## Reading order

1. [Product](docs/PRODUCT.md), [decisions](docs/DECISIONS.md), [glossary](docs/GLOSSARY.md).
2. [Journeys](docs/USER_JOURNEYS.md), [pedagogy](docs/PEDAGOGY.md), [interaction rules](docs/INTERACTION_CONTRACT.md).
3. [Graph](docs/GRAPH_MODEL.md), [notes and activities](docs/NOTES_AND_ACTIVITIES.md), [context](docs/NOTES_CONTEXT.md).
4. [Architecture](docs/ARCHITECTURE.md), [data model](docs/DATA_MODEL.md), [security](docs/SECURITY_PRIVACY.md).
5. [Frontend](docs/FRONTEND.md), [navigation/brand](docs/NAVIGATION_AND_BRAND.md), [mobile](docs/MOBILE_INTERACTION.md), [theme brief](docs/THEME_BRIEF.md).
6. [Visual process](docs/VISUAL_BRIEF.md), [selection status](docs/VISUAL_SELECTION.md), [work plan](docs/WORK_PLAN.md).
7. Read [research](docs/RESEARCH.md), [plugins](docs/PLUGINS.md), [MCP Apps](docs/MCP_APPS.md), or [decision layer](docs/DECISION_LAYER.md) only for the relevant unit.
8. [Self-hosting](docs/DEPLOYMENT_AND_PORTABILITY.md), [licensing/business](docs/LICENSING_BUSINESS.md), [tests](docs/TEST_PLAN.md), [open gates](docs/OPEN_QUESTIONS.md).

AGENTS.md applies within the adopted scope. PROGRESS.md records observed implementation state. VALIDATION.md covers only the documentation package.

## Continuity

Ghost refers to a specification-led, small-step, verified engineering process, not a required IDE or later framework rewrite. The existing CoLearni rebuild remains a reference with authoritative docs for its own implementation. Its graph rules were re-read for this update. [R1, R2, G1]

Earlier source-ledger entries are retained as historical references; the v0.4 research ledger identifies what was newly checked. Exact package compatibility, device behaviour, API access, runtime isolation and model results must still be verified at implementation time. No pricing or performance marketing claim is a Desk benchmark.
