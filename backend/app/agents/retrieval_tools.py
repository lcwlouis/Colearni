from backend.app.agents.provider_tools import ProviderToolDefinition

GET_CONCEPT_SOURCES_TOOL = ProviderToolDefinition(
    name="get_concept_sources",
    description=(
        "List sources linked to a concept. Returns title, origin, access, "
        "url, and relation. Never returns raw file content, object keys, "
        "or hashes. Defaults to the current concept when concept_id is omitted."
    ),
    parameters={
        "type": "object",
        "properties": {
            "concept_id": {
                "type": "string",
                "description": "UUID of the concept whose sources to list.",
            },
        },
        "required": [],
        "additionalProperties": False,
    },
    public_argument_fields=("concept_id",),
)

GET_GRAPH_NEIGHBOURHOOD_TOOL = ProviderToolDefinition(
    name="get_graph_neighbourhood",
    description=(
        "Return the immediate graph neighbourhood of a concept: "
        "prerequisites, containing nodes, contained nodes, related, "
        "and application nodes. Defaults to the current concept when concept_id is omitted."
    ),
    parameters={
        "type": "object",
        "properties": {
            "concept_id": {
                "type": "string",
                "description": "UUID of the concept to query.",
            },
        },
        "required": [],
        "additionalProperties": False,
    },
    public_argument_fields=("concept_id",),
)

SEARCH_SOURCES_TOOL = ProviderToolDefinition(
    name="search_sources",
    description=(
        "Search source document chunks by keyword within the current workspace. "
        "Results are automatically scoped to the concept currently being tutored. "
        "Returns brief matching snippets plus chunk metadata including section_heading, "
        "line_start, and line_end. Use read_document_section only when these snippets "
        "are insufficient and fuller context is needed."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Keyword to match against source chunk text.",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    public_argument_fields=("query",),
)

READ_DOCUMENT_SECTION_TOOL = ProviderToolDefinition(
    name="read_document_section",
    description=(
        "Read a window of lines from a source document starting at a given line number. "
        "Use the line_start value returned by search_sources to navigate to a relevant "
        "section. Returns markdown-formatted text from that location in the document. "
        "Never returns raw file content, object keys, or hashes."
    ),
    parameters={
        "type": "object",
        "properties": {
            "source_revision_id": {
                "type": "string",
                "description": "UUID of the source revision to read from.",
            },
            "line_start": {
                "type": "integer",
                "description": "1-indexed line number to start reading from.",
            },
            "window_lines": {
                "type": "integer",
                "description": "Number of lines to read (default 50, max 200).",
            },
        },
        "required": ["source_revision_id", "line_start"],
        "additionalProperties": False,
    },
    public_argument_fields=("source_revision_id", "line_start", "window_lines"),
)

GET_CONCEPT_PRIMER_TOOL = ProviderToolDefinition(
    name="get_concept_primer",
    description=(
        "Return this concept's orientation primer: a short overview, key terms with "
        "one-line definitions, and sample starter questions. Use it to re-orient a "
        "learner (e.g. when they ask how to get started). The primer is injected "
        "automatically on the opening turn, so only call this on later turns. "
        "Defaults to the current concept when concept_id is omitted. Returns abstract "
        "concept-level orientation only, never raw source content."
    ),
    parameters={
        "type": "object",
        "properties": {
            "concept_id": {
                "type": "string",
                "description": "UUID of the concept whose primer to read.",
            },
        },
        "required": [],
        "additionalProperties": False,
    },
    public_argument_fields=("concept_id",),
)

RETRIEVAL_TOOLS = [
    GET_CONCEPT_SOURCES_TOOL,
    GET_GRAPH_NEIGHBOURHOOD_TOOL,
    SEARCH_SOURCES_TOOL,
    READ_DOCUMENT_SECTION_TOOL,
    GET_CONCEPT_PRIMER_TOOL,
]

# Suggest-quiz is NOT a retrieval tool: it never reads sources or graph context
# and is offered on EVERY tutor turn (see Phase 14), unlike the retrieval tools
# which are gated on the concept having sources or a cached primer. It is kept
# out of RETRIEVAL_TOOLS / select_retrieval_tools and appended separately by the
# tutor orchestrator so it is always available. The model only emits an intent;
# the backend stays the owner of quiz drafts, grading, and mastery.
SUGGEST_QUIZ_TOOL = ProviderToolDefinition(
    name="suggest_quiz",
    description=(
        "Suggest a quiz card to the learner at a good moment. This only surfaces "
        "an opt-in suggestion; it never generates, opens, or grades a quiz, and it "
        "never changes mastery. The learner chooses whether to start it. Use "
        "quiz_type='practice' anytime focused practice would help the learner "
        "consolidate. Use quiz_type='level_up' ONLY when the learner looks "
        "near-ready to advance this concept (e.g. they have demonstrated solid "
        "understanding this turn); do not push level-up prematurely. Always give a "
        "short, encouraging, learner-visible reason. The current concept is implied; "
        "do not pass a concept id. Call this at most once per turn."
    ),
    parameters={
        "type": "object",
        "properties": {
            "quiz_type": {
                "type": "string",
                "enum": ["level_up", "practice"],
                "description": "Kind of quiz to suggest.",
            },
            "reason": {
                "type": "string",
                "description": "Short learner-visible reason for the suggestion.",
            },
        },
        "required": ["quiz_type", "reason"],
        "additionalProperties": False,
    },
    public_argument_fields=("quiz_type", "reason"),
)

SUGGEST_FLASHCARDS_TOOL = ProviderToolDefinition(
    name="suggest_flashcards",
    description=(
        "Suggest generating flashcards for the learner when spaced recall would help. "
        "This only surfaces an opt-in suggestion; it never generates cards, opens "
        "the panel, grades anything, or changes mastery. Use it when the learner "
        "would benefit from recall-first review of source-grounded facts from this "
        "concept. Always give a short, encouraging, learner-visible reason. The "
        "current concept is implied; do not pass a concept id. Call this at most "
        "once per turn."
    ),
    parameters={
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Short learner-visible reason for the suggestion.",
            },
        },
        "required": ["reason"],
        "additionalProperties": False,
    },
    public_argument_fields=("reason",),
)

# Suggest-artifact is NOT a retrieval tool either: like suggest_quiz it reads no
# sources or graph context and is offered on EVERY tutor turn (Phase 15f). It is
# appended separately by the tutor orchestrator so it is always available. The
# model only emits an intent (kind + reason); the backend stays the owner of
# artifact generation/persistence, which happens only when the learner clicks the
# CTA and reuses the existing artifact build path. The current concept is implied;
# the model never passes a concept id (trusted backend context, like suggest_quiz).
SUGGEST_ARTIFACT_TOOL = ProviderToolDefinition(
    name="suggest_artifact",
    description=(
        "Suggest a learning artifact (a visual or interactive aid) to the learner "
        "at a good moment. This only surfaces an opt-in suggestion; it never "
        "generates, opens, or persists an artifact, and it never changes mastery. "
        "The learner chooses whether to build it. Pick the kind that best fits what "
        "would help right now: 'worked_example' for a step-by-step solved problem, "
        "'comparison_card' to contrast two related ideas, 'timeline' for ordered "
        "events or steps, 'mini_graph' for a small relationship diagram, "
        "'simulation_slider' for an interactive parameter to explore. Always give a "
        "short, encouraging, learner-visible reason. The current concept is implied; "
        "do not pass a concept id. Call this at most once per turn."
    ),
    parameters={
        "type": "object",
        "properties": {
            "kind": {
                "type": "string",
                "enum": [
                    "worked_example",
                    "comparison_card",
                    "timeline",
                    "mini_graph",
                    "simulation_slider",
                ],
                "description": "Kind of artifact to suggest.",
            },
            "reason": {
                "type": "string",
                "description": "Short learner-visible reason for the suggestion.",
            },
        },
        "required": ["kind", "reason"],
        "additionalProperties": False,
    },
    public_argument_fields=("kind", "reason"),
)


def select_retrieval_tools(
    *,
    has_sources: bool,
    has_primer: bool,
) -> list[ProviderToolDefinition]:
    """Build the retrieval tool set scoped to what is actually useful this turn.

    Source tools (search_sources, read_document_section, get_concept_sources) are
    only offered when the concept has at least one linked source, so source-less
    concepts are never told to search material that does not exist. The graph
    neighbourhood tool is always offered when the loop runs (it leaks no source
    content), and get_concept_primer is offered whenever a primer is cached so the
    tutor can re-orient a learner on later turns without auto-flooding context.
    """
    tools: list[ProviderToolDefinition] = []
    if has_sources:
        tools.append(GET_CONCEPT_SOURCES_TOOL)
        tools.append(SEARCH_SOURCES_TOOL)
        tools.append(READ_DOCUMENT_SECTION_TOOL)
    tools.append(GET_GRAPH_NEIGHBOURHOOD_TOOL)
    if has_primer:
        tools.append(GET_CONCEPT_PRIMER_TOOL)
    return tools
