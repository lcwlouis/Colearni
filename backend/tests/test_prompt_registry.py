import pytest

from backend.app.agents.prompts.registry import PromptRegistry


def test_prompt_registry_loads_and_renders_versioned_prompt(tmp_path):
    prompt_path = tmp_path / "example_task.v1.md"
    prompt_path.write_text(
        "---\ntask: example_task\nversion: 1\ntemperature: 0.3\n---\n\nHello {{ name }}."
    )

    registry = PromptRegistry(prompt_dir=tmp_path)
    template = registry.load("example_task", version=1)

    assert template.task == "example_task"
    assert template.version == 1
    assert template.temperature == 0.3
    assert template.render({"name": "learner"}) == "Hello learner."


def test_prompt_registry_loads_latest_numeric_version(tmp_path):
    for version in (2, 10):
        (tmp_path / f"example_task.v{version}.md").write_text(
            f"---\ntask: example_task\nversion: {version}\n---\n\nVersion {version}"
        )

    registry = PromptRegistry(prompt_dir=tmp_path)

    assert registry.load("example_task").version == 10


def test_prompt_registry_rejects_missing_variables(tmp_path):
    prompt_path = tmp_path / "example_task.v1.md"
    prompt_path.write_text("---\ntask: example_task\nversion: 1\n---\n\nHello {{ name }}.")

    registry = PromptRegistry(prompt_dir=tmp_path)

    with pytest.raises(KeyError, match="name"):
        registry.render("example_task", {}, version=1)
