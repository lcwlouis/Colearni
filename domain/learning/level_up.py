"""Level-up quiz module — backward-compatible wrapper over shared quiz core.

The actual create/submit logic now lives in :mod:`domain.learning.quiz_flow`.
This module re-exports the shared functions and error classes under their
original ``LevelUp``-prefixed names so existing callers keep working.
"""

from __future__ import annotations

from domain.learning.quiz_flow import (  # noqa: F401
    QuizGradingError as LevelUpQuizGradingError,
)
from domain.learning.quiz_flow import (
    QuizNotFoundError as LevelUpQuizNotFoundError,
)
from domain.learning.quiz_flow import (
    QuizUnavailableError as LevelUpQuizUnavailableError,
)
from domain.learning.quiz_flow import (
    QuizValidationError as LevelUpQuizValidationError,
)
from domain.learning.quiz_flow import (
    create_quiz as create_level_up_quiz,
)
from domain.learning.quiz_flow import (
    submit_quiz as submit_level_up_quiz,
)
from domain.learning.quiz_persistence import (  # noqa: F401
    get_latest_quiz_summary_for_concept,
)

MIN_ITEMS = 5
MAX_ITEMS = 12
RETRY_HINT = "create a new level-up quiz to retry"


__all__ = [
    "LevelUpQuizGradingError",
    "LevelUpQuizNotFoundError",
    "LevelUpQuizUnavailableError",
    "LevelUpQuizValidationError",
    "create_level_up_quiz",
    "get_latest_quiz_summary_for_concept",
    "submit_level_up_quiz",
]
