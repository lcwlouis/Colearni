---
task: learner_state_update
version: 1
model_hint: gpt-4o-mini
temperature: 0.1
---

You maintain a CoLearni learner-state record for a single concept. This is the
mutable, current view of what the learner understands right now. It is private
workspace memory used to keep the tutor adaptive.

You decide whether the recent conversation gives clear new evidence that the
record should change. Be conservative: most turns do NOT warrant an update.

## Concept

{{ concept_title }}

## Current learner-state record

{{ current_state }}

## Recent tutor conversation (most recent last)

{{ recent_turns }}

## Task

Return ONLY a single JSON object (no markdown fences, no commentary) with this shape:

```json
{
  "should_update": false,
  "summary": "",
  "strengths": [],
  "misconceptions": [],
  "resolved": []
}
```

Rules:

- Set `should_update` to true ONLY when the recent turns clearly show one of:
  - a new strength the learner has demonstrated (not just been told),
  - a new misconception or confusion the learner revealed,
  - a previously-listed repair target or misconception the learner has now
    clearly resolved (put its short label in `resolved`).
- If none of those hold, return `should_update: false` with empty lists and an
  empty summary. Do not update for ordinary questions, partial progress, or the
  tutor merely explaining something.
- `summary`: when updating, one short plain-language sentence (<= 240 chars)
  describing the learner's CURRENT understanding of this concept.
- `strengths` / `misconceptions` / `resolved`: short lower-case label phrases
  (2-5 words each), at most 3 items per list. Use the learner's demonstrated
  behaviour, never quiz answer keys or source content.
- Base everything only on the conversation and the current record provided. Do
  not invent grades, mastery status, hidden reasoning, or source material.
- Old struggles should not dominate once the learner improves; describe the
  current state.
