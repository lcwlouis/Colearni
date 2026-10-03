# Progressive note context

## Desired behaviour

The tutor can know relevant shared notes exist, see selected recent changes automatically, and request additional passages when needed. It must not receive every note in full or react to every keystroke.

Read access does not grant write access. The current desk has a disclosed tutor-read default. Notes have independent identity, a private override and explicit per-desk read grants; a link to another desk does not silently expose the note there. The application presents “Used from your notes” information showing which revisions/passages were actually included, rather than equating retrieval with complete model comprehension.

## Proposed flow

Learner edits → save commits a revision → emit a deduplicated metadata event → check current permissions → update shared-note index → select bounded relevant changes for the next tutor turn → tutor may request a scoped passage.

An in-flight model request is not silently rewritten when the learner keeps typing. The next turn uses the latest authorised state. Debounce editor saves and coalesce intermediate revisions. Idle saving must not depend on focus loss, and typing should remain usable while save feedback updates.

## Three context layers

**1. Small index.** Include allowed notes' IDs, titles, current revisions, linked concepts, and changed block IDs. Use selected/current notes plus a bounded relevant list. Private or out-of-scope notes do not appear, including their titles.

**2. Recent saved-change excerpt.** When relevant and within budget, include the actual newly saved paragraphs or changed blocks. Label them as learner-provided observations, with note ID, revision, block IDs, and whether truncated. Do not silently present an AI summary as the original note.

**3. On-demand passage reads.** The tutor requests a specific authorised note revision and block/range. The trusted service rechecks current sharing and desk scope on every read. Excess content is paginated; stale versions are rejected or explicitly reported. Note reads share a total retrieval budget with paper/source reads.

Example: “Note n1 changed from revision 2 to 3; blocks p2–p4 were updated. Here are selected saved passages. Additional content is available through the note reader.” The quoted passages carry the original learner wording; the system label does not endorse it.

## Starting budgets — proposed, not pedagogical facts

Prototype fixtures should exercise an index of at most 8 relevant notes, recent deltas totalling at most 800 tokens, and at most 2 note-read calls per tutor turn. Production must use the active model's tokenizer and one global context/retrieval budget. Adjust these values from traces and learning tests, not folklore. If no tokenizer is present in the prototype, label its size estimate approximate.

For a three-paragraph addition, include the saved paragraphs when authorised, relevant, and within budget. Otherwise provide metadata and fetch only the necessary section. Do not trigger an LLM summarisation call for every edit; the first implementation can perform deterministic block diffs. A later compact summary must identify covered revisions and distinguish quotation from inference.

## Privacy and stale context

Apply current permissions before index generation, delta selection, retrieval, caches, and model dispatch. On note deletion or sharing revocation, invalidate relevant cached chunks and summaries, remove queued excerpts, and rebuild future context. A late event for an old shared revision must not reintroduce now-private text. Derived context needs provenance so invalidation can find it.

Revocation cannot recall content already sent to an external provider. Disclose that limit. Cancel in-flight work where possible and prevent stale responses from causing new actions. Do not claim the provider has “forgotten” the content; provider-side retention/deletion requires a separate production policy.

Saved notes may contain mistaken statements or adversarial instructions. Separate them from system instructions, and validate any resulting tool/action request independently. [R9]

## Learning and graph use

A note can identify a question, confusion, tentative connection, or possible strength. It cannot automatically prove mastery: the text may be copied, assisted, or untested. Store suggested links with the supporting note passage, origin, and confidence/confirmation status. Do not propagate mastery across linked concepts.

## Required scenarios

A relevant three-paragraph addition appears once; rapid edits coalesce; a private note never enters the index; an oversized edit produces a bounded excerpt and read option; an out-of-order event is ignored; revocation blocks queued/derived excerpts; a stale semantic target fails safely; a proposed tutor contribution cannot mutate the note.

These scenarios initially use a deterministic context-preview fixture. No real note content is sent to a model in the Storybook prototype.

## v0.3: activities and MCP view context

Apply the same bounded authorised-context principles to saved worksheet responses and annotations, respecting their distinct task/revision and sharing rules. A draft save is not a submission or a feedback request. Keep response text separate from generated questions and worked solutions.

MCP view context has its own latest-update semantics; it does not replace native note context or our append-only observations. Treat app-supplied data as untrusted and scoped to the app/card, not as authority to read private notes or trigger tutoring. No LLM call is required for each context update. See MCP_APPS.md.

## v0.4 — quiet decisions

A saved note event does not trigger a tutor reply or a classifier assessment of every draft. An optional relevance selector may operate on already-authorised context at a relevant interaction. It must not see private note text or infer that model-speed improvements authorise automatic critique. Sharing revocation invalidates queued content, derived context and unapplied results as specified above. See [DECISION_LAYER.md](DECISION_LAYER.md).
