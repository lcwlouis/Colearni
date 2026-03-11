"""Unit tests for the prompt kit – social intent classifier and prompt builder."""

from __future__ import annotations

import pytest

from core.llm_messages import MessageBuilder
from core.schemas import EvidenceItem, EvidenceSourceType, GroundingMode
from domain.chat.prompt_kit import (
    PromptMessages,
    build_full_tutor_prompt,
    build_full_tutor_prompt_with_meta,
    build_social_response,
    build_socratic_interactive_messages,
    build_socratic_interactive_prompt,
    build_system_prompt,
    build_tutor_messages,
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
        assert "ai tutor" in prompt.lower()
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

    def test_full_prompt_hybrid_sets_strict_flag_false(self) -> None:
        persona = get_persona("colearni")
        prompt = build_full_tutor_prompt(
            query="what do you know?",
            evidence=[],
            persona=persona,
            style="socratic",
            grounding_mode=GroundingMode.HYBRID,
        )
        assert "STRICT_GROUNDED_MODE: false" in prompt

    def test_full_prompt_with_learner_profile(self) -> None:
        persona = get_persona("colearni")
        prompt = build_full_tutor_prompt(
            query="What is momentum?",
            evidence=[],
            persona=persona,
            style="socratic",
            learner_profile_summary="Weak topics: Thermodynamics; Strong topics: Mechanics",
        )
        assert "Thermodynamics" in prompt
        assert "Mechanics" in prompt


class TestBuildTutorMessages:
    """Tests for the new MessageBuilder-based build_tutor_messages()."""

    def test_returns_message_builder_and_meta(self) -> None:
        persona = get_persona("colearni")
        builder, meta = build_tutor_messages(
            query="What is recursion?",
            evidence=_sample_evidence(),
            persona=persona,
            style="socratic",
        )
        assert isinstance(builder, MessageBuilder)

    def test_builder_has_system_prefix(self) -> None:
        persona = get_persona("colearni")
        builder, _ = build_tutor_messages(
            query="What is recursion?",
            evidence=[],
            persona=persona,
            style="socratic",
        )
        msgs = builder.build()
        system_msgs = [m for m in msgs if m["role"] == "system"]
        assert len(system_msgs) >= 1
        prefix = system_msgs[0]["content"]
        assert "CoLearni" in prefix
        # Template-loaded prefix includes guiding question instruction
        assert "guiding question" in prefix.lower()

    def test_builder_ends_with_user_message(self) -> None:
        persona = get_persona("colearni")
        builder, _ = build_tutor_messages(
            query="Explain mitosis",
            evidence=_sample_evidence(),
            persona=persona,
            style="direct",
        )
        msgs = builder.build()
        assert msgs[-1]["role"] == "user"
        assert "Explain mitosis" in msgs[-1]["content"]

    def test_evidence_in_context_block(self) -> None:
        persona = get_persona("colearni")
        builder, _ = build_tutor_messages(
            query="Explain photosynthesis",
            evidence=_sample_evidence(),
            persona=persona,
            style="socratic",
        )
        msgs = builder.build()
        # Evidence should be in a system context block, not in the user message
        system_msgs = [m for m in msgs if m["role"] == "system"]
        all_system = " ".join(m["content"] for m in system_msgs)
        assert "Photosynthesis" in all_system
        # User message should only have the query
        user_msg = msgs[-1]["content"]
        assert "Explain photosynthesis" in user_msg
        assert "USER_QUESTION:" not in user_msg

    def test_context_blocks_present(self) -> None:
        persona = get_persona("colearni")
        builder, _ = build_tutor_messages(
            query="Question",
            evidence=[],
            persona=persona,
            style="socratic",
            document_summaries="Chapter 1 overview",
            graph_context="A -> B -> C",
            assessment_context="score: 80%",
        )
        msgs = builder.build()
        system_msgs = [m for m in msgs if m["role"] == "system"]
        # prefix + 3 context blocks
        assert len(system_msgs) == 4
        all_system = " ".join(m["content"] for m in system_msgs)
        assert "Chapter 1 overview" in all_system
        assert "A -> B -> C" in all_system
        assert "score: 80%" in all_system

    def test_empty_context_blocks_skipped(self) -> None:
        persona = get_persona("colearni")
        builder, _ = build_tutor_messages(
            query="Question",
            evidence=[],
            persona=persona,
            style="socratic",
            document_summaries="",
            graph_context="",
            assessment_context="",
        )
        msgs = builder.build()
        system_msgs = [m for m in msgs if m["role"] == "system"]
        # Only the persona prefix — no context blocks
        assert len(system_msgs) == 1

    def test_direct_style_prefix(self) -> None:
        persona = get_persona("colearni")
        builder, _ = build_tutor_messages(
            query="Q",
            evidence=[],
            persona=persona,
            style="direct",
        )
        msgs = builder.build()
        prefix = msgs[0]["content"]
        # Template-loaded prefix includes direct-style phrasing
        assert "clear" in prefix.lower() or "concise" in prefix.lower()

    def test_history_turns_produce_discrete_messages(self) -> None:
        """L1.2: history_turns produces user/assistant pairs, not a context block."""
        persona = get_persona("colearni")
        turns = [("What is DNA?", "DNA is a molecule."), ("Tell me more", "It has a double helix.")]
        builder, _ = build_tutor_messages(
            query="Continue",
            evidence=[],
            persona=persona,
            style="socratic",
            history_turns=turns,
        )
        msgs = builder.build()
        # Should contain discrete user/assistant messages from history
        user_msgs = [m for m in msgs if m["role"] == "user"]
        asst_msgs = [m for m in msgs if m["role"] == "assistant"]
        # 2 history user + 1 final query = 3 user messages
        assert len(user_msgs) == 3
        assert len(asst_msgs) == 2
        assert user_msgs[0]["content"] == "What is DNA?"
        assert asst_msgs[0]["content"] == "DNA is a molecule."
        assert user_msgs[1]["content"] == "Tell me more"
        assert asst_msgs[1]["content"] == "It has a double helix."
        assert user_msgs[2]["content"] == "Continue"

    def test_history_turns_with_compacted_summary(self) -> None:
        """L1.2: compacted summary is added as context when history_turns provided."""
        persona = get_persona("colearni")
        turns = [("Hi", "Hello!")]
        builder, _ = build_tutor_messages(
            query="Go on",
            evidence=[],
            persona=persona,
            style="socratic",
            history_turns=turns,
            compacted_summary="Previously discussed photosynthesis.",
        )
        msgs = builder.build()
        system_msgs = [m for m in msgs if m["role"] == "system"]
        all_system = " ".join(m["content"] for m in system_msgs)
        assert "photosynthesis" in all_system.lower()
        # No "[history]" context block — uses compacted_history label instead
        assert "[compacted_history]" in all_system

    def test_history_turns_overrides_history_summary(self) -> None:
        """L1.2: when history_turns is provided, history_summary is ignored."""
        persona = get_persona("colearni")
        turns = [("Q1", "A1")]
        builder, _ = build_tutor_messages(
            query="Q2",
            evidence=[],
            persona=persona,
            style="socratic",
            history_summary="OLD SUMMARY TEXT",
            history_turns=turns,
        )
        msgs = builder.build()
        all_text = " ".join(m["content"] for m in msgs)
        # Old summary should NOT appear
        assert "OLD SUMMARY TEXT" not in all_text
        # But discrete messages should
        assert "Q1" in all_text
        assert "A1" in all_text

    def test_history_summary_fallback_still_works(self) -> None:
        """L1.2 backward compat: history_summary works when history_turns is None."""
        persona = get_persona("colearni")
        builder, _ = build_tutor_messages(
            query="Question",
            evidence=[],
            persona=persona,
            style="socratic",
            history_summary="User asked about biology.",
        )
        msgs = builder.build()
        system_msgs = [m for m in msgs if m["role"] == "system"]
        all_system = " ".join(m["content"] for m in system_msgs)
        assert "biology" in all_system.lower()
        assert "[history]" in all_system


class TestBuildFullTutorPromptWithMetaCompat:
    """Backward compatibility: build_full_tutor_prompt_with_meta returns PromptMessages."""

    def test_returns_prompt_messages(self) -> None:
        persona = get_persona("colearni")
        pm, meta = build_full_tutor_prompt_with_meta(
            query="What is recursion?",
            evidence=_sample_evidence(),
            persona=persona,
            style="socratic",
        )
        assert isinstance(pm, PromptMessages)
        assert isinstance(pm.system, str)
        assert isinstance(pm.user, str)

    def test_system_contains_persona_and_context(self) -> None:
        persona = get_persona("colearni")
        pm, _ = build_full_tutor_prompt_with_meta(
            query="Q",
            evidence=[],
            persona=persona,
            style="socratic",
            document_summaries="Biology chapter 5",
            assessment_context="quiz passed",
        )
        assert "CoLearni" in pm.system
        assert "Biology chapter 5" in pm.system
        assert "quiz passed" in pm.system

    def test_evidence_in_system_and_query_in_user(self) -> None:
        persona = get_persona("colearni")
        pm, _ = build_full_tutor_prompt_with_meta(
            query="Explain DNA",
            evidence=_sample_evidence(),
            persona=persona,
            style="direct",
        )
        assert "Explain DNA" in pm.user
        # Evidence is now in the system (context block), not the user message
        assert "Photosynthesis" in pm.system


class TestBuildSocraticInteractiveMessages:
    """Tests for build_socratic_interactive_messages()."""

    def test_returns_message_builder(self) -> None:
        builder, meta = build_socratic_interactive_messages(
            query="Tell me more",
            evidence=[],
            tutor_state_text="phase: explain",
        )
        assert isinstance(builder, MessageBuilder)

    def test_builder_structure(self) -> None:
        builder, _ = build_socratic_interactive_messages(
            query="Why?",
            evidence=_sample_evidence(),
            tutor_state_text="phase: question",
            command_context="/hint",
            document_summaries="Doc summary",
        )
        msgs = builder.build()
        assert msgs[-1]["role"] == "user"
        assert "Why?" in msgs[-1]["content"]
        system_msgs = [m for m in msgs if m["role"] == "system"]
        all_system = " ".join(m["content"] for m in system_msgs)
        assert "Socratic" in all_system
        assert "phase: question" in all_system
        assert "/hint" in all_system
        assert "Doc summary" in all_system

    def test_compat_wrapper_returns_prompt_messages(self) -> None:
        pm, meta = build_socratic_interactive_prompt(
            query="What next?",
            evidence=[],
            tutor_state_text="phase: hint",
        )
        assert isinstance(pm, PromptMessages)
        assert "What next?" in pm.user
        assert "Socratic" in pm.system


class TestPromptCacheStructure:
    """L3.2: Verify prompt structure supports prompt caching."""

    def test_stable_prefix_deterministic_across_turns(self) -> None:
        """Same style + persona → identical first system message."""
        persona = get_persona("colearni")
        builder1, _ = build_tutor_messages(
            query="What is DNA?",
            evidence=_sample_evidence(),
            persona=persona,
            style="socratic",
            document_summaries="Chapter 1: Biology basics",
            assessment_context="score: 90%",
        )
        builder2, _ = build_tutor_messages(
            query="Explain mitosis",
            evidence=[],
            persona=persona,
            style="socratic",
            document_summaries="Chapter 5: Cell division",
            graph_context="cell → mitosis → prophase",
        )
        msgs1 = builder1.build()
        msgs2 = builder2.build()
        assert msgs1[0]["content"] == msgs2[0]["content"]

    def test_variable_context_not_in_stable_prefix(self) -> None:
        """Variable per-turn data must be in separate context messages."""
        persona = get_persona("colearni")
        doc_marker = "UNIQUE_DOC_SUMMARY_XYZ"
        assess_marker = "UNIQUE_ASSESSMENT_ABC"
        builder, _ = build_tutor_messages(
            query="Q",
            evidence=[],
            persona=persona,
            style="socratic",
            document_summaries=doc_marker,
            assessment_context=assess_marker,
        )
        msgs = builder.build()
        prefix = msgs[0]["content"]
        assert doc_marker not in prefix
        assert assess_marker not in prefix
        all_system = " ".join(m["content"] for m in msgs if m["role"] == "system")
        assert doc_marker in all_system
        assert assess_marker in all_system

    def test_different_styles_produce_different_prefixes(self) -> None:
        persona = get_persona("colearni")
        socratic, _ = build_tutor_messages(
            query="Q", evidence=[], persona=persona, style="socratic",
        )
        direct, _ = build_tutor_messages(
            query="Q", evidence=[], persona=persona, style="direct",
        )
        assert socratic.build()[0]["content"] != direct.build()[0]["content"]

    def test_prefix_substantial_for_caching(self) -> None:
        """Stable prefix should be loaded from the template and be substantial."""
        persona = get_persona("colearni")
        builder, _ = build_tutor_messages(
            query="Q", evidence=[], persona=persona, style="socratic",
        )
        prefix = builder.build()[0]["content"]
        # Template-derived prefix includes Role, Goal, Rules, Output contract
        assert len(prefix) > 200
        assert "---Role---" in prefix or "CoLearni" in prefix
