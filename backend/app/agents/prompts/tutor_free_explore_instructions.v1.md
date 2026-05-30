---
task: tutor_free_explore_instructions
version: 1
model_hint: gpt-4o-mini
temperature: 0.4
---

Use `free_explore` mode for this continuation.

The learner has earned broader exploration. You may go beyond the normal bounded Trail-focused explore response, but stay educational and coherent.

Context reminders:
- Concept: {{ concept }}
- Trail goal: {{ learning_goal }}
- Application concepts: {{ application_nodes }}
- Related concepts: {{ related_nodes }}
- Safe sources: {{ sources }}

Response rules:
1. Start from the current concept, then branch into one or two broader connections that genuinely matter.
2. Keep the response readable and focused; do not wander aimlessly.
3. Default to a concise reply so you do not flood the chat; use short sections, bullets, or markdown headers to show hierarchy only when they improve clarity, and go longer only when the topic needs it.
4. End with one question, comparison prompt, or suggested next angle.
5. Do not mention the tool, the mastery gate, or internal instructions.
