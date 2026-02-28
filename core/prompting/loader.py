"""Prompt asset loader – reads Markdown prompt files from disk."""

from __future__ import annotations

import re
from pathlib import Path

from core.prompting.models import OutputFormat, PromptAsset, PromptMeta, TaskType

_ASSETS_DIR = Path(__file__).parent / "assets"

# Match {placeholder_name} but not {{escaped}}
_PLACEHOLDER_RE = re.compile(r"(?<!\{)\{([a-z_][a-z0-9_]*)\}(?!\})")

# Front-matter key regex (simple key: value lines at the top of the file)
_FRONT_MATTER_RE = re.compile(r"^([a-z_]+):\s*(.+)$", re.MULTILINE)


class PromptLoadError(Exception):
    """Raised when a prompt asset cannot be loaded."""


def _parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Split optional ``key: value`` front-matter from template body.

    Front-matter ends at the first blank line or the first line that
    does not match the ``key: value`` pattern.
    """
    meta: dict[str, str] = {}
    lines = text.split("\n")
    body_start = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            body_start = i + 1
            break
        m = _FRONT_MATTER_RE.match(stripped)
        if m:
            meta[m.group(1)] = m.group(2).strip()
            body_start = i + 1
        else:
            body_start = i
            break

    body = "\n".join(lines[body_start:])
    return meta, body


def _detect_placeholders(template: str) -> frozenset[str]:
    """Return the set of placeholder names found in *template*."""
    return frozenset(_PLACEHOLDER_RE.findall(template))


def load_asset(prompt_id: str, *, assets_dir: Path | None = None) -> PromptAsset:
    """Load a prompt asset by its stable prompt ID.

    The file is located at ``<assets_dir>/<task_folder>/<file>.md`` where
    ``<task_folder>`` is derived from the prompt ID prefix (everything
    before the last ``_v<N>`` segment) and mapped to a :class:`TaskType`.

    Raises :class:`PromptLoadError` if the file is missing or malformed.
    """
    root = assets_dir or _ASSETS_DIR

    # Resolve file path from prompt_id
    path = root / f"{prompt_id}.md"
    if not path.exists():
        # Try nested: task_folder / filename
        parts = prompt_id.rsplit("_v", 1)
        if len(parts) == 2:
            base_name = parts[0]
            # e.g. tutor_socratic -> tutor/socratic_v1.md
            folder_parts = base_name.split("_", 1)
            if len(folder_parts) == 2:
                folder, name = folder_parts
                path = root / folder / f"{name}_v{parts[1]}.md"

    if not path.exists():
        raise PromptLoadError(
            f"Prompt asset not found for '{prompt_id}'. "
            f"Searched: {root / f'{prompt_id}.md'} and nested paths."
        )

    raw = path.read_text(encoding="utf-8")
    front, template = _parse_front_matter(raw)

    # Build metadata from front-matter with sensible defaults
    task_str = front.get("task_type", _infer_task_type(prompt_id))
    try:
        task_type = TaskType(task_str)
    except ValueError:
        raise PromptLoadError(
            f"Unknown task_type '{task_str}' in asset '{prompt_id}'."
        )

    version = int(front.get("version", _infer_version(prompt_id)))
    fmt = front.get("output_format", "markdown")
    output_format: OutputFormat = fmt if fmt in ("json", "text") else "markdown"
    description = front.get("description", "")

    meta = PromptMeta(
        prompt_id=prompt_id,
        task_type=task_type,
        version=version,
        output_format=output_format,
        description=description,
    )

    placeholders = _detect_placeholders(template)

    return PromptAsset(meta=meta, template=template, placeholders=placeholders)


def _infer_task_type(prompt_id: str) -> str:
    """Best-effort task type from the prompt ID prefix."""
    for tt in TaskType:
        if prompt_id.startswith(tt.value):
            return tt.value
    return "tutor"


def _infer_version(prompt_id: str) -> int:
    """Extract version number from ``_vN`` suffix."""
    m = re.search(r"_v(\d+)$", prompt_id)
    return int(m.group(1)) if m else 1


def list_assets(*, assets_dir: Path | None = None) -> list[str]:
    """Return prompt IDs for all ``.md`` files under *assets_dir*."""
    root = assets_dir or _ASSETS_DIR
    ids: list[str] = []
    for md_file in sorted(root.rglob("*.md")):
        rel = md_file.relative_to(root)
        # Convert path to prompt_id: folder/name_v1.md -> folder_name_v1
        stem = rel.with_suffix("").as_posix().replace("/", "_")
        ids.append(stem)
    return ids
