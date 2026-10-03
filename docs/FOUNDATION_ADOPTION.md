# Foundation v0.4 — repository adoption and reconciliation

**Date:** 3 October 2026. **Inspected base:** `desk` at `35bb4f3c9d9c958e79d58f88a915387f3f14c922`.

The founder requested importing the image-free Foundation v0.4 handoff into the repository. The complete 61-file package is preserved byte-for-byte under [foundation/v0.4](foundation/v0.4/README.md). This document explicitly reconciles that standalone package with existing implementation; it does not silently rewrite the supplied source.

## Authority

Explicit founder instructions and root `AGENTS.md` apply first. This adoption record resolves conflicts between the imported snapshot and the existing repo. Foundation v0.4 supplies the current product/design requirements and labelled proposals. The current package/lockfile and approved tooling decisions remain implementation authority. Runtime code describes what exists, not automatic approval to weaken product requirements.

Earlier root documentation and entry prompts are preserved under [history/pre-v0.4](history/pre-v0.4/README.md). Root documentation entry points now link to the current specifications. The decision IDs in that historical register and the snapshot are different namespaces; do not equate identically numbered proposals.

## Reconciled differences

| Topic | Repository treatment |
|---|---|
| P0 status | Preserve the completed tooling work recorded in root `PROGRESS.md`. Snapshot statements about no implementation refer to producing the standalone pack, not this repository. Do not re-scaffold. |
| Storybook / Vitest | Retain the founder-approved Storybook 10.6.0 and Vitest 4.1.11 baseline recorded in the existing decisions and package files. Snapshot references to 9/3 are historical recommendations and must not trigger a downgrade. |
| Other dependencies | Preserve `.nvmrc`, package manifest, lockfile and configurations. Re-check compatibility/security when an assigned dependency task requires it; historical audit results are not current certification. |
| Runtime contracts | Root `contracts/desk-contracts.ts`, root fixture and validators remain version 1. Snapshot version 2 is a draft migration target. Changing types, fixtures, validators and adapters requires a separate atomic, tested implementation unit. |
| Notes and activities | Reusable note identity, per-desk access, distinct activity/attempt/feedback, and the shared rich editor supersede the earlier desk-local/plaintext-only product placeholder. These are requirements, not shipped features. |
| Graph | Carry explicit umbrella/topic/subtopic/granular levels and reviewed relationship vocabulary; no hierarchy-based mastery or restored graph-first product flow. |
| Visuals | Root `docs/VISUAL_SELECTION.md` is the live approval record. All earlier mockups are retired; one screen/viewport/theme/state per explicitly requested review. No A/B/C collage requirement survives. |
| Mobile/theme/brand | Global drawer and desk-local bottom tabs; contextual mobile formatting with accessible fallback; stable navigation; no invented approved logo or palette. Follow the new dedicated specs. |
| MCP / decisions | Independent optional spikes, not mandatory services or installed capabilities. Historical provider claims are not reverified by importing docs; verify primary contracts/access before implementation. |
| Self-hosting / licence | PostgreSQL and bundled Compose are accepted directions. Readable exports are not live folder sync. Licensing intent is not a grant or an instruction to add MIT/AGPL/custom terms. |

The existing Sep 27 tooling decision history is retained in [historical DECISIONS.md](history/pre-v0.4/docs/DECISIONS.md); its evidence remains in [root PROGRESS.md](../PROGRESS.md). It outranks inherited 9/3 instructions regardless of the snapshot's later document date.

## Scope and preservation

No application source, active contract, fixture, dependency, lockfile, tool configuration, source asset or existing progress log is changed. Root entry docs are reconciled, previous versions archived, and the supplied package is added as a versioned source snapshot. The large line count is the requested full document import, not a large implementation change. No image or additional mockup-prompt pack is included.

Keep the snapshot immutable so its manifest remains verifiable. Amend this adoption record for repository exceptions; use a new reviewed version for later baseline revisions. Its nested `AGENTS.md` remains subordinate to the repository's root rules.

## Next work and verification

Use [the resume prompt](../prompts/RESUME_DESK.md), not the snapshot's new-workspace P0 task. P1 is still gated; migration and optional experiments need separate assignments. See [import validation](FOUNDATION_IMPORT_VALIDATION.md). Imported tests/types do not certify application behaviour, security, model quality, or educational efficacy.
