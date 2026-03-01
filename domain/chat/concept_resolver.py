"""Concept inference and switch-suggestion policy for tutor chat."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

SwitchDecision = Literal["accept", "reject"]

# Below this confidence, weak mismatches are suppressed and the current concept
# is preserved.  Only strong evidence (exact name match, multi-token overlap,
# or explicit user language) triggers a switch suggestion.
_SWITCH_CONFIDENCE_THRESHOLD = 0.75


@dataclass(frozen=True)
class ConceptInfo:
    concept_id: int
    canonical_name: str


@dataclass(frozen=True)
class ConceptSwitchSuggestion:
    from_concept_id: int
    from_concept_name: str
    to_concept_id: int
    to_concept_name: str
    reason: str


@dataclass(frozen=True)
class ConceptResolution:
    resolved_concept: ConceptInfo | None
    confidence: float
    requires_clarification: bool
    clarification_prompt: str | None
    switch_suggestion: ConceptSwitchSuggestion | None


def resolve_concept_for_turn(
    session: Session,
    *,
    workspace_id: int,
    query: str,
    history_text: str,
    current_concept_id: int | None,
    suggested_concept_id: int | None,
    switch_decision: SwitchDecision | None,
) -> ConceptResolution:
    if not hasattr(session, "execute"):
        return _fallback_resolution(
            switch_decision=switch_decision,
            current_concept_id=current_concept_id,
            suggested_concept_id=suggested_concept_id,
        )

    current = _concept_by_id(
        session,
        workspace_id=workspace_id,
        concept_id=current_concept_id,
    )
    suggested = _concept_by_id(
        session,
        workspace_id=workspace_id,
        concept_id=suggested_concept_id,
    )

    if switch_decision == "accept" and suggested is not None:
        return ConceptResolution(
            resolved_concept=suggested,
            confidence=0.95,
            requires_clarification=False,
            clarification_prompt=None,
            switch_suggestion=None,
        )

    if switch_decision == "reject":
        # Explicit rejection means we must clarify before changing concept context.
        baseline = current or suggested
        return ConceptResolution(
            resolved_concept=baseline,
            confidence=0.35,
            requires_clarification=True,
            clarification_prompt=(
                "I see a possible concept mismatch. Which concept should we focus on for this "
                "question? You can pick a node in the graph panel or name the concept."
            ),
            switch_suggestion=None,
        )

    inferred, score = _infer_concept(
        session,
        workspace_id=workspace_id,
        query=query,
        history_text=history_text,
        suggested_concept=suggested,
    )
    resolved = inferred or suggested or current
    confidence = _to_confidence(score=score, used_suggestion=resolved == suggested)

    # Stay on the current concept when the switch signal is weak.
    if (
        current is not None
        and resolved is not None
        and current.concept_id != resolved.concept_id
        and confidence < _SWITCH_CONFIDENCE_THRESHOLD
    ):
        resolved = current

    switch_suggestion: ConceptSwitchSuggestion | None = None
    if (
        current is not None
        and resolved is not None
        and current.concept_id != resolved.concept_id
        and confidence >= _SWITCH_CONFIDENCE_THRESHOLD
    ):
        switch_suggestion = ConceptSwitchSuggestion(
            from_concept_id=current.concept_id,
            from_concept_name=current.canonical_name,
            to_concept_id=resolved.concept_id,
            to_concept_name=resolved.canonical_name,
            reason="latest message appears closer to another concept",
        )

    return ConceptResolution(
        resolved_concept=resolved,
        confidence=confidence,
        requires_clarification=False,
        clarification_prompt=None,
        switch_suggestion=switch_suggestion,
    )


def _fallback_resolution(
    *,
    switch_decision: SwitchDecision | None,
    current_concept_id: int | None,
    suggested_concept_id: int | None,
) -> ConceptResolution:
    if switch_decision == "reject":
        return ConceptResolution(
            resolved_concept=None,
            confidence=0.35,
            requires_clarification=True,
            clarification_prompt=(
                "I see a possible concept mismatch. Which concept should we focus on for this "
                "question? You can pick a node in the graph panel or name the concept."
            ),
            switch_suggestion=None,
        )

    if switch_decision == "accept" and suggested_concept_id is not None:
        return ConceptResolution(
            resolved_concept=ConceptInfo(
                concept_id=suggested_concept_id,
                canonical_name=f"Concept {suggested_concept_id}",
            ),
            confidence=0.8,
            requires_clarification=False,
            clarification_prompt=None,
            switch_suggestion=None,
        )

    if current_concept_id is not None:
        return ConceptResolution(
            resolved_concept=ConceptInfo(
                concept_id=current_concept_id,
                canonical_name=f"Concept {current_concept_id}",
            ),
            confidence=0.5,
            requires_clarification=False,
            clarification_prompt=None,
            switch_suggestion=None,
        )

    return ConceptResolution(
        resolved_concept=None,
        confidence=0.4,
        requires_clarification=False,
        clarification_prompt=None,
        switch_suggestion=None,
    )


def _infer_concept(
    session: Session,
    *,
    workspace_id: int,
    query: str,
    history_text: str,
    suggested_concept: ConceptInfo | None,
) -> tuple[ConceptInfo | None, float]:
    rows = (
        session.execute(
            text(
                """
                SELECT id AS concept_id, canonical_name, aliases
                FROM concepts_canon
                WHERE workspace_id = :workspace_id
                  AND is_active = TRUE
                ORDER BY updated_at DESC, id DESC
                LIMIT 200
                """
            ),
            {"workspace_id": workspace_id},
        )
        .mappings()
        .all()
    )
    if not rows:
        return suggested_concept, 0.0

    query_text = " ".join(query.lower().split())
    history_only = history_text.lower().replace(query.lower(), " ")
    history_text_norm = " ".join(history_only.split())
    query_tokens = set(_tokens(query_text))
    history_tokens = set(_tokens(history_text_norm))
    best: ConceptInfo | None = None
    best_score = 0.0

    for row in rows:
        names = [str(row["canonical_name"])] + [str(alias) for alias in (row["aliases"] or [])]
        score = 0.0
        for name in names:
            norm = " ".join(name.lower().split())
            if not norm:
                continue
            name_tokens = set(_tokens(norm))
            query_match = _match_strength(
                norm,
                name_tokens=name_tokens,
                text=query_text,
                tokens=query_tokens,
                exact_score=6.0,
                full_token_score=4.0,
                partial_score=2.0,
            )
            history_match = _match_strength(
                norm,
                name_tokens=name_tokens,
                text=history_text_norm,
                tokens=history_tokens,
                exact_score=1.5,
                full_token_score=1.0,
                partial_score=0.4,
            )
            score = max(score, query_match + history_match)

        concept = ConceptInfo(
            concept_id=int(row["concept_id"]),
            canonical_name=str(row["canonical_name"]),
        )
        if suggested_concept is not None and concept.concept_id == suggested_concept.concept_id:
            score += 0.8

        if score > best_score:
            best_score = score
            best = concept

    if best is None:
        return suggested_concept, 0.0
    return best, best_score


def _concept_by_id(
    session: Session,
    *,
    workspace_id: int,
    concept_id: int | None,
) -> ConceptInfo | None:
    if concept_id is None:
        return None
    row = (
        session.execute(
            text(
                """
                SELECT id AS concept_id, canonical_name
                FROM concepts_canon
                WHERE workspace_id = :workspace_id
                  AND id = :concept_id
                  AND is_active = TRUE
                LIMIT 1
                """
            ),
            {"workspace_id": workspace_id, "concept_id": concept_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return ConceptInfo(
        concept_id=int(row["concept_id"]),
        canonical_name=str(row["canonical_name"]),
    )


def _tokens(value: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", value.lower()) if token]


def _match_strength(
    normalized_name: str,
    *,
    name_tokens: set[str],
    text: str,
    tokens: set[str],
    exact_score: float,
    full_token_score: float,
    partial_score: float,
) -> float:
    if not text or not normalized_name:
        return 0.0
    if normalized_name in text:
        return exact_score
    if name_tokens and name_tokens.issubset(tokens):
        return full_token_score
    if name_tokens and any(token in tokens for token in name_tokens):
        return partial_score
    return 0.0


def _to_confidence(*, score: float, used_suggestion: bool) -> float:
    if used_suggestion and score <= 0:
        return 0.6
    if score >= 4:
        return 0.95
    if score >= 3:
        return 0.8
    if score > 0:
        return 0.65
    return 0.4


__all__ = [
    "ConceptInfo",
    "ConceptResolution",
    "ConceptSwitchSuggestion",
    "SwitchDecision",
    "_SWITCH_CONFIDENCE_THRESHOLD",
    "resolve_concept_for_turn",
]
