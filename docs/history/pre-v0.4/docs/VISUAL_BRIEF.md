# Visual exploration brief — Desk

**Status:** proposed exploration, not an approved UI. No mockup images have been generated or reviewed as part of v0.2.

## Purpose

Decide how a persistent learning desk lets a person work with a source, their own notes, and situated help without becoming a dense AI dashboard. The comparison is about information hierarchy, workspace behaviour, and ownership—not three colour palettes.

Target: a responsive web application, desktop-first for comparing source material and learner work, with a credible narrow-screen reading/editing path. Working label: Desk, not a final logo/brand. The source, activity, and note must remain meaningful at actual reading size.

## One shared learning moment

Use `fixtures/paper-session.synthetic.json` as the only source content. It describes a deliberately synthetic source, not a published research paper or actual uploaded PDF.

The learner wants to explain y = a*x + b and predict a new output. They are reading the source passage, writing why changing b shifts every output, and considering why changing a affects negative and positive inputs differently. The tutor offers one short worked example or the reviewed affine-function explorer as support.

Every option should show the same capability goal, source passage and locator, learner note, a small distinct tutor contribution, and a supported activity. Do not show all generated tools expanded at once. A focus state may keep some material one action away rather than compressing everything into narrow columns.

Useful visible copy:
- Goal: Explain the relationship and predict a new output.
- Source: A Simple Score Transformation — synthetic example.
- Learner note: Changing b adds the same amount to every output.
- Learner question: Why does changing a affect negative inputs differently?
- Tutor contribution: Keep b fixed. Compare the outputs at x = -2 and x = 2.
- Note access: Available to tutor / Private to me.
- Support action: Open a worked example / Explore the relationship.

Longer fixture content remains accessible. Do not falsely cite this material as a real research finding.

## Three proposed layout directions

### A — Reading desk

A source-focused reading area with a clear adjacent note area. Short tutor contributions appear beside their semantic target or in a stable supporting area; tutor chat is secondary. The original source is easy to return to. Restrained document-like typography and a minimal outline orient the learner.

Question tested: Can source and notes remain visible at readable widths while relevant help is nearby?

Tradeoff: Strong source continuity; less space for large simulations unless the learner explicitly expands the activity.

### B — Guided workbook

One central activity with deliberate pacing and a learner-owned response area. Source context opens beside the activity or in a consistent inspectable drawer. Progress describes the current goal and next step, not a mastery percentage or gamified score. Notes persist across activities.

Question tested: Does focusing on one coherent activity reduce overload without hiding the source or trapping the learner in a rigid lesson?

Tradeoff: Strong focus; must make exploration and returning to earlier work easy.

### C — Research workbench

An organised, explicitly arranged source / work / support composition with a small number of cards. The learner may deliberately expand a simulation or comparison. Notes are visibly owned and stay stable. No physics-driven graph, free-scrolling infinity, or automatic rearrangement.

Question tested: Can multiple representations support comparison without turning the space into a control panel?

Tradeoff: More comparison power; higher risk of visual density and undersized reading areas.

A is the initial recommendation to test for the paper journey, not a selected design. Neither the renderer contracts nor the final application architecture should hardcode this preference.

## Invariants visible in every option

- Learner notes, tutor text, and source material have distinct labels and boundaries; colour alone does not establish ownership.
- Read-sharing is clear and reversible. Reading permission is not writing permission.
- One obvious current task, with depth available through progressive disclosure.
- Automatic support additions occupy a predictable place without stealing focus or moving the note editor.
- Source passages and equations have stable semantic targets and understandable locators.
- Generated material can be inspected, dismissed, or selectively undone. Important actions have persistent history, not only a disappearing toast.
- No fake streaks, fabricated usage metrics, invented mastery percentages, promotional dashboard, or giant chat feed.
- No claim that a mockup validates security, execution correctness, learning quality, or accessibility.

## Exploration sequence and gates

**V0 — Compare layouts:** create one mid-fidelity static mockup per direction using the same scenario and viewport. Prefer a 1440 x 1000 desktop reference; dimensions are review targets, not a fixed production layout. Do not spend the first round polishing logos or filling the app with unrelated features.

**V1 — Select and exercise one direction:** explicitly choose a direction before producing a more detailed state board. Show reading, editing a shared note, receiving a tutor addition, a private-note state, a selective undo/conflict state, and a narrow-screen variant. Record what stays fixed and what may change. This state board may be completed alongside component review; it does not require implementing all later subsystems in P1.

**V2 — Implement the selected slice in Storybook:** translate the chosen hierarchy into real tokens, components, and interactions. Test actual reading density and focus. Use a reviewed browser render for later pixel comparisons.

Do not merge all three options automatically. Choose one structure, then record specific borrowed elements if necessary.

## Review questions

Can a new learner locate the source, their own work, and the immediate next action? Can they tell what the tutor wrote and what it can read? Does opening an explanation preserve their position? Is there a credible place for a larger diagram or code example? Are paragraphs readable without excessive scrolling? What does the interface do when it cannot provide an interactive tool?

Assess how the layout supports the task, not which screenshot looks most impressive. Static images cannot prove keyboard/focus handling, editor reliability, animation behaviour, or responsiveness; those require a working slice.

## Selected-reference handoff

Give the coding agent only the selected primary reference, approved state variants, exact available asset paths, and `VISUAL_SELECTION.md` with a reviewer decision. Include approved tokens, dimensions as guidance, component mapping, responsive rules, forbidden changes, and acceptance stories. Do not describe an ungenerated or absent image as approved.

If a reference disagrees with ownership/privacy rules, the product contract wins; flag the discrepancy instead of copying a forbidden interaction. Ask for design review when the reference cannot fit real content rather than shrinking text silently.
