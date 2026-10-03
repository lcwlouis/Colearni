# Handoff to Codex and Claude Code

**Version:** 0.4, text only. **Date:** 30 September 2026. **Working name:** Desk. Final branding is not settled.

## What we are building

A calm, intentional learning workspace: the learner works with sources, their own notes, worksheets, worked examples and interactive teaching tools. A tutor helps without taking over. An intention-centred desk spans sessions and multiple resources; a shelf holds inactive material. The graph connects and orients knowledge without becoming a compulsory progression gate.

The founder is starting a greenfield product with lessons from `lcwlouis/Colearni` on branch `rebuild`, rather than reskinning its graph-plus-switching-panels interaction. Its documentation remains authoritative for that existing implementation, not for an unreviewed rewrite. Graph classification is one feature explicitly worth carrying forward.

## Firm boundaries

- Help is available. Teach one coherent difficulty at a time; do not interrogate beginners or flood them with prose/cards.
- The learner owns notes, responses and annotations. Tutors/plugins do not edit those documents or grant themselves access. Contributions remain separately attributed even when the learner saves them.
- Read sharing is explicit and scoped by desk. A private override wins. Linking a note does not grant another tutor access.
- Relevant saved note deltas can inform the next interaction. No grading, interruption or AI autocomplete triggered merely by typing/saving.
- Separate task versions, learner attempts and feedback. Consuming a source or moving a slider is not mastery.
- Bounded, evidence-aware research can assemble initial material and fill gaps. Research should not become an endless reading backlog.
- Host-owned actions, revisions, change sets and selective undo protect later user work. History is not permission to mutate.
- Native first-party plugins share an extensible contract. MCP Apps is a candidate interactive-host adapter, not the document store or security system.
- PostgreSQL is accepted. One Docker Compose package bundles app and database. Readable Markdown exports and restorable private backups are separate from the internal database. Two-way external file sync is not promised.
- Source-available licensing and paid managed hosting are the provisional business direction. Free personal, educational and internal workplace use is intended. This package grants no licence or authority to adopt one.

## Latest changes you must not miss

1. Every image has been removed from this package. Retire prior screenshot/layout/logo claims; none is approved. Do not retrieve old images as fallback design authority.
2. Visual exploration is **one screen/state at a time**. No multi-screen collages, multiple theme variants in one output, or automatic follow-up generations. Written review and approval precede the next view.
3. Carry forward `umbrella`, `topic`, `subtopic`, `granular` as explicit concept levels. Keep those separate from node kind, edge relation, difficulty, Bloom goals and learner evidence. Initial edge vocabulary is `contains`, `prerequisite`, `application`, `related`; extension is reviewed/versioned, not unrestricted prose. See GRAPH_MODEL.md.
4. Navigation and logo must be consistent. Collapsed sidebar uses only an approved mark; never squeeze a wordmark into the icon rail. Mobile global navigation is a drawer/menu; its bottom bar is for the current desk's tabs. The exact proposed labels still await visual review.
5. Mobile writing uses selection/long-press contextual formatting, not an always-visible desktop Markdown toolbar. Keep an accessible explicit formatting route; test native selection and browser limitations rather than promising identical native phone menus.
6. The prior dark-mode direction is rejected. Preserve the liked calm light-direction intent; investigate Singapore school-table colour inspiration for a warmer, quieter dark treatment. No specific school's palette or new hex values are approved.
7. Fast decision models are an optional experiment, not a new mandatory agent chain. Jev and Ollama System One have primary-source support; OpenAI Decisions API details remain a verification gate. Do not invent a payload/endpoint or silently fall back from local to cloud. Read DECISION_LAYER.md.

## First action in a new workspace

Inspect the actual directory, repository instructions, dirty files and existing prototype progress. Do not assume prior Claude work exists or has not happened. Keep the handoff in a clearly bounded folder until the founder explicitly adopts it. Do not overwrite repository-root AGENTS.md or CLAUDE.md blindly.

Read START_HERE.md and the boundary docs relevant to the assigned task. Report conflicts once with concrete proposed resolution. P0 is permitted only when explicitly assigned; P1 remains gated on a new selected visual reference. A minimal nonvisual editor, graph-contract or provider evaluation is a separate assignment, not automatic scope expansion.

## Working with both agents

Use one implementation owner for each unit and one reviewer. Do not let Codex and Claude simultaneously change the same schema, contracts, lockfile, navigation registry or design tokens. Prefer separate worktrees for genuinely independent work; merge reviewed changes only with founder approval. Reviewers should inspect actual diffs, execute relevant checks where available, and distinguish observed failures from speculation.

Maintain PROGRESS.md and a short NEXT_SESSION.md with task, files changed, commands/results, unresolved choices and next permitted action. No invisible background promises. No stage/commit/push/deploy/install-paid-service/licence change without explicit approval.

## Start prompts

- Codex: `prompts/CODEX_FIRST_TASK.md`.
- Claude Code: `prompts/CLAUDE_FIRST_TASK.md`.
- Both wrappers use `prompts/FIRST_TASK.md`; this is the single P0 task authority.
- Visual work: `prompts/NEXT_VISUAL_ONLY.md`, only after the founder requests that next view.
- Optional experiments: `prompts/EDITOR_SPIKE.md`, `prompts/GRAPH_CONTRACT_SPIKE.md`, `prompts/DECISION_LAYER_SPIKE.md`, or the retained MCP spike prompt. Run only the assigned one.

## What is not done

No approved logo, navigation label set, exact theme, editor selection, provider benchmark, MCP host, app implementation, deployment, live research, educational efficacy study or final licence. Documentation validation is not a claim that those systems work.

There is enough context to build bounded units and review one visual at a time. Remaining technical/legal/pilot gates are enumerated in OPEN_QUESTIONS.md; they are not reasons to postpone all work.
