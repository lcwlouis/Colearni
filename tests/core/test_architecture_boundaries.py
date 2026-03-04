"""Architecture boundary tests.

Prevent core/ and domain/ from importing apps/ code.
These layers must depend downward, never upward.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_RULES: list[tuple[str, str]] = [
    # (source layer directory, forbidden import prefix)
    ("core", "apps"),
    ("domain", "apps"),
]


def _collect_python_files(directory: Path) -> list[Path]:
    """Return all .py files under *directory*."""
    return sorted(directory.rglob("*.py"))


def _imports_from_file(filepath: Path) -> list[str]:
    """Return all top-level module names imported by *filepath*."""
    try:
        tree = ast.parse(filepath.read_text(), filename=str(filepath))
    except SyntaxError:
        return []
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.append(node.module)
    return modules


def _violations_for_rule(source_dir: str, forbidden_prefix: str) -> list[str]:
    """Return human-readable violation strings."""
    source_path = REPO_ROOT / source_dir
    if not source_path.is_dir():
        return []
    violations: list[str] = []
    for pyfile in _collect_python_files(source_path):
        rel = pyfile.relative_to(REPO_ROOT)
        for mod in _imports_from_file(pyfile):
            top_package = mod.split(".")[0]
            if top_package == forbidden_prefix:
                violations.append(f"{rel} imports {mod}")
    return violations


@pytest.mark.parametrize(
    "source_dir,forbidden_prefix",
    FORBIDDEN_RULES,
    ids=[f"{s}->!{f}" for s, f in FORBIDDEN_RULES],
)
def test_layer_boundary(source_dir: str, forbidden_prefix: str) -> None:
    violations = _violations_for_rule(source_dir, forbidden_prefix)
    assert violations == [], (
        f"Layer violation: {source_dir}/ must not import from {forbidden_prefix}/.\n"
        + "\n".join(f"  - {v}" for v in violations)
    )
