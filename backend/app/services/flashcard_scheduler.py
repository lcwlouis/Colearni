"""Leitner scheduler for flashcards (v1).

Pure, deterministic, unit-testable functions. Scheduling v1 is LEITNER: a card
lives in one of ``MAX_BOX`` boxes with geometric review intervals. A recall-first
swipe drives promotion/demotion:

- recalled (yes)  => box + 1 (capped at ``MAX_BOX``)
- not recalled (no) => box reset to 1, ``lapses`` incremented

``reps`` increments on every review. ``due`` is computed as
``last_reviewed + interval_days``. The schema also stores ``last_reviewed`` /
``interval_days`` / ``lapses`` so a future FSRS scheduler can drop in without a
migration; v1 logic is intentionally Leitner only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

# Geometric intervals (days) for boxes 1..5. Index 0 == box 1.
LEITNER_INTERVALS: tuple[int, ...] = (1, 3, 7, 16, 35)
MIN_BOX = 1
MAX_BOX = len(LEITNER_INTERVALS)


def interval_for_box(box: int) -> int:
    """Geometric interval in days for a (1-indexed) Leitner box, clamped to range."""
    clamped = max(MIN_BOX, min(box, MAX_BOX))
    return LEITNER_INTERVALS[clamped - 1]


@dataclass(frozen=True)
class ScheduleState:
    box: int
    interval_days: int
    last_reviewed: datetime
    due: datetime
    reps: int
    lapses: int


def review(
    *,
    box: int,
    reps: int,
    lapses: int,
    recalled: bool,
    now: datetime,
) -> ScheduleState:
    """Apply one recall-first swipe and return the new scheduling state.

    Pure: takes the current counters + ``now`` and returns the next state. The
    caller persists the fields onto the card row.
    """
    reps = reps + 1
    if recalled:
        box = min(box + 1, MAX_BOX)
    else:
        box = MIN_BOX
        lapses = lapses + 1
    interval_days = interval_for_box(box)
    due = now + timedelta(days=interval_days)
    return ScheduleState(
        box=box,
        interval_days=interval_days,
        last_reviewed=now,
        due=due,
        reps=reps,
        lapses=lapses,
    )
