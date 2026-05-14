from typing import Literal

BloomLevel = Literal["remember", "understand", "apply", "analyze", "evaluate", "create"]
ConceptLevel = Literal["umbrella", "topic", "subtopic", "granular"]
Difficulty = Literal["beginner", "intermediate", "advanced"]
NodeType = Literal["concept", "skill", "misconception", "example"]
RelationType = Literal["prerequisite", "contains", "application", "related"]
SourceAccess = Literal["public", "private", "restricted", "unknown"]
SourceOrigin = Literal["research_agent", "user_upload", "manual", "system"]
TargetDepth = BloomLevel
MasteryStatus = Literal["not_started", "learning", "needs_review", "mastered"]
