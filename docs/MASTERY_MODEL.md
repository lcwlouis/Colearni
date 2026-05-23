# Mastery Model

## Purpose

Mastery tracking is a core CoLearni product primitive. It should help the learner see progress, decide what to study next, and unlock more direct explanations only after demonstrated understanding.

Mastery is goal-relative. A learner studying for an intro exam may only need Apply-level mastery. A learner building ML systems may need Analyze-level mastery.

## Statuses

```text
not_started
learning
needs_review
mastered
```

Status meanings:

- `not_started`: the learner has not begun the concept.
- `learning`: the learner has interacted with the concept but has not passed a mastery check.
- `needs_review`: the learner attempted a check and needs more practice or repair.
- `mastered`: the learner passed the current goal-relative mastery check.

## Bloom Levels

```text
remember
understand
apply
analyze
evaluate
create
```

The Trail target depth should set the expected Bloom level for each concept. Individual concepts may require lower or higher Bloom levels based on their role in the Trail.

## Recommended Tables

```sql
mastery_records
- id
- workspace_id
- concept_id
- status
- bloom_level
- score
- updated_at

quiz_attempts
- id
- concept_id
- quiz_type
- questions_json
- answers_json
- evaluator_feedback
- passed
- score
- created_at

quiz_drafts
- id
- concept_id
- quiz_type
- questions_json
- created_at
- updated_at
```

## Level-Up Flow

```text
Tutor detects readiness
-> generates level-up card from mastery_check_labels
-> user answers
-> evaluator grades answer
-> mastery status updates
-> graph UI updates
```

The tutor may invite the learner to level up, but it should not mark a concept mastered without an explicit grade/evaluation step.

## Level-Up Card Shape

A practical level-up card should usually include 2-4 questions chosen dynamically from the current concept's mastery labels.

- Use `multiple_choice` for lower-friction recognition checks or supporting details.
- Use `short_answer` for definitions, recall, relationships, and misconception checks.
- Use `long_answer` sparingly for essential explanation, application, or comparison checks.
- Each question also carries a difficulty label: `light`, `standard`, or `challenge`.

The quiz should be generated from abstract `mastery_check_labels`, not from private source-derived content that could later leak through public export.

## Grading Rules

- Passing updates mastery to `mastered`.
- Failing updates mastery to `needs_review`.
- Feedback must identify what was strong, what was missing, and what to try next.
- Retrying should be allowed.
- Practice quizzes can help learning without updating mastery.

## Quiz Draft Persistence

- Generated level-up and practice cards are stored server-side in `quiz_drafts`.
- Reopening the same concept and quiz type returns the existing draft until grading clears it.
- Clients can explicitly request a fresh card with `force_new`.

## State Machine and Transitions

Statuses follow this directed graph:

```text
not_started --[first chat turn]--> learning
learning    --[passed quiz]------> mastered
learning    --[failed quiz]------> needs_review
needs_review --[retry started]---> learning
needs_review --[passed quiz]-----> mastered
mastered    --[explicit reset]---> needs_review   (future feature, not MVP)
```

Rules:
- The first chat turn for a concept auto-transitions `not_started` -> `learning`. This is a side-effect of the tutor chat endpoint.
- Only a graded level-up quiz can transition to `mastered`. The tutor cannot mark mastery directly.
- Failed level-up quizzes always transition to or stay at `needs_review`.
- Practice quizzes never update mastery status. They are purely for learning.
- Retries are unlimited. There is no lockout.

## Scoring

The `score` field on `mastery_records` and `quiz_attempts` is a float in `[0.0, 1.0]`.

Pass threshold: `score >= 0.7`.

Score ranges:
- `0.0–0.4` — incorrect or substantially missing
- `0.5–0.69` — partial; set `needs_review`
- `0.7–0.89` — passing
- `0.9–1.0` — strong mastery

`multiple_choice` questions are graded deterministically as 0.0 or 1.0 per question.
`short_answer` and `long_answer` questions are graded by the `quiz_grader` prompt (see `docs/PROMPTS.md`). The grader returns a float per question, and the service averages all question scores into the overall score.

## Practice Mode

Practice quizzes use the same `quiz_generation` prompt as level-up quizzes. The difference is in how the grade result is handled:

| Behavior | Level-Up | Practice |
|---|---|---|
| Attempt stored | yes | yes |
| Mastery updated on pass | yes (`mastered`) | no |
| Mastery updated on fail | yes (`needs_review`) | no |
| Feedback returned | yes | yes |

Practice endpoints: `POST .../practice` and `POST .../practice/grade`.

## Product Requirement

Mastery gating should feel motivating, not punitive. The learner should experience it as a coach checking readiness, not as a wall blocking progress.

## Tutor Mode Gates

For the current MVP tutor flow:

- `socratic`, `repair`, `quiz_prompt`, and bounded `explore` do not require mastery.
- `direct` is mastery-gated to `mastered`.
- `free_explore` is mastery-gated to `mastered`.

If the learner requests a gated tutor mode before mastery, the tutor should preserve the learner's intent as much as possible while falling back to Socratic or bounded explore behaviour. It must not reveal internal gating policy in the visible response.
