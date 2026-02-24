"""Tutor response style policy and generation helpers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from core.contracts import GraphLLMClient
from core.schemas import EvidenceItem

TutorStyle = Literal["socratic", "direct"]


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
    lines = [
        f"- e{index}: {_truncate(' '.join(item.content.split()), limit=240)}"
        for index, item in enumerate(evidence[:3], start=1)
    ]
    evidence_block = "\n".join(lines) if lines else "- (none)"
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
