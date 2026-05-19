from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PROMPT_DIR = Path(__file__).parent
_FRONT_MATTER_BOUNDARY = "---"
_VARIABLE_PATTERN = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")


@dataclass(frozen=True)
class PromptTemplate:
    task: str
    version: int
    body: str
    model_hint: str | None = None
    temperature: float | None = None

    def render(self, variables: dict[str, Any]) -> str:
        """Render a prompt body using the repo's simple Jinja-style placeholders."""

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in variables:
                raise KeyError(f"Missing prompt variable: {name}")
            return str(variables[name])

        return _VARIABLE_PATTERN.sub(replace, self.body)


class PromptRegistry:
    """Load versioned Markdown prompts from backend/app/agents/prompts/.

    The prompt files use a small YAML-like front matter block as documented in
    docs/PROMPTS.md. This parser intentionally supports only the scalar fields
    currently used by CoLearni prompts, avoiding an extra YAML dependency.
    """

    def __init__(self, prompt_dir: Path = _PROMPT_DIR) -> None:
        self._prompt_dir = prompt_dir

    def load(self, task: str, version: int | None = None) -> PromptTemplate:
        if version is None:
            candidates = list(self._prompt_dir.glob(f"{task}.v*.md"))
            if not candidates:
                raise FileNotFoundError(f"No prompt found for task: {task}")
            prompt_path = max(candidates, key=_version_from_path)
        else:
            prompt_path = self._prompt_dir / f"{task}.v{version}.md"
            if not prompt_path.exists():
                raise FileNotFoundError(f"Prompt not found: {prompt_path.name}")
        return _parse_prompt(prompt_path)

    def render(
        self,
        task: str,
        variables: dict[str, Any],
        version: int | None = None,
    ) -> str:
        return self.load(task, version=version).render(variables)


def _version_from_path(path: Path) -> int:
    match = re.search(r"\.v(\d+)\.md$", path.name)
    if match is None:
        raise ValueError(f"Prompt filename does not include a version: {path.name}")
    return int(match.group(1))


def _parse_prompt(path: Path) -> PromptTemplate:
    text = path.read_text()
    metadata: dict[str, str] = {}
    body = text

    if text.startswith(f"{_FRONT_MATTER_BOUNDARY}\n"):
        parts = text.split(f"\n{_FRONT_MATTER_BOUNDARY}\n", 1)
        if len(parts) != 2:
            raise ValueError(f"Prompt front matter is not closed: {path.name}")
        metadata_text = parts[0].removeprefix(f"{_FRONT_MATTER_BOUNDARY}\n")
        body = parts[1].strip()
        metadata = _parse_front_matter(metadata_text)

    task = metadata.get("task")
    version_text = metadata.get("version")
    if not task or version_text is None:
        raise ValueError(f"Prompt must define task and version: {path.name}")

    return PromptTemplate(
        task=task,
        version=int(version_text),
        body=body,
        model_hint=metadata.get("model_hint"),
        temperature=_optional_float(metadata.get("temperature")),
    )


def _parse_front_matter(text: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            raise ValueError(f"Invalid prompt front matter line: {line}")
        key, value = stripped.split(":", 1)
        metadata[key.strip()] = value.strip().strip("\"'")
    return metadata


def _optional_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


prompt_registry = PromptRegistry()
