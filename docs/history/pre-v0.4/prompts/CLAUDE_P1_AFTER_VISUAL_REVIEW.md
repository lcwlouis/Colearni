# Claude task — selected-reference card and notes slice

Use Desk foundation v0.2. Read the directory's `AGENTS.md`, `docs/FRONTEND.md`, `docs/INTERACTION_CONTRACT.md`, P1 in `docs/WORK_PLAN.md`, and `docs/VISUAL_SELECTION.md`.

Prerequisites: P0 tooling exists; a selected reference is accessible; the founder approved it and the decision is recorded or can be accurately transcribed from their explicit approval. If any prerequisite is missing, report it and stop visual implementation rather than inventing or silently approving a design.

Implement **P1 only** against the selected reference: shared CardShell, source/provenance display, learner-owned note editor, separate tutor contribution, explicit save-with-origin, read-sharing states, and failure/permission stories. Do not build every card in a mockup or implement the full desk. Reuse existing scaffolding and keep the validated workplace-aligned major versions.

Use semantic tokens and enumerated component variants. Radix/cva/tailwind-merge/lucide are appropriate building blocks; they are not a reason to adopt a generic dashboard aesthetic. App and Storybook share CSS. Keep tokens, primitives, domain rules, and adapter access separate.

Keep the card/notes permission contract authoritative over visual imagery. No agent command may edit learner note text or sharing. Private note metadata/content stay out of mock context. Persist generated provenance after an explicit learner save. Reject invalid commands in mock domain tests, not only by hiding a button.

Include all P1 stories, long content, narrow viewport, clear keyboard focus, and errors. Test interaction behaviour and accessibility with the version-correct Storybook tooling. Inspect actual browser renderings at reference and narrow sizes; report discrepancies and unavailable checks. Do not shrink text or remove ownership/privacy controls to imitate a mockup. Generated images are references, not executable specifications or screenshot-regression baselines.

No production backend, live model calls, uploads, arbitrary JavaScript, plugin downloads, or new authentication. A simulation shown in the reference may remain a clearly labelled illustrative support card until P3, not a claim of a working engine.

Update progress with actual results and screenshots only if captured. Stop after P1 for review. No commit, push, deploy, or automatic P2.
