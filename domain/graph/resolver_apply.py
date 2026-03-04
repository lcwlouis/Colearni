"""Decision application helpers – merge aliases, descriptions, and merge-map method."""

from __future__ import annotations

from collections.abc import Sequence

from domain.graph.types import normalize_alias, truncate_text


def merge_map_method(method: str) -> str:
    """Normalize the method string for the merge-map row."""
    if method in {"exact", "lexical", "vector", "llm", "manual"}:
        return method
    return "exact"


def merge_aliases(existing_aliases: Sequence[str], alias_to_add: str) -> list[str]:
    """Add *alias_to_add* to *existing_aliases* if not already present."""
    candidate = alias_to_add.strip()
    if not candidate:
        return list(existing_aliases)
    normalized_existing = {normalize_alias(alias) for alias in existing_aliases}
    if normalize_alias(candidate) in normalized_existing:
        return list(existing_aliases)
    return [*existing_aliases, candidate]


def merge_description(*, existing: str, proposed: str | None, max_chars: int) -> str:
    """Pick the longer of existing/proposed description, bounded by max_chars."""
    bounded_existing = truncate_text(existing, max_chars)
    bounded_proposed = truncate_text(proposed, max_chars)
    if not bounded_existing:
        return bounded_proposed
    if not bounded_proposed:
        return bounded_existing
    return bounded_proposed if len(bounded_proposed) > len(bounded_existing) else bounded_existing
