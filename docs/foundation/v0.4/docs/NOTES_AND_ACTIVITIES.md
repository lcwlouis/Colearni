# Notes, worksheets and worked examples

## Shared foundation

Use one familiar editing foundation for learner notes, rich worksheet responses, scratch work and annotations. It provides desktop toolbar controls, mobile contextual formatting, Markdown shortcuts, keyboard interaction, selections, stable block IDs, saved/draft/conflict states and source links. Rich text is the default experience; Markdown syntax is optional.

The exact editor library and canonical document format are open until an evaluation exercises the requirements below. `react-markdown`/Streamdown are presentation boundaries from the frontend baseline, not a selected editing engine. Do not use a raw HTML textarea as the permanent architecture just because the first fixture is simple.

## Minimum editor behaviour

Headings, emphasis, lists, links, code blocks, quotes and a discoverable insert menu. Test tables and equations as part of the library evaluation even if introduced after the first slice. Formatting must be available without knowing slash commands. Avoid constantly appearing large toolbars, heavy animation or AI ghost-writing by default.

Autosave must preserve caret, selection, IME/composition input, undo and unsaved drafts. A saved server revision cannot replace active local typing on refetch. Empty, saving, saved, offline/disconnected, failed-save and conflict states need explicit design. Reading/writing remains useful without a model connection; this is not an offline-sync promise.

## Ownership by surface

| Surface | Learner-owned content | Separate material |
|---|---|---|
| Note | Whole editable document, including explicitly saved attributed blocks | Adjacent tutor proposals; source excerpts retain attribution. |
| Worksheet | Responses, calculations, scratch work | Versioned prompts and feedback. |
| Worked example | Annotations and a new practice attempt | Demonstration steps remain tutor/source authored. |
| Simulation | Predictions/explanations and meaningful selected state | Engine implementation and model assumptions. |
| Code activity | Learner code revisions and explanation | Suggested diffs and execution results, with origin. |

Use specialised number/code/diagram inputs where appropriate. The common foundation is ownership and behaviour, not forcing every input into Markdown.

## Feedback without surveillance

Saving means saving. The tutor may use relevant authorised saved work during the next requested teaching interaction. “Check my explanation” explicitly requests adjacent feedback for a selected passage/revision. Suggestions do not replace original writing. Do not mark unfinished draft thoughts wrong automatically.

## Reuse in the knowledge collection

A note can be linked to several desks without divergent copies. “Keep this in my notes” offers a linked reference or an explicit extraction retaining source/task/attempt origin. Later note edits do not rewrite the historic attempt. Inferred concept links need evidence and confirmation state. A quoted or generated explanation is not treated as demonstrated understanding.

## Editor selection exercise

Compare at most two credible editor candidates after checking their licences and current React/toolchain compatibility. Use the same fixture and tests: Unicode/IME; paste sanitisation; lists/code/table/math; long documents; selection/annotation anchors; Markdown round trip; mixed-origin blocks; keyboard and screen-reader path; draft-save conflicts; note/response reuse. Record limitations rather than adopting a library from appearance alone.

Initial visual implementation waits for the selected mockup. A minimal unstyled editor evaluation can be assigned separately; it does not select the product layout or justify a full notebook build.

## Mobile refinement accepted in v0.4

No always-visible desktop Markdown bar on a phone. Prefer ordinary long-press/selection behaviour with contextual formatting; an explicit accessible Format/Insert route remains available. Do not promise arbitrary native phone menu injection. The same behaviour applies to worksheet rich responses and worked-example annotations. Evaluate actual iOS/Android browsers, software keyboard, selection handles, clipboard and IME as described in MOBILE_INTERACTION.md. The user retains full ownership; mobile feedback is not a loophole for tutor edits.
