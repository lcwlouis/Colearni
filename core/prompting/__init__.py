"""core.prompting – file-based prompt asset system for CoLearni.

Public API:
    - PromptRegistry: load, cache, and render prompt assets by stable ID.
    - PromptAsset / PromptMeta: typed prompt metadata.
    - render(): render a loaded asset with a context dict.
    - load_asset(): load a single asset from disk.
    - PromptLoadError / PromptRenderError: error types.
"""

from core.prompting.loader import PromptLoadError, list_assets, load_asset
from core.prompting.models import OutputFormat, PromptAsset, PromptMeta, TaskType
from core.prompting.registry import PromptRegistry
from core.prompting.renderer import PromptRenderError, render

__all__ = [
    "OutputFormat",
    "PromptAsset",
    "PromptLoadError",
    "PromptMeta",
    "PromptRegistry",
    "PromptRenderError",
    "TaskType",
    "list_assets",
    "load_asset",
    "render",
]
