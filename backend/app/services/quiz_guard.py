"""Semantic guard that blocks learners from extracting active quiz answers.

Exact-prompt matching catches verbatim copies, but learners frequently reword a
quiz question. This guard runs a small, structured LLM classification that decides
whether the learner's latest message is essentially one of the active quiz
questions (a paraphrase or near-duplicate). It runs backend-only and returns a
boolean; the active quiz prompts are never streamed or surfaced as reasoning.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from backend.app.agents.prompts import prompt_registry

if TYPE_CHECKING:
    from backend.app.agents.llm_client import LLMClient
    from backend.app.agents.prompts.registry import PromptRegistry


async def detect_quiz_answer_seeking(
    client: LLMClient,
    *,
    learner_message: str,
    quiz_prompts: list[str],
    registry: PromptRegistry = prompt_registry,
) -> bool:
    """Return True when the learner is asking an active quiz question in disguise.

    Fails open (returns False) so an unavailable or malformed model response never
    blocks a legitimate question; exact-match still covers verbatim copies.
    """
    if not quiz_prompts:
        return False

    prompt = registry.render(
        "quiz_answer_guard",
        {
            "learner_message": learner_message,
            "quiz_questions": "\n".join(f"- {prompt}" for prompt in quiz_prompts),
        },
        version=1,
    )
    try:
        raw = await client.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=64,
        )
    except Exception:
        # Fail open: an unavailable/erroring model must never block a legitimate
        # question. Exact-prompt matching still covers verbatim copies upstream.
        return False
    return _parse_match(raw)


def _parse_match(raw: str) -> bool:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    try:
        data = json.loads(cleaned)
    except Exception:
        match = re.search(r'"matches_quiz_question"\s*:\s*(true|false)', cleaned, re.IGNORECASE)
        return bool(match) and match.group(1).lower() == "true"
    value = data.get("matches_quiz_question")
    return value is True
