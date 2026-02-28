"""Unit tests for the prompt kit – social intent classifier and prompt builder."""

from __future__ import annotations

import pytest
from core.schemas import EvidenceItem, EvidenceSourceType
from domain.chat.prompt_kit import (
    build_full_tutor_prompt,
    build_social_response,
    build_system_prompt,
    classify_social_intent,
    get_persona,
)


def _sample_evidence() -> list[EvidenceItem]:
    return [
        EvidenceItem(
            evidence_id="e1",
            source_type=EvidenceSourceType.WORKSPACE,
            content="Photosynthesis converts light energy into chemical energy.",
            document_id=1,
            chunk_id=2,
            chunk_index=0,
        )
    ]


class TestSocialIntentClassifier:
    @pytest.mark.parametrize(
        "query",
        [
            "Hi",
            "hello",
            "Hey there!",
            "Good morning",
            "Thanks",
            "thank you so much",
            "bye",
            "See you later",
            "how are you",
            "what's your name",
            "lol",
            "😂",
        ],
    )
    def test_social_queries_detected(self, query: str) -> None:
        assert classify_social_intent(query) is True

    @pytest.mark.parametrize(
        "query",
        [
            "Explain photosynthesis",
            "What is the difference between mitosis and meiosis?",
            "How does gradient descent work?",
            "Give me a summary of chapter 3",
            "What are the key points of the article?",
        ],
    )
    def test_study_queries_not_detected(self, query: str) -> None:
        assert classify_social_intent(query) is False


class TestSocialResponse:
    def test_greeting_response(self) -> None:
        persona = get_persona("colearni")
        resp = build_social_response("Hello!", persona=persona)
        assert resp  # non-empty
        assert "CoLearni" in resp or "study buddy" in resp or "explore" in resp

    def test_thanks_response(self) -> None:
        persona = get_persona("colearni")
        resp = build_social_response("Thanks!", persona=persona)
        assert "welcome" in resp.lower()

    def test_bye_response(self) -> None:
        persona = get_persona("colearni")
        resp = build_social_response("Bye!", persona=persona)
        assert "next time" in resp.lower() or "great work" in resp.lower()


class TestPersona:
    def test_default_persona(self) -> None:
        persona = get_persona("colearni")
        assert persona["name"] == "CoLearni"
        assert "system_prefix" in persona

    def test_unknown_persona_defaults(self) -> None:
        persona = get_persona("nonexistent")
        assert persona["name"] == "CoLearni"


class TestPromptBuilder:
    def test_system_prompt_socratic(self) -> None:
        persona = get_persona("colearni")
        prompt = build_system_prompt(persona=persona, style="socratic")
        assert "study partner" in prompt.lower()
        assert "guiding question" in prompt.lower()

    def test_system_prompt_direct(self) -> None:
        persona = get_persona("colearni")
        prompt = build_system_prompt(persona=persona, style="direct")
        assert "direct" in prompt.lower()
        assert "concise" in prompt.lower()

    def test_full_prompt_includes_evidence(self) -> None:
        persona = get_persona("colearni")
        prompt = build_full_tutor_prompt(
            query="Explain photosynthesis",
            evidence=_sample_evidence(),
            persona=persona,
            style="socratic",
        )
        assert "Explain photosynthesis" in prompt
        assert "Photosynthesis" in prompt

    def test_full_prompt_with_assessment_context(self) -> None:
        persona = get_persona("colearni")
        prompt = build_full_tutor_prompt(
            query="What is light energy?",
            evidence=[],
            persona=persona,
            style="direct",
            assessment_context="quiz_result: Biology — score 80%, passed.",
        )
        assert "quiz_result" in prompt

    def test_full_prompt_with_history(self) -> None:
        persona = get_persona("colearni")
        prompt = build_full_tutor_prompt(
            query="Continue",
            evidence=[],
            persona=persona,
            style="socratic",
            history_summary="User asked about cell division. Tutor explained mitosis.",
        )
        assert "cell division" in prompt
