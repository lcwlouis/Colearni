"""Prompt renderer – fills placeholders with explicit missing-key failures."""

from __future__ import annotations

import re
from typing import Any

from core.prompting.models import PromptAsset

_PLACEHOLDER_RE = re.compile(r"(?<!\{)\{([a-z_][a-z0-9_]*)\}(?!\})")


class PromptRenderError(Exception):
    """Raised when a prompt cannot be rendered due to missing placeholders."""


def render(asset: PromptAsset, context: dict[str, Any]) -> str:
    """Render the prompt template with the given context values.

    All placeholders declared in the template must be present in *context*.
    Raises :class:`PromptRenderError` if any required placeholder is missing.

    Values are converted to ``str`` before substitution.
    """
    missing = asset.placeholders - set(context.keys())
    if missing:
        raise PromptRenderError(
            f"Missing placeholders for prompt '{asset.meta.prompt_id}': "
            f"{sorted(missing)}"
        )

    def _replace(m: re.Match[str]) -> str:
        key = m.group(1)
        val = context.get(key)
        if val is None:
            return ""
        return str(val)

    return _PLACEHOLDER_RE.sub(_replace, asset.template)
