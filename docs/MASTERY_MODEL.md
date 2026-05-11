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
- user_answer
- evaluator_feedback
- passed
- created_at
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

A practical level-up card should usually include:

1. Explain the concept in your own words.
2. Apply it to a small example.
3. Compare it with a related concept or address a common misconception.

The quiz should be generated from abstract `mastery_check_labels`, not from private source-derived content that could later leak through public export.

## Grading Rules

- Passing updates mastery to `mastered`.
- Failing updates mastery to `needs_review`.
- Feedback must identify what was strong, what was missing, and what to try next.
- Retrying should be allowed.
- Practice quizzes can help learning without updating mastery.

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

MCQ questions (future): deterministic 0.0 or 1.0 per question, averaged.
Short-answer questions: graded by the `quiz_grader` prompt (see `docs/PROMPTS.md`). The LLM returns a float per question. The service averages them to compute overall score.

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
