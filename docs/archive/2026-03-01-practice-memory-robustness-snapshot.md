# Practice Memory + Robustness Snapshot (2026-03-01)

Context captured before executing the new refactor slices:

- User-reported issues:
  1. Practice quiz and flashcards are not retrievable/reusable enough in product UX.
  2. Flashcard generation should account for prior generated cards and user ratings.
  3. Practice/quiz generation robustness failed with a 500.
  4. Level-up quizzes should remain retrievable and reusable as practice, and remain in tutor context.
- Production/dev trace indicates failure path:
  - `POST /workspaces/{id}/practice/quizzes` returned 500
  - Root exception: `QuizValidationError: question_count must be between 3 and 6`
  - Trigger occurred in fallback generation after overfetch exceeded bounds.

Repository status notes at snapshot time:

- Stateful flashcard persistence exists (`practice_generation_runs`, `practice_flashcard_bank`, `practice_flashcard_progress`).
- Novelty fingerprint history exists (`practice_item_history`) for flashcards and quizzes.
- Quiz persistence exists (`quizzes`, `quiz_items`, `quiz_attempts`) for both `level_up` and `practice` quiz types.
- Retrieval/reuse API surfaces for prior practice runs and prior quizzes are limited.
