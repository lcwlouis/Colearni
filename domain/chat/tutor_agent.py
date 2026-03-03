"""Tutor response style policy and generation helpers."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Literal

from core.contracts import GraphLLMClient
from core.prompting import PromptRegistry
from core.schemas import EvidenceItem, GroundingMode

log = logging.getLogger("domain.chat.tutor_agent")

TutorStyle = Literal["socratic", "direct"]

_registry = PromptRegistry()

_TUTOR_ASSET_IDS: dict[str, str] = {
    "socratic": "tutor_socratic_v1",
    "direct": "tutor_direct_v1",
}


def resolve_tutor_style(*, mastery_status: str | None) -> TutorStyle:
    return "direct" if mastery_status == "learned" else "socratic"


def build_tutor_response_text(
    *,
    query: str,
    evidence: Sequence[EvidenceItem],
    mastery_status: str | None,
    grounding_mode: GroundingMode,
    llm_client: GraphLLMClient | None,
) -> str:
    style = resolve_tutor_style(mastery_status=mastery_status)
    system_prompt, user_prompt = _build_tutor_prompt_parts(
        query=query,
        evidence=evidence,
        style=style,
        grounding_mode=grounding_mode,
    )
    if llm_client is not None:
        try:
            text = llm_client.generate_tutor_text(
                prompt=user_prompt,
                system_prompt=system_prompt,
            ).strip()
        except (RuntimeError, ValueError):
            text = ""
        if text:
            return text
    return _fallback_text(query=query, evidence=evidence, style=style)


def build_tutor_prompt(
    *,
    query: str,
    evidence: Sequence[EvidenceItem],
    style: TutorStyle,
    grounding_mode: GroundingMode,
) -> str:
    """Build a tutor prompt using file-based assets with inline fallback."""
    system, user = _build_tutor_prompt_parts(
        query=query, evidence=evidence, style=style, grounding_mode=grounding_mode,
    )
    return f"{system}\n\n{user}"


def _build_tutor_prompt_parts(
    *,
    query: str,
    evidence: Sequence[EvidenceItem],
    style: TutorStyle,
    grounding_mode: GroundingMode,
) -> tuple[str, str]:
    """Build tutor prompt separated into (system, user) parts."""
    lines = [
        f"- e{index}: {' '.join(item.content.split())}"
        for index, item in enumerate(evidence[:3], start=1)
    ]
    evidence_block = "\n".join(lines) if lines else "- (none)"

    asset_id = _TUTOR_ASSET_IDS.get(style, "tutor_socratic_v1")
    strict_grounded_mode = "true" if grounding_mode == GroundingMode.STRICT else "false"
    try:
        rendered = _registry.render(asset_id, {
            "strict_grounded_mode": strict_grounded_mode,
            "mastery_status": "learned" if style == "direct" else "locked",
            "document_summaries": "(none)",
            "assessment_context": "(none)",
            "flashcard_progress": "(none)",
            "learner_profile_summary": "(none)",
            "history_summary": "(none)",
            "evidence_block": evidence_block,
            "query": query,
        })
        parts = rendered.split("\n---Inputs---\n", maxsplit=1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
        return rendered, ""
    except Exception:
        log.debug("asset render failed for %s, using inline fallback", asset_id)
        return _build_tutor_prompt_inline_parts(
            query=query, evidence_block=evidence_block, style=style,
        )


def _build_tutor_prompt_inline(
    *, query: str, evidence_block: str, style: TutorStyle
) -> str:
    """Inline fallback for tutor prompt assembly (pre-P2 behavior)."""
    system, user = _build_tutor_prompt_inline_parts(
        query=query, evidence_block=evidence_block, style=style,
    )
    return f"{system}\n\n{user}"


def _build_tutor_prompt_inline_parts(
    *, query: str, evidence_block: str, style: TutorStyle
) -> tuple[str, str]:
    """Inline fallback returning (system, user) parts."""
    system = (
        "STYLE: socratic\n"
        "Do not provide the final answer directly.\n"
        "Ask one guiding question first, then give a brief hint and a next step."
        if style == "socratic"
        else (
            "STYLE: direct\n"
            "Provide a direct summary or explanation.\n"
            "Be concise and grounded in the cited evidence."
        )
    )
    user = f"USER_QUESTION: {query}\n\nEVIDENCE:\n{evidence_block}"
    return system, user


def _fallback_text(*, query: str, evidence: Sequence[EvidenceItem], style: TutorStyle) -> str:
    if style == "direct":
        if not evidence:
            return f"I need source-linked material before I can directly explain: {query}"
        lead = " ".join(evidence[0].content.split())
        return f'From your notes, here is a direct explanation: "{lead}"'
    if not evidence:
        return "What key idea do you already know? Share one step and I will guide next."
    lead = " ".join(evidence[0].content.split())
    return f'What do you think this passage implies? Hint: start from "{lead}".'


__all__ = ["build_tutor_prompt", "build_tutor_response_text", "resolve_tutor_style"]
