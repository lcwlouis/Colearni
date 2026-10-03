# Desk — foundation and frontend handoff

**Version:** 0.2 · **Prepared:** 27 September 2026  
**Status:** discussion-derived product baseline, workplace-aligned frontend recommendation, and visual-design brief.  
**Working name:** Desk. Final branding remains open.

## What changed

The founder supplied the exact workplace stack. This revision records that reference and proposes a deliberate subset for Desk. It also adds a visual-selection gate: the coding agent can perform P0 tooling/contract work now, but learner-facing components in P1 and the composed desk wait for an approved visual reference.

This replaces the v0.1 first-task authorisation to do P0 and P1 together with provisional styling. It does not undo any existing prototype work; inspect and preserve work already started, then bring it through the new review gate.

## What this package is

Specifications and handoff material, not a running application. No mockup images, selected visual direction, installed dependencies, or browser-verified screens are included. `docs/VISUAL_BRIEF.md` describes the proposed visual exploration; `docs/VISUAL_SELECTION.md` is deliberately pending. Existing contracts and synthetic fixtures are unchanged from v0.1.

No live repository was changed, committed, or pushed. TypeScript types are a vocabulary seed, not production authorisation or runtime validation.

## Start now

Give Claude `prompts/CLAUDE_FIRST_TASK.md` plus this whole directory in an explicitly selected isolated prototype workspace. P0 covers tooling, empty Storybook configuration, a minimal smoke story, and pure contract checks—not a designed application shell.

In parallel, use `docs/VISUAL_BRIEF.md` to compare layout directions for the same learning moment. Select one reference and record the decision in `docs/VISUAL_SELECTION.md`. Then give the coding agent `prompts/CLAUDE_P1_AFTER_VISUAL_REVIEW.md` and the actual selected images. Do not give a coding agent three competing mockups as equally authoritative references.

Read in order:
1. `docs/PRODUCT.md`
2. `docs/DECISIONS.md`
3. `docs/INTERACTION_CONTRACT.md`
4. `docs/FRONTEND.md`
5. `docs/VISUAL_BRIEF.md` and `docs/VISUAL_SELECTION.md`
6. The assigned unit in `docs/WORK_PLAN.md`

`AGENTS.md` governs this prototype only. `PROGRESS.md` must describe actual results, not planned features.

## Existing project and Ghost

The existing `lcwlouis/Colearni` rebuild remains authoritative for its own implementation. This package describes the founder's requested greenfield direction; it does not silently supersede repository instructions. Preserve source privacy, ownership, and review safeguards without reproducing the old graph-and-panel flow. Adopting the pack into that repo requires an explicit supersession boundary. [R1]

Ghost supplies a spec-led, incremental, verified workflow—not a required hosting environment, frontend framework, or second future rewrite. The same workflow can guide Claude and a Vite frontend. [R2]

## Interpretation

Accepted product decisions record the conversation, not user-study results. Workplace technologies are facts supplied by the founder. Their adoption in Desk is a proposed implementation baseline, not automatic approval of every integration. Exact resolved versions, visual direction, final hosting, authentication, and production plugin isolation still require appropriate checks. See `CHANGELOG.md` and `VALIDATION.md`.
