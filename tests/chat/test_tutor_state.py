"""Tests for core/schemas/tutor_state.py and domain/chat/tutor_state_store.py."""
import pytest
from core.schemas.tutor_state import TutorState
from domain.chat.tutor_state_store import (
    get_tutor_state,
    save_tutor_state,
    clear_tutor_state,
    is_tutor_active,
    _store,
)


class TestTutorState:
    def test_default_state(self):
        state = TutorState()
        assert state.active is False
        assert state.concept == ""
        assert state.bloom == "Remember"
        assert state.step == 1
        assert len(state.step_labels) == 5

    def test_init_relation(self):
        state = TutorState()
        state.init_relation_concept()
        assert state.active is True
        assert state.concept == "Relation"
        assert state.table_name == "Students"
        assert len(state.table_columns) == 4
        assert len(state.table_rows) == 3

    def test_init_concept_generic(self):
        state = TutorState()
        state.init_concept("B-Trees")
        assert state.active is True
        assert state.concept == "B-Trees"
        assert state.table_name == ""
        assert state.table_columns == []
        assert state.table_rows == []
        assert state.bloom == "Remember"
        assert state.step == 1

    def test_init_concept_different_topics(self):
        for topic in ["SQL Joins", "Database Engine Internals", "Normalization"]:
            state = TutorState()
            state.init_concept(topic)
            assert state.active is True
            assert state.concept == topic

    def test_init_concept_resets_state(self):
        state = TutorState()
        state.init_relation_concept()
        state.step = 3
        state.bloom = "Apply"
        state.misconceptions_detected = ["wrong"]
        state.init_concept("Indexing")
        assert state.step == 1
        assert state.bloom == "Remember"
        assert state.misconceptions_detected == []
        assert state.concept == "Indexing"

    def test_step_checklist(self):
        state = TutorState()
        state.init_relation_concept()
        state.step = 2
        checklist = state.step_checklist()
        assert "[x] 1" in checklist
        assert "[>] 2" in checklist
        assert "[ ] 3" in checklist

    def test_bloom_indicator(self):
        state = TutorState()
        state.bloom = "Understand"
        state.bloom_step = 2
        assert state.bloom_indicator() == "Understand 2/6"

    def test_data_block(self):
        state = TutorState()
        state.init_relation_concept()
        block = state.data_block()
        assert "Students(sid, name, major, gpa)" in block
        assert "Alice" in block
        assert "duplicates_mode: off" in block

    def test_state_block(self):
        state = TutorState()
        state.init_relation_concept()
        block = state.state_block()
        assert "concept: Relation" in block
        assert "bloom: Remember (1/6)" in block
        assert "step: 1" in block


class TestTutorStateStore:
    @pytest.fixture(autouse=True)
    def clear_store(self):
        _store.clear()
        yield
        _store.clear()

    def test_get_creates_default(self):
        state = get_tutor_state(999)
        assert state.active is False

    def test_save_and_get(self):
        state = TutorState()
        state.init_relation_concept()
        save_tutor_state(42, state)
        retrieved = get_tutor_state(42)
        assert retrieved.active is True
        assert retrieved.concept == "Relation"

    def test_isolation(self):
        """Modifying retrieved state should not affect the store."""
        state = TutorState()
        state.init_relation_concept()
        save_tutor_state(42, state)
        retrieved = get_tutor_state(42)
        retrieved.concept = "MODIFIED"
        again = get_tutor_state(42)
        assert again.concept == "Relation"

    def test_clear(self):
        state = TutorState()
        state.active = True
        save_tutor_state(42, state)
        assert is_tutor_active(42) is True
        clear_tutor_state(42)
        assert is_tutor_active(42) is False

    def test_is_active_false_by_default(self):
        assert is_tutor_active(999) is False
