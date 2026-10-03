# Verification and learning-quality plan

Planned tests are not test results. PROGRESS.md and VALIDATION.md record what actually ran.

## Testing layers

Use pure contract/state tests for permissions, revisions and calculations; Storybook interaction stories for component behaviour; browser tests for focus, actual iframe/CSP/network behaviour and composed flows; human review for visual clarity, accessibility and subject-matter correctness. MSW mocks HTTP boundaries when applicable, not security mechanisms that require actual browser enforcement. [R6, R7, R22, R25]

## Required cases

| ID | Scenario | Expected invariant |
|---|---|---|
| T01 | Tutor/plugin submits note edit | Trusted service rejects; content and revision unchanged. |
| T02 | Tutor/plugin changes sharing | Rejected even if a client actor field says learner. |
| T03 | Private note indexed/read | Neither title nor content enters tutor context. |
| T04 | Note linked to second desk | No implicit grant; one document identity. |
| T05 | Three paragraphs saved rapidly | Coalesced authorised delta, no per-keystroke model calls. |
| T06 | Sharing revoked before dispatch | Queued excerpts/derived caches removed; late event cannot restore them. |
| T07 | Source contains instructions | Untrusted content cannot grant capabilities. |
| T08 | Typing while Query refetches | Draft/caret preserved; conflict visible. |
| T09 | IME/Unicode/keyboard formatting | No dropped input; same document via toolbar/shortcuts. |
| T10 | Markdown round trip | Supported content preserved; losses reported, not hidden. |
| T11 | Worksheet regenerated | Old attempt references original revision and survives. |
| T12 | Example saved in notes | Generated/source origin retained. |
| T13 | Draft save | Does not submit for assessment or trigger unsolicited critique. |
| T14 | Support added during writing | No focus theft or automatic layout switch. |
| T15 | Undo support after note edit | Later writing preserved. |
| T16 | Undo with dependent learner work | Conflict, not destructive deletion. |
| T17 | Retried operation | Same idempotency key cannot create duplicate cards. |
| T18 | Stale semantic target | Safe rejection/explicit retargeting; no guessed highlight. |
| T19 | Affine explorer | Verified numeric cases and labelled accessible table alternative. |
| T20 | Unknown/failed plugin | Fallback and saved state preserved. |
| T21 | Research missing/full text unavailable | Accurate access status; no invented citation. |
| T22 | Private data requested for external search | Separate disclosure control; minimal allowed query. |
| T23 | Research redirect/internal URL | Network policy rejects forbidden targets. |
| T24 | Return session | Reopens work; optional check; no automatic remote mutation replay. |
| T25 | Backup restore on fresh instance | Notes, attempts, links, origins and supported state survive. |
| T26 | Import hostile archive | Reject traversal, oversized files, invalid identities and executable autoload. |
| T27 | Workspace A requests B's object | Denied server-side across API, cache, source and download paths. |
| T28 | Model/provider fails | Learner can still save/read work and receive clear status. |

## MCP-specific spike cases

- Negotiate supported version/capabilities; reject or fall back on incompatibility.
- Fetch a registered UI resource and validate expected MIME, size, origin and allowed release.
- Verify frame-to-host communication identity and malformed payload rejection.
- Deny undeclared network requests, unsupported tools, capability escalation and private-note mutation.
- Parameter changes update latest view context without automatically scheduling a model response; keep host learning history separate.
- Test inline dimensions/theme, controlled expansion, title, keyboard exit, reduced motion and readable fallback.
- Disconnect/teardown/reload preserves registered saved state and does not duplicate operations.
- App cannot fake a host consent action or approval badge.
- No real notes/keys leave the fixture. Browser tests must exercise actual CSP/iframe behaviour; a mocked permission test is not sandbox verification.

## Pilot learning checks

Recruit and define the adult pilot audience before interpreting efficacy. Use a reviewed small learning task, an independent application/explanation and a later optional check. Record assistance and grading uncertainty. Have subject reviewers inspect correctness and a sample of evaluations. Track whether users find a starting point, request useful help, retain control and return. Do not equate satisfaction or generated output volume with learning.

## Release readiness

Security, restore, privacy, accessibility and source-fidelity gates precede private uploads/public accounts. Managed billing needs provider-cost controls and failure handling. School/minor use has a separate review gate. No test suite proves absolute security or universal teaching effectiveness.

## v0.4 additional acceptance scenarios

Graph: all four levels/kinds validated separately; unknown relation rejected; confirmed contains/prerequisite cycles rejected; proposed cycles cannot become confirmed; scope/endpoint checks; related-edge deduplication; no automatic note access or learner mastery from linking.

Navigation: expanded rail, collapsed rail and mobile drawer resolve the same global IDs/order; local bottom tabs use desk IDs; selected icon/label and accessible state agree; no fallback to old mockup names/logos. Theme changes do not change destinations or graph geometry.

Mobile editor: long-press preserves selection/copy-paste; contextual Format/Insert remains keyboard and assistive-technology reachable; no persistent desktop toolbar; composing with IME and opening keyboard preserve unsaved text; footer does not obstruct text or native menus. These require actual browser/device testing, not images.

Decision layer: explicit action bypass; feature disabled; allowlist filtering; stale/revoked context; invalid option; abstention; timeout; no cloud escalation without permission; no note-write capability; no tutor interruption from note-save. Fixture expectations are not model benchmarks. Evaluate candidate performance separately, using reviewed labels and end-to-end costs.

Package: zero image/media binaries, zero embedded mockups/data images, retired reference status, local links and manifest checksums intact.
