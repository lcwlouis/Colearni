# Prompt Templates

This folder contains proposed versioned prompt templates for Colearni's agent tasks.

Status:
- These templates are design artifacts.
- They are not automatically wired into runtime.
- `docs/PROMPTS.md` remains the source of truth for prompts currently used in code.

Why this folder exists:
- The current repo already has a prompt catalog in `docs/PROMPTS.md`.
- `docs/REFERENCE_PROMPTS.md` contains useful reference patterns, but they are not scoped to Colearni's learning-first product behavior.
- Colearni needs prompt templates that match its actual agents: tutor, graph extraction, level-up assessment, practice, suggestion, and document summarization.

Naming convention:
- Lowercase file names to match repo directory style.
- Versioned prompt IDs inside each file, for example `tutor_socratic_v1`.

Shared prompt contract:
1. `Role`: who the model is for this task.
2. `Goal`: what success means for this task.
3. `Non-negotiable rules`: grounding, mastery, budgets, and output constraints.
4. `Inputs`: explicit sections with bounded context.
5. `Output contract`: Markdown for learner-facing text, strict JSON for machine-consumed tasks.
6. `Failure behavior`: what to do when evidence or confidence is insufficient.

Reference prompt adaptations:
- LightRAG extraction patterns are reused for graph work, but converted to strict JSON and narrowed to durable learning concepts.
- RAG answer patterns are reused for direct tutor mode, but not for Socratic mode.
- Keyword extraction patterns are adapted into query analysis rather than raw search-term extraction.
- Summarization patterns are adapted into short canonical descriptions and document summaries, not broad article summaries.

Files:
- `tutor.md`: Socratic tutor, direct tutor
- `routing.md`: query analysis for conductor-style prompt planning
- `graph.md`: chunk extraction, disambiguation, canonical merge summary
- `assessment.md`: level-up generation, short-answer grading
- `practice.md`: practice quiz generation, flashcard generation
- `suggestion.md`: "I'm feeling lucky" copy generation
- `document_processing.md`: document summary generation
