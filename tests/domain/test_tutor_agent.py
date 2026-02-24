"""Unit tests for tutor style policy and generation behavior."""

from __future__ import annotations

import pytest
from core.schemas import EvidenceItem, EvidenceSourceType
from domain.chat.tutor_agent import (
    build_tutor_prompt,
    build_tutor_response_text,
    resolve_tutor_style,
)


class FailingTutorClient:
    def generate_tutor_text(self, *, prompt: str) -> str:  # noqa: ARG002
        raise RuntimeError("llm unavailable")


def _sample_evidence() -> list[EvidenceItem]:
    return [
        EvidenceItem(
            evidence_id="e1",
            source_type=EvidenceSourceType.WORKSPACE,
            content="Linear maps preserve vector addition and scalar multiplication.",
            document_id=1,
            chunk_id=2,
            chunk_index=0,
        )
    ]


@pytest.mark.parametrize(
    ("mastery_status", "expected_style"),
    [
        ("learned", "direct"),
        ("locked", "socratic"),
        ("learning", "socratic"),
        (None, "socratic"),
    ],
)
def test_resolve_tutor_style(mastery_status: str | None, expected_style: str) -> None:
    assert resolve_tutor_style(mastery_status=mastery_status) == expected_style


def test_build_tutor_response_falls_back_on_provider_failure() -> None:
    text = build_tutor_response_text(
        query="Explain linear maps",
        evidence=_sample_evidence(),
        mastery_status="learned",
        llm_client=FailingTutorClient(),
    )

    assert text.startswith("From your notes, here is a direct explanation:")


def test_build_tutor_prompt_includes_socratic_constraints() -> None:
    prompt = build_tutor_prompt(
        query="How do I derive this?",
        evidence=_sample_evidence(),
        style="socratic",
    )

    assert "STYLE: socratic" in prompt
    assert "Do not provide the final answer directly." in prompt
    assert "guiding question" in prompt
