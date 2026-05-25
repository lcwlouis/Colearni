from backend.app.agents.provider_tools import ProviderToolDefinition

GET_CONCEPT_SOURCES_TOOL = ProviderToolDefinition(
    name="get_concept_sources",
    description=(
        "List sources linked to a concept. Returns title, origin, access, "
        "url, and relation. Never returns raw file content, object keys, "
        "or hashes."
    ),
    parameters={
        "type": "object",
        "properties": {
            "concept_id": {
                "type": "string",
                "description": "UUID of the concept whose sources to list.",
            },
        },
        "required": ["concept_id"],
        "additionalProperties": False,
    },
    public_argument_fields=("concept_id",),
)

GET_GRAPH_NEIGHBOURHOOD_TOOL = ProviderToolDefinition(
    name="get_graph_neighbourhood",
    description=(
        "Return the immediate graph neighbourhood of a concept: "
        "prerequisites, containing nodes, contained nodes, related, "
        "and application nodes."
    ),
    parameters={
        "type": "object",
        "properties": {
            "concept_id": {
                "type": "string",
                "description": "UUID of the concept to query.",
            },
        },
        "required": ["concept_id"],
        "additionalProperties": False,
    },
    public_argument_fields=("concept_id",),
)

SEARCH_SOURCES_TOOL = ProviderToolDefinition(
    name="search_sources",
    description=(
        "Search sources by title keyword within the current workspace. "
        "Optionally scoped to a concept. Returns metadata only - "
        "never raw content."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Keyword to match against source titles.",
            },
            "concept_id": {
                "type": "string",
                "description": (
                    "Optional UUID to restrict search to sources "
                    "linked to one concept."
                ),
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    public_argument_fields=("query", "concept_id"),
)

RETRIEVAL_TOOLS = [
    GET_CONCEPT_SOURCES_TOOL,
    GET_GRAPH_NEIGHBOURHOOD_TOOL,
    SEARCH_SOURCES_TOOL,
]
