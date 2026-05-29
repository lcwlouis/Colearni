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

RETRIEVAL_TOOLS = [
    GET_CONCEPT_SOURCES_TOOL,
    GET_GRAPH_NEIGHBOURHOOD_TOOL,
    SEARCH_SOURCES_TOOL,
    READ_DOCUMENT_SECTION_TOOL,
]
