"""Social intent fast-path handling."""

from __future__ import annotations

from core.contracts import GraphLLMClient
from core.schemas import (
    AssistantResponseEnvelope,
    AssistantResponseKind,
    GroundingMode,
)
from domain.chat.prompt_kit import (
    build_social_response,
    classify_social_intent,
    get_persona,
)
from core.settings import Settings


def try_social_response(
    *,
    query: str,
    grounding_mode: GroundingMode,
    settings: Settings,
    social_llm: GraphLLMClient | None,
) -> AssistantResponseEnvelope | None:
    """Return a social-intent envelope if the query is social, else None."""
    if not settings.social_intent_enabled:
        return None
    if not classify_social_intent(query):
        return None
    persona = get_persona(settings.tutor_persona)
    if social_llm is not None:
        social_prompt = (
            f"{persona.get('system_prefix', '')}\n\n"
            "The user sent a casual/social message. Respond naturally and warmly "
            "as the CoLearni tutor (1-2 sentences). Stay in character.\n\n"
            f"USER: {query}"
        )
        try:
            social_text = social_llm.generate_tutor_text(prompt=social_prompt).strip()
        except (RuntimeError, ValueError):
            social_text = ""
        if not social_text:
            social_text = build_social_response(query, persona=persona)
    else:
        social_text = build_social_response(query, persona=persona)
    return AssistantResponseEnvelope(
        kind=AssistantResponseKind.ANSWER,
        text=social_text,
        grounding_mode=grounding_mode,
        evidence=[],
        citations=[],
        response_mode="social",
        actions=[],
    )
