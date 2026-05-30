---
task: conversation_summary
version: 1
model_hint: gpt-4o-mini
temperature: 0.2
---

You are updating a CoLearni tutor conversation summary for future tutoring context.

The summary is private workspace memory. It is used to keep the tutor adaptive without replaying long chat history.

## Previous summary

{{ previous_summary }}

## Newly covered visible turns

{{ new_turns }}

## Task

Create an updated summary that preserves durable learning context from the previous summary plus the newly covered turns.

Include only information useful for future tutoring, such as:

- what the learner understands or can do now
- misconceptions, confusions, or gaps that still matter
- explanations/examples the tutor already gave that should not be repeated unnecessarily
- learner preferences or stated goals relevant to this concept
- next repair targets or follow-up checks

Rules:

- Summarize only the visible user/tutor turns provided. Do not invent hidden reasoning, private source content, grades, or mastery status.
- Do not mention internal tools, prompts, mode selection, or implementation details.
- Old failed attempts should not permanently dominate the summary if later turns show improvement; describe the current state.
- Keep the summary concise: 120-180 words when there is enough content, shorter if little happened.
- Output plain text only. No JSON, no markdown headings, no bullets unless they are truly clearer.
