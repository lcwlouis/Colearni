"""Parse user chat messages for Socratic tutor commands.

Commands are detected by simple prefix/regex matching. If the message
is a regular conversational message, returns None.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from core.schemas.tutor_state import TutorState


CommandType = Literal[
    "hint", "reveal", "next", "quiz",
    "add_row", "delete_row", "update_row", "shuffle_rows",
    "set_duplicates", "set_nulls", "highlight_key",
]


@dataclass
class TutorCommand:
    """A parsed tutor command."""
    type: CommandType
    args: list[str] = field(default_factory=list)
    raw: str = ""


def parse_command(message: str) -> TutorCommand | None:
    """Parse a user message as a tutor command. Returns None if not a command."""
    text = message.strip().lower()

    # Simple commands (exact match)
    if text == "hint":
        return TutorCommand(type="hint", raw=message)
    if text == "reveal":
        return TutorCommand(type="reveal", raw=message)
    if text == "next":
        return TutorCommand(type="next", raw=message)
    if text == "quiz":
        return TutorCommand(type="quiz", raw=message)
    if text == "shuffle rows":
        return TutorCommand(type="shuffle_rows", raw=message)

    # Parameterized commands
    # add row: val1, val2, val3
    m = re.match(r"^add\s+row:\s*(.+)$", text)
    if m:
        values = [v.strip() for v in m.group(1).split(",")]
        return TutorCommand(type="add_row", args=values, raw=message)

    # delete row: <index>
    m = re.match(r"^delete\s+row:\s*(\d+)$", text)
    if m:
        return TutorCommand(type="delete_row", args=[m.group(1)], raw=message)

    # update row: <index> -> val1, val2, val3
    m = re.match(r"^update\s+row:\s*(\d+)\s*->\s*(.+)$", text)
    if m:
        values = [v.strip() for v in m.group(2).split(",")]
        return TutorCommand(type="update_row", args=[m.group(1)] + values, raw=message)

    # set duplicates: on|off
    m = re.match(r"^set\s+duplicates:\s*(on|off)$", text)
    if m:
        return TutorCommand(type="set_duplicates", args=[m.group(1)], raw=message)

    # set nulls: on|off
    m = re.match(r"^set\s+nulls:\s*(on|off)$", text)
    if m:
        return TutorCommand(type="set_nulls", args=[m.group(1)], raw=message)

    # highlight key: col1, col2
    m = re.match(r"^highlight\s+key:\s*(.+)$", text)
    if m:
        cols = [c.strip() for c in m.group(1).split(",")]
        return TutorCommand(type="highlight_key", args=cols, raw=message)

    return None


def apply_command(state: TutorState, cmd: TutorCommand) -> str:
    """Apply a command to the tutor state. Returns a status message for the LLM context.

    Table-mutating commands modify state in-place and return a description
    of what changed so the LLM can acknowledge it.
    """
    import random

    if cmd.type == "add_row":
        if len(cmd.args) != len(state.table_columns):
            return f"Error: expected {len(state.table_columns)} values ({', '.join(state.table_columns)}), got {len(cmd.args)}."
        state.table_rows.append(cmd.args)
        return f"Added row {cmd.args} to {state.table_name}."

    if cmd.type == "delete_row":
        idx = int(cmd.args[0])
        if idx < 0 or idx >= len(state.table_rows):
            return f"Error: row index {idx} out of range (0–{len(state.table_rows) - 1})."
        removed = state.table_rows.pop(idx)
        return f"Deleted row {idx} ({removed}) from {state.table_name}."

    if cmd.type == "update_row":
        idx = int(cmd.args[0])
        values = cmd.args[1:]
        if idx < 0 or idx >= len(state.table_rows):
            return f"Error: row index {idx} out of range (0–{len(state.table_rows) - 1})."
        if len(values) != len(state.table_columns):
            return f"Error: expected {len(state.table_columns)} values, got {len(values)}."
        old = state.table_rows[idx]
        state.table_rows[idx] = values
        return f"Updated row {idx}: {old} → {values}."

    if cmd.type == "shuffle_rows":
        random.shuffle(state.table_rows)
        return f"Rows in {state.table_name} have been shuffled."

    if cmd.type == "set_duplicates":
        state.duplicates_mode = cmd.args[0] == "on"
        return f"duplicates_mode set to {'on' if state.duplicates_mode else 'off'}."

    if cmd.type == "set_nulls":
        state.nulls_mode = cmd.args[0] == "on"
        return f"nulls_mode set to {'on' if state.nulls_mode else 'off'}."

    if cmd.type == "highlight_key":
        return f"Highlight key column(s): {', '.join(cmd.args)}."

    # hint, reveal, next, quiz — handled by the LLM prompt, not state mutations
    if cmd.type == "hint":
        return "USER_COMMAND: hint — provide a small hint (1–2 lines) and restate the same question."
    if cmd.type == "reveal":
        return "USER_COMMAND: reveal — provide the explanation + correct answer, then advance the step."
    if cmd.type == "next":
        state.step = min(state.step + 1, 5)
        return f"USER_COMMAND: next — advancing to step {state.step}."
    if cmd.type == "quiz":
        return "USER_COMMAND: quiz — generate Quick Check Cards (Recall, Apply, Analyze)."

    return ""
