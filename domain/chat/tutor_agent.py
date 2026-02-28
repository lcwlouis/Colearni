"""Tutor response style policy and generation helpers."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Literal

from core.contracts import GraphLLMClient
from core.prompting import PromptRegistry
from core.schemas import EvidenceItem

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
    llm_client: GraphLLMClient | None,
) -> str:
    style = resolve_tutor_style(mastery_status=mastery_status)
    prompt = build_tutor_prompt(query=query, evidence=evidence, style=style)
    if llm_client is not None:
        try:
            text = llm_client.generate_tutor_text(prompt=prompt).strip()
        except (RuntimeError, ValueError):
            text = ""
        if text:
            return text
    return _fallback_text(query=query, evidence=evidence, style=style)


def build_tutor_prompt(*, query: str, evidence: Sequence[EvidenceItem], style: TutorStyle) -> str:
    """Build a tutor prompt using file-based assets with inline fallback."""
    lines = [
        f"- e{index}: {_truncate(' '.join(item.content.split()), limit=240)}"
        for index, item in enumerate(evidence[:3], start=1)
    ]
    evidence_block = "\n".join(lines) if lines else "- (none)"

    asset_id = _TUTOR_ASSET_IDS.get(style, "tutor_socratic_v1")
    try:
        return _registry.render(asset_id, {
            "strict_grounded_mode": "true",
            "mastery_status": "learned" if style == "direct" else "locked",
            "document_summaries": "(none)",
            "assessment_context": "(none)",
            "flashcard_progress": "(none)",
            "history_summary": "(none)",
            "evidence_block": evidence_block,
            "query": query,
        })
    except Exception:
        log.debug("asset render failed for %s, using inline fallback", asset_id)
        return _build_tutor_prompt_inline(
            query=query, evidence_block=evidence_block, style=style
        )


def _build_tutor_prompt_inline(
    *, query: str, evidence_block: str, style: TutorStyle
) -> str:
    """Inline fallback for tutor prompt assembly (pre-P2 behavior)."""
    rules = (
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
    return f"{rules}\n\nUSER_QUESTION: {query}\n\nEVIDENCE:\n{evidence_block}"


def _fallback_text(*, query: str, evidence: Sequence[EvidenceItem], style: TutorStyle) -> str:
    if style == "direct":
        if not evidence:
            return f"I need source-linked material before I can directly explain: {query}"
        lead = _truncate(" ".join(evidence[0].content.split()), limit=280)
        return f'From your notes, here is a direct explanation: "{lead}"'
    if not evidence:
        return "What key idea do you already know? Share one step and I will guide next."
    lead = _truncate(" ".join(evidence[0].content.split()), limit=220)
    return f'What do you think this passage implies? Hint: start from "{lead}".'


def _truncate(value: str, *, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 3] + "..."


__all__ = ["build_tutor_prompt", "build_tutor_response_text", "resolve_tutor_style"]
