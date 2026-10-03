# Contract version 2 — design migration notes

This replaces the v0.1 TypeScript vocabulary bundled in v0.2. It is not a migration applied to a live database or implementation.

- `LearnerNote` becomes an independent `LearnerDocument` with workspace/owner identity, a private override, and explicit `DeskDocumentLink` entries. Remove the assumption that a note belongs to exactly one desk.
- A desk contains card/document references; cross-desk linking never implicitly grants tutor access.
- Add activity definition, response/attempt and feedback separation; example annotations remain learner-owned.
- Card bodies distinguish native text, document references, activity references, native plugin binding and optional MCP App binding.
- MCP fields in the Desk record are our metadata, not standard wire protocol. Permissions live in a trusted registry/service, not in a model-supplied card.
- Add latest app context envelope separately from immutable learning observations; context updates do not auto-submit or grade.
- Contract version becomes `2`; fixtureVersion is `2`. Existing prototype data needs an explicit conversion preserving note origin, privacy, task versions and unknown fields.
- The `desk-blocks/0.3-draft` fixture payload is deliberately minimal. It does not select a rich-text engine or guarantee lossless Markdown round trips.

TypeScript checking proves syntax/type consistency only. Production requires runtime validation, current authorisation, revision checks and malicious-input tests. The included JSON Schema only illustrates the candidate MCP binding boundary; it does not validate every entity or secure a host.

## Documentation v0.4 — additive proposals only

The existing core contract version remains `2`, and the existing paper fixture remains version `2`. The `desk-blocks/0.3-draft` identifier is retained deliberately: a documentation revision does not silently migrate persisted editor content.

New independent draft modules `graph-contracts.ts` and `decision-contracts.ts` add vocabulary for an explicit graph and optional provider-neutral decisions. The associated synthetic fixtures have their own version `1`; these are not vendor wire examples, generated provider results, full schemas or production migrations. The relation-schema identifier is `desk-relations/1-draft` pending implementation review. No migration has run.
