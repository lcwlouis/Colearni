# Interaction, ownership and history contract

## Stable host shell

The host owns card titles, author/source labels, permission controls, focus, loading/error/fallback states, layout, provenance and revision controls. Native structured content cannot inject arbitrary HTML, CSS classes, JavaScript or resource URLs. An MCP App is a separately declared executable view loaded only through the reviewed adapter, never a loophole in native Markdown rendering.

Text labels communicate ownership in addition to colour. A source passage, tutor contribution and learner response must remain distinguishable at a glance and to assistive technology.

## Semantic targets

Targets reference an object ID, revision and stable block/step/cell/code/plot identity. The host resolves a target before acting. Stale targets report unavailable or undergo an explicitly reported re-resolution; do not highlight a convenient nearest match. Cross-iframe highlighting needs a negotiated Desk profile; the host cannot inspect or manipulate arbitrary app DOM.

## Attention policy

Preserve the active reading/writing task. The tutor may add bounded support in a predictable area or place found resources on the shelf. It must not move focus, automatically switch tabs, rearrange notes, expand to fullscreen or flood the desk. Dismissal and pausing interventions remain available. A requested expansion is controlled by the learner.

One primary activity plus optional support is a starting layout hypothesis, not a fixed limit on what a desk can contain. Browser/animation events are not all learning events.

## Mutation authority

| Operation | Learner | Tutor | Embedded app/plugin |
|---|---|---|---|
| Edit note or response | Through trusted owner action | No | No direct host-document write |
| Change note sharing | Explicit action | No | No |
| Read note | According to actual permissions | Scoped shared context service | Not unless separately approved scoped input; default none |
| Add support | Yes | Within budget and allowlist | May request a narrowly allowed own-card action |
| Replace learner work | Explicit review, preserve history | Proposal only | No |
| Suggest link | Yes | Labelled proposal | Only through an approved capability |
| Save own activity state | Yes | Approved typed action | Validated through host, not arbitrary mutation |
| Install plugin/server | Later explicit approval workflow | No | No |
| Award understanding | Not a cosmetic button | Only validated evidence process | No |

Production derives identity from authenticated context. A frontend button, actor string, origin badge or app declaration is not authorisation. Host-owned confirmation is required for importing a plugin/tutor contribution into protected writing. A malicious app can forge an internal click event; it cannot attest that the learner consented.

## Origin versus acceptance

A learner accepting content does not become its original author. Source quotes and generated text retain provenance in blocks and exports. Do not assert independent authorship for mixed-origin notes. Manual paste origin may be unknown; be honest about detection limits.

## Revisions and undo

Record object revisions and a grouped atomic change with before/after pointers, actor and idempotency key. Generate proposals outside transactions. Check current permission and expected revision again before applying.

Undo is a new targeted reversal. Tutor adds card → learner edits note → undo card: note survives. If a card has acquired learner annotations or newer dependencies, a conflict preserves them and requests a reviewed resolution. A whole-desk checkpoint restore is separate and previews its scope.

Database rollback cannot reverse external disclosures, emails, charges, network side effects or already sent model context. Such operations need explicit consent and, where available, separate compensating actions. Do not replay them when restoring state.

## Accessibility and failure

Provide keyboard paths, visible focus, named controls, accessible state announcements, readable contrast, reduced motion and a linear small-screen path. Avoid whole-card live announcements during typing or streaming. Preserve source/notes when a plugin fails. An iframe must have an accessible title and a way to leave it with the keyboard; provide fallback content outside it. Automated checks supplement manual review, not certify accessibility.

## Privacy across time

Current permissions always outrank historical permissions. Revoked/deleted data must be removed from future context and derived caches. Existing provider transmissions cannot be recalled by local undo. Deletion and backup-retention rules must be stated before real data is stored.

## v0.4 graph, navigation and optional decisions

Concept levels and typed relationships follow GRAPH_MODEL.md. Mobile global destinations live in a drawer; bottom navigation represents current-desk tabs. Shell/brand identity cannot drift with active card, collapsed state or theme. Mobile rich writing has contextual formatting rather than a persistent desktop toolbar. These changes apply equally to native cards and the host around an MCP app.

A decision-model result is a fallible recommendation, not a privileged command. Deterministic policy filters eligible context and candidate actions first, validates the outcome and current revisions afterward, and retains exclusive control over permissions, learner writing, evidence and change sets. No extra autonomous critique is authorised by a saved note event.
