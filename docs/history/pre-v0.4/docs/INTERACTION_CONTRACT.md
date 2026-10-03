# Desk interaction and ownership contract

## Core objects

| Object | Meaning |
|---|---|
| Desk | Scoped learning workspace; contains material, goals, work, and history. |
| Goal | An editable, plain-language capability the learner wants. |
| Card | Addressable, versioned object with a stable shell and a typed body. |
| Source reference | Source/revision + passage/figure/equation location; origin is distinguishable from generated explanation. |
| Learner note | Learner-controlled content with explicit tutor-read sharing. |
| Tutor contribution | Agent-authored material, even when accepted or saved by the learner. |
| Semantic target | An address into a specific revision: block, step, code range, cell, or plotted object. |
| Change set | One meaningful action grouped across affected objects, with before/after revisions. |
| Learning evidence | A bounded observation with activity, assistance, time, and provenance—not automatically mastery. |

## Card shell

Own title, author/origin labels, sources, capability controls, loading/error/fallback states, and consistent focus behaviour centrally. Bodies do not supply arbitrary HTML, CSS classes, event handlers, script URLs, or executable source as ordinary content. Structured data is runtime validated before rendering; TypeScript annotations alone do not enforce runtime validation. [R10]

Bodies expose stable targets, events, and serialisable state. A worked example can have step targets; a plot can have named series/objects; code targets specify the code revision. If a target is stale, do not highlight the nearest convenient text. Report unavailable or re-resolve against the current revision with an explicit result.

## Attention and layout

The current learner activity remains stable while they read or type. Place bounded tutor additions into a predictable supporting area. Do not automatically pan, resize, switch tabs, reorder cards, or move keyboard focus. Coalesce duplicate suggestions. Allow dismissal and pausing of interventions.

One primary activity with optional support is the prototype default, not a maximum workspace size. Do not recreate verbose chat as dozens of cards. Each render cycle must handle empty, loading, error, unsupported, and reduced-motion states.

## Author versus accepting actor

The learner alone edits their note body and controls its sharing setting. The tutor may propose an adjacent contribution. Saving or copying that contribution is an explicit learner action and retains its generated origin. Mixed-origin note blocks should preserve provenance rather than labelling the whole document as independently authored.

Source excerpts retain attribution and are not silently rewritten. Source material, notes, and plugin descriptions are task data, not higher-priority instructions; this separation is one part of a broader prompt-injection defence, not a guarantee against it. [R9]

## Permission boundary

| Action | Learner | Tutor |
|---|---|---|
| Edit learner note / sharing flag | Yes | Never |
| Read shared current-desk note | Yes | Through the scoped context service |
| Read private note | Yes | No |
| Add small support card | Yes | Yes, within host policy and budget |
| Replace existing work or restructure desk | Yes | Proposal requiring acceptance |
| Suggest concept link | Yes | Yes, labelled as inferred until confirmed |
| Install unknown executable plugin | Explicit later workflow | No autonomous installation |

Production rules are enforced by a trusted service. An actor string or a frontend disabled button is not authentication. Tests should model maliciously submitted commands, not only hidden buttons.

## Revisions, undo, and checkpoints

Store immutable revisions of affected objects, and record an atomic change set with before/after pointers. The current-state projection can be stored directly; a full event-sourcing framework is unnecessary for the prototype.

An agent addition followed by learner note edits must be reversible without changing those notes. Undo creates a new compensating change rather than deleting history. If the target has later learner edits or dependent work, do not overwrite or delete it: show a conflict and offer a preserved-copy or user-reviewed resolution. Checkpoints capture the wider workspace for recovery, distinct from normal action undo.

Use expected revisions and idempotency keys. A retried command must not add duplicate cards. A multi-object operation either succeeds entirely or leaves state unchanged. Do not hold a database transaction open during a model request. A future trusted service can generate a proposal first, then check permissions/revisions and apply it in a short transaction.

Historical sharing permissions must never override current permission checks. History retention and user deletion need an explicit policy before production; indefinite snapshots are not a substitute for deletion support.

## Accessibility and resilience

Use semantic HTML, named controls, visible focus, keyboard equivalents, readable contrast, and a linear small-screen path. Ownership is conveyed with text, not colour alone. Animations have pause/reset/step where relevant and honour reduced-motion preferences. Error boundaries preserve the rest of the desk when a renderer fails. Automated accessibility tests supplement manual keyboard/screen-reader checks; they do not certify complete accessibility. [R7]
