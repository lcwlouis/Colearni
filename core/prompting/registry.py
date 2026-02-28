"""Prompt registry – in-memory prompt asset catalog with version lookup."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.prompting.loader import list_assets, load_asset
from core.prompting.models import PromptAsset, PromptMeta, TaskType
from core.prompting.renderer import render


class PromptRegistry:
    """Singleton-style registry that loads and caches prompt assets.

    Usage::

        registry = PromptRegistry()
        rendered = registry.render("tutor_socratic_v1", {"query": "What is DNA?"})
    """

    def __init__(self, *, assets_dir: Path | None = None) -> None:
        self._assets_dir = assets_dir
        self._cache: dict[str, PromptAsset] = {}

    def get(self, prompt_id: str) -> PromptAsset:
        """Load and cache a prompt asset by stable ID.

        Raises :class:`PromptLoadError` if the asset does not exist.
        """
        if prompt_id not in self._cache:
            self._cache[prompt_id] = load_asset(
                prompt_id, assets_dir=self._assets_dir
            )
        return self._cache[prompt_id]

    def render(self, prompt_id: str, context: dict[str, Any]) -> str:
        """Load, cache, and render a prompt in one call.

        Raises :class:`PromptLoadError` or :class:`PromptRenderError`.
        """
        asset = self.get(prompt_id)
        return render(asset, context)

    def render_with_meta(
        self, prompt_id: str, context: dict[str, Any]
    ) -> tuple[str, PromptMeta]:
        """Render and return both the rendered text and metadata.

        Useful for observability: callers can log prompt_id, version,
        task_type, and rendered length from the returned meta.
        """
        asset = self.get(prompt_id)
        rendered = render(asset, context)
        return rendered, asset.meta

    def meta(self, prompt_id: str) -> PromptMeta:
        """Return metadata for a prompt asset."""
        return self.get(prompt_id).meta

    def list_ids(self) -> list[str]:
        """Return all discoverable prompt IDs."""
        return list_assets(assets_dir=self._assets_dir)

    def invalidate(self, prompt_id: str | None = None) -> None:
        """Clear cache for a single ID or the entire cache."""
        if prompt_id:
            self._cache.pop(prompt_id, None)
        else:
            self._cache.clear()

    def by_task(self, task_type: TaskType) -> list[str]:
        """Return cached prompt IDs filtered by task type."""
        return [
            pid for pid, asset in self._cache.items()
            if asset.meta.task_type == task_type
        ]
