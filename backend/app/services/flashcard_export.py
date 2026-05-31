"""Flashcard export (export-only formats; NOT the source of truth).

Two formats:

- ``export_deck_csv``: Anki-compatible CSV. Emits Anki import directives
  (``#separator``/``#columns``) followed by one row per card so the file imports
  cleanly into Anki without manual column mapping.
- ``export_deck_json``: a round-trippable JSON document with the full deck +
  card fields (including scheduling state).

The canonical store stays relational; these are derived views only.
"""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.schemas.flashcard import FlashcardDeckRead

# Anki import column order. ``front`` and ``back`` map to the first two note
# fields; the rest are extra fields Anki will store on the note type.
CSV_COLUMNS = ("front", "back", "hint", "source_ref", "card_type")


def export_deck_csv(deck: FlashcardDeckRead) -> str:
    """Render the deck as Anki-importable CSV text."""
    buffer = io.StringIO()
    buffer.write("#separator:Comma\n")
    buffer.write("#html:false\n")
    buffer.write(f"#columns:{','.join(CSV_COLUMNS)}\n")
    writer = csv.writer(buffer, lineterminator="\n")
    for card in deck.cards:
        writer.writerow(
            [
                card.front,
                card.back,
                card.hint or "",
                card.source_ref or "",
                card.card_type,
            ]
        )
    return buffer.getvalue()


def export_deck_json(deck: FlashcardDeckRead) -> dict:
    """Render the deck as a round-trippable JSON-serialisable dict."""
    return {
        "deck": {
            "id": str(deck.id),
            "workspace_id": str(deck.workspace_id),
            "trail_id": str(deck.trail_id),
            "concept_id": str(deck.concept_id),
            "title": deck.title,
        },
        "cards": [
            {
                "id": str(card.id),
                "front": card.front,
                "back": card.back,
                "hint": card.hint,
                "source_ref": card.source_ref,
                "card_type": card.card_type,
                "box": card.box,
                "interval_days": card.interval_days,
                "last_reviewed": card.last_reviewed.isoformat() if card.last_reviewed else None,
                "due": card.due.isoformat() if card.due else None,
                "reps": card.reps,
                "lapses": card.lapses,
            }
            for card in deck.cards
        ],
    }
