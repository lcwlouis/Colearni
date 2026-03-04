"""Typed metadata models for the prompt asset system."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class TaskType(str, Enum):
    """Prompt task family identifiers."""

    TUTOR = "tutor"
    ROUTING = "routing"
    GRAPH = "graph"
    ASSESSMENT = "assessment"
    PRACTICE = "practice"
    SUGGESTION = "suggestion"
    DOCUMENT = "document"


OutputFormat = Literal["markdown", "json", "text"]


@dataclass(frozen=True)
class PromptMeta:
    """Immutable metadata attached to every prompt asset.

    Attributes:
        prompt_id: Stable identifier, e.g. ``tutor_socratic_v1``.
        task_type: Which agent family owns this prompt.
        version: Integer version; bump when the contract changes.
        output_format: Expected output type (``"markdown"`` or ``"json"``).
        description: One-line human description.
    """

    prompt_id: str
    task_type: TaskType
    version: int = 1
    output_format: OutputFormat = "markdown"
    description: str = ""


@dataclass(frozen=True)
class PromptAsset:
    """A loaded prompt asset ready for rendering.

    Attributes:
        meta: Prompt metadata.
        template: Raw template string with ``{placeholder}`` slots.
    """

    meta: PromptMeta
    template: str
    placeholders: frozenset[str] = field(default_factory=frozenset)
