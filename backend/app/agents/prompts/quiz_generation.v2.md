---
task: quiz_generation
version: 2
model_hint: gpt-4o-mini
temperature: 0.4
---

You are generating a CoLearni quiz card.

Rules:
- Generate the quiz only from the abstract mastery check labels provided below.
- Do not use private notes, uploaded files, source text, quoted material, or any source-derived details.
- Keep the card scoped to the current concept and Bloom target.
- Return only valid JSON.
- Produce 2 to 3 questions for `practice`; produce 2 to 4 questions for `level_up`.
- Use stable ids like `q1`, `q2`, `q3`.
- Choose the question type dynamically from `multiple_choice`, `short_answer`, `long_answer`, `code`, `multi_select`, `ordering`, and `cloze`.
- Choose `difficulty` dynamically from `light`, `standard`, and `challenge`.
- Prefer lower-friction `multiple_choice` for beginner recognition checks, supporting details, or early practice.
- Prefer `short_answer` for important recall, definitions, relationships, and misconception checks.
- Use `long_answer` sparingly for essential, high-importance checks that require explanation, application, or comparison.
- Use `code` only when the mastery label is genuinely about writing or completing code/pseudocode (e.g. implementing an algorithm, fixing a snippet). State the language or "pseudocode" in the prompt. Never use `code` for purely conceptual checks.
- Use `multi_select` when several items are simultaneously true. Provide 3 to 5 options with one OR MORE correct. Do not reveal which options are correct.
- Use `ordering` when the learner should sequence steps or ranked items. Put 3 to 6 items in `options` in a deliberately scrambled order, and state the target order in the prompt (e.g. "from top to bottom", "earliest to latest"). The learner will reorder them.
- Use `cloze` for targeted fill-in-the-blank recall. Write each blank as `____` (4 or more underscores) inside the prompt, with 1 to 3 blanks total. Each blank must have a short, unambiguous answer. Do not include `options`.
- You MAY use Markdown in `prompt`: inline code with backticks, fenced code blocks for snippets the learner must read, and LaTeX (`$...$` / `$$...$$`) for math. Keep prompts compact.
- Use `light` for supporting or introductory labels, `standard` for core labels, and `challenge` only for essential labels where a learner must integrate or apply ideas.
- Do not scare the learner away: keep prompts compact, use plain language, and avoid unnecessarily complex multi-step tasks.
- For `level_up`, include at least one `short_answer` or `long_answer` question unless every mastery label is purely recognition-level.
- For `multiple_choice`, include 3 or 4 plausible options. Do not include a visible answer key.
- Use the prior quiz context to avoid repeating exact prompts, especially prompts the learner already answered correctly or strongly. You may still assess the same mastery label with a different framing when it remains important.
- Prior quiz context is for variation only. Do not copy old questions verbatim, do not include old answers, and do not reveal grading feedback.

Concept:
{{ concept }}

Mastery check labels:
{{ mastery_check_labels }}

Bloom target: {{ bloom_target }}
Quiz type: {{ quiz_type }}

Prior quiz context:
{{ prior_quiz_context }}

Return this JSON shape exactly:

```json
{
  "questions": [
    {
      "id": "q1",
      "type": "multiple_choice",
      "prompt": "string",
      "mastery_label": "string",
      "difficulty": "light",
      "options": ["string", "string", "string"]
    }
  ]
}
```

For `short_answer`, `long_answer`, `code`, and `cloze`, omit `options`. For `multiple_choice`, `multi_select`, and `ordering`, include `options`.
