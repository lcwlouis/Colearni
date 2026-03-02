"""Per-session state for the Socratic interactive tutor protocol."""
from __future__ import annotations
from pydantic import BaseModel, Field


class TutorState(BaseModel):
    """Tracks the learner's progress through a Socratic concept session."""

    active: bool = False
    concept: str = ""
    bloom: str = "Remember"  # Remember | Understand | Apply | Analyze | Evaluate | Create
    bloom_step: int = 1      # 1-6 mapping to Bloom stages
    step: int = 1            # 1-5 (Observe / Name parts / Relation=set / Apply / Analyze)
    step_labels: list[str] = Field(default_factory=lambda: [
        "Observe", "Name parts", "Relation = set", "Apply (mini test)", "Analyze (keys/constraints)"
    ])

    # DATA BLOCK — the micro-world table
    table_name: str = ""
    table_columns: list[str] = Field(default_factory=list)
    table_rows: list[list[str]] = Field(default_factory=list)

    # Mode flags
    duplicates_mode: bool = False
    nulls_mode: bool = False

    # Learner tracking
    misconceptions_detected: list[str] = Field(default_factory=list)
    last_user_answer: str = ""

    def step_checklist(self) -> str:
        """Render the 5-step checklist as markdown."""
        lines: list[str] = []
        for i, label in enumerate(self.step_labels, start=1):
            marker = "[x]" if i < self.step else ("[ ]")
            if i == self.step:
                marker = "[>]"  # current step
            lines.append(f"- {marker} {i} {label}")
        return "\n".join(lines)

    def bloom_indicator(self) -> str:
        """e.g. 'Understand 2/6'"""
        return f"{self.bloom} {self.bloom_step}/6"

    def data_block(self) -> str:
        """Render the DATA BLOCK as a text representation."""
        if not self.table_name:
            return "(no table defined yet)"
        schema = f"{self.table_name}({', '.join(self.table_columns)})"
        rows_str = "\n".join(f"  {row}" for row in self.table_rows)
        flags = f"duplicates_mode: {'on' if self.duplicates_mode else 'off'}, nulls_mode: {'on' if self.nulls_mode else 'off'}"
        return f"schema: {schema}\nrows:\n{rows_str}\n{flags}"

    def state_block(self) -> str:
        """Render the machine-readable STATE block."""
        misconceptions = ", ".join(self.misconceptions_detected) if self.misconceptions_detected else "none"
        return (
            f"STATE\n"
            f"concept: {self.concept}\n"
            f"bloom: {self.bloom} ({self.bloom_step}/6)\n"
            f"table: {self.table_name}({', '.join(self.table_columns)})\n"
            f"step: {self.step}\n"
            f"duplicates_mode: {'on' if self.duplicates_mode else 'off'}\n"
            f"nulls_mode: {'on' if self.nulls_mode else 'off'}\n"
            f"misconceptions_detected: [{misconceptions}]\n"
            f"last_user_answer: {self.last_user_answer}"
        )

    def init_relation_concept(self) -> None:
        """Initialize state for the 'Relation' concept demo."""
        self.active = True
        self.concept = "Relation"
        self.bloom = "Remember"
        self.bloom_step = 1
        self.step = 1
        self.table_name = "Students"
        self.table_columns = ["sid", "name", "major", "gpa"]
        self.table_rows = [
            ["101", "Alice", "CS", "3.8"],
            ["102", "Bob", "Math", "3.5"],
            ["103", "Carol", "CS", "3.9"],
        ]
        self.duplicates_mode = False
        self.nulls_mode = False
        self.misconceptions_detected = []
        self.last_user_answer = ""
