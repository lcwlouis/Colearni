# Archived Prompts

Superseded prompt versions kept for provenance only. The `PromptRegistry` globs the
prompt directory **non-recursively** (`{task}.v*.md`), so files in this subdirectory
are intentionally invisible to `load()`/`render()` and never reach the model.

| File | Replaced by |
|---|---|
| `tutor_mode_classifier.v1.md`, `tutor_mode_classifier.v2.md` | `tutor_turn_classifier.v1.md` (unified enforced-JSON classifier returning `{mode, blocks_active_quiz_answer}`) |
| `tutor_socratic.v1.md` | `tutor_socratic.v2.md` |
| `tutor_repair.v1.md` | `tutor_repair.v2.md` |
| `tutor_explore.v1.md` | `tutor_explore.v2.md` |
| `tutor_direct.v1.md` | `tutor_direct.v2.md` |
| `concept_primer.v1.md` | `concept_primer.v2.md` (`PRIMER_VERSION = 2`) |

Note: `quiz_generation.v1.md` is intentionally NOT archived — it is still loaded by a
prompt-registry regression test (`test_prompt_registry_loads_quiz_prompts_from_repo`).
