"""Tests for domain/chat/tutor_commands.py — command parser + state mutations."""
import pytest
from domain.chat.tutor_commands import parse_command, apply_command, TutorCommand
from core.schemas.tutor_state import TutorState


class TestParseCommand:
    def test_hint(self):
        cmd = parse_command("hint")
        assert cmd is not None
        assert cmd.type == "hint"

    def test_hint_case_insensitive(self):
        cmd = parse_command("HINT")
        assert cmd is not None
        assert cmd.type == "hint"

    def test_hint_with_whitespace(self):
        cmd = parse_command("  hint  ")
        assert cmd is not None
        assert cmd.type == "hint"

    def test_reveal(self):
        cmd = parse_command("reveal")
        assert cmd is not None
        assert cmd.type == "reveal"

    def test_next(self):
        cmd = parse_command("next")
        assert cmd is not None
        assert cmd.type == "next"

    def test_quiz(self):
        cmd = parse_command("quiz")
        assert cmd is not None
        assert cmd.type == "quiz"

    def test_shuffle_rows(self):
        cmd = parse_command("shuffle rows")
        assert cmd is not None
        assert cmd.type == "shuffle_rows"

    def test_add_row(self):
        cmd = parse_command("add row: Alice, CS, 3.8")
        assert cmd is not None
        assert cmd.type == "add_row"
        assert cmd.args == ["alice", "cs", "3.8"]

    def test_delete_row(self):
        cmd = parse_command("delete row: 2")
        assert cmd is not None
        assert cmd.type == "delete_row"
        assert cmd.args == ["2"]

    def test_update_row(self):
        cmd = parse_command("update row: 1 -> Bob, Math, 3.5")
        assert cmd is not None
        assert cmd.type == "update_row"
        assert cmd.args == ["1", "bob", "math", "3.5"]

    def test_set_duplicates_on(self):
        cmd = parse_command("set duplicates: on")
        assert cmd is not None
        assert cmd.type == "set_duplicates"
        assert cmd.args == ["on"]

    def test_set_nulls_off(self):
        cmd = parse_command("set nulls: off")
        assert cmd is not None
        assert cmd.type == "set_nulls"
        assert cmd.args == ["off"]

    def test_highlight_key(self):
        cmd = parse_command("highlight key: sid, name")
        assert cmd is not None
        assert cmd.type == "highlight_key"
        assert cmd.args == ["sid", "name"]

    def test_regular_message_returns_none(self):
        assert parse_command("What is a relation?") is None

    def test_empty_string_returns_none(self):
        assert parse_command("") is None

    def test_partial_command_returns_none(self):
        assert parse_command("add") is None

    def test_invalid_delete_row(self):
        assert parse_command("delete row: abc") is None

    def test_sentence_containing_hint(self):
        # "give me a hint" should NOT match — only exact "hint"
        assert parse_command("give me a hint") is None


class TestApplyCommand:
    @pytest.fixture
    def state(self):
        s = TutorState()
        s.init_relation_concept()
        return s

    def test_add_row(self, state):
        cmd = TutorCommand(type="add_row", args=["104", "Dave", "Physics", "3.2"])
        result = apply_command(state, cmd)
        assert "Added row" in result
        assert len(state.table_rows) == 4
        assert state.table_rows[-1] == ["104", "Dave", "Physics", "3.2"]

    def test_add_row_wrong_count(self, state):
        cmd = TutorCommand(type="add_row", args=["104", "Dave"])
        result = apply_command(state, cmd)
        assert "Error" in result
        assert len(state.table_rows) == 3  # unchanged

    def test_delete_row(self, state):
        cmd = TutorCommand(type="delete_row", args=["1"])
        result = apply_command(state, cmd)
        assert "Deleted row" in result
        assert len(state.table_rows) == 2

    def test_delete_row_out_of_range(self, state):
        cmd = TutorCommand(type="delete_row", args=["10"])
        result = apply_command(state, cmd)
        assert "Error" in result
        assert len(state.table_rows) == 3  # unchanged

    def test_update_row(self, state):
        cmd = TutorCommand(type="update_row", args=["0", "101", "Alice", "Physics", "4.0"])
        result = apply_command(state, cmd)
        assert "Updated row" in result
        assert state.table_rows[0] == ["101", "Alice", "Physics", "4.0"]

    def test_shuffle_rows(self, state):
        original = [row[:] for row in state.table_rows]
        cmd = TutorCommand(type="shuffle_rows")
        apply_command(state, cmd)
        assert len(state.table_rows) == len(original)
        # All original rows still present (just potentially reordered)
        for row in original:
            assert row in state.table_rows

    def test_set_duplicates(self, state):
        cmd = TutorCommand(type="set_duplicates", args=["on"])
        apply_command(state, cmd)
        assert state.duplicates_mode is True

    def test_set_nulls(self, state):
        cmd = TutorCommand(type="set_nulls", args=["on"])
        apply_command(state, cmd)
        assert state.nulls_mode is True

    def test_next_advances_step(self, state):
        assert state.step == 1
        cmd = TutorCommand(type="next")
        apply_command(state, cmd)
        assert state.step == 2

    def test_next_caps_at_5(self, state):
        state.step = 5
        cmd = TutorCommand(type="next")
        apply_command(state, cmd)
        assert state.step == 5

    def test_hint_returns_directive(self, state):
        cmd = TutorCommand(type="hint")
        result = apply_command(state, cmd)
        assert "USER_COMMAND: hint" in result

    def test_reveal_returns_directive(self, state):
        cmd = TutorCommand(type="reveal")
        result = apply_command(state, cmd)
        assert "USER_COMMAND: reveal" in result
