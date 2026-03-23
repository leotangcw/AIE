"""MCP Tools definitions for memory operations."""

from typing import Any


# Tool definitions following MCP schema
TOOL_DEFINITIONS = [
    {
        "name": "memory_store",
        "description": "Store a new memory to long-term memory store with automatic L0/L1/L2 tier generation",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Full content of the memory",
                },
                "name": {
                    "type": "string",
                    "description": "Name/title of the memory",
                },
                "context_type": {
                    "type": "string",
                    "enum": ["memory", "resource", "skill"],
                    "description": "Type of context",
                    "default": "memory",
                },
                "uri": {
                    "type": "string",
                    "description": "Optional custom URI path",
                },
                "parent_uri": {
                    "type": "string",
                    "description": "Optional parent memory URI for hierarchy",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional tags for categorization",
                },
                "source": {
                    "type": "string",
                    "description": "Source of the memory (chat, document, event)",
                    "default": "unknown",
                },
                "metadata": {
                    "type": "object",
                    "description": "Optional additional metadata",
                },
                "tenant_id": {
                    "type": "string",
                    "description": "Optional tenant ID for multi-tenancy",
                },
            },
            "required": ["content", "name"],
        },
    },
    {
        "name": "memory_recall",
        "description": "Recall relevant memories based on semantic search with hierarchical retrieval",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Query text to search for relevant memories",
                },
                "context_type": {
                    "type": "string",
                    "enum": ["memory", "resource", "skill", "all"],
                    "description": "Filter by context type",
                    "default": "all",
                },
                "user_id": {
                    "type": "string",
                    "description": "Filter to user's memories",
                },
                "agent_id": {
                    "type": "string",
                    "description": "Filter to agent's memories",
                },
                "session_id": {
                    "type": "string",
                    "description": "Filter to session's memories",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results",
                    "default": 5,
                },
                "level": {
                    "type": "integer",
                    "enum": [0, 1, 2],
                    "description": "Preferred content level (0=abstract, 1=overview, 2=full)",
                    "default": 2,
                },
                "tenant_id": {
                    "type": "string",
                    "description": "Tenant ID for multi-tenancy",
                },
                "context": {
                    "type": "string",
                    "description": "Optional session context for better intent analysis",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "memory_get",
        "description": "Get a specific memory by URI",
        "input_schema": {
            "type": "object",
            "properties": {
                "uri": {
                    "type": "string",
                    "description": "Memory URI to retrieve",
                },
                "level": {
                    "type": "integer",
                    "enum": [0, 1, 2],
                    "description": "Content level to retrieve",
                },
                "tenant_id": {
                    "type": "string",
                    "description": "Tenant ID for multi-tenancy",
                },
            },
            "required": ["uri"],
        },
    },
    {
        "name": "memory_update",
        "description": "Update an existing memory's content",
        "input_schema": {
            "type": "object",
            "properties": {
                "uri": {
                    "type": "string",
                    "description": "Memory URI to update",
                },
                "content": {
                    "type": "string",
                    "description": "New content",
                },
                "name": {
                    "type": "string",
                    "description": "New name",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "New tags",
                },
                "metadata": {
                    "type": "object",
                    "description": "New metadata",
                },
            },
            "required": ["uri"],
        },
    },
    {
        "name": "memory_delete",
        "description": "Delete a memory and all its children",
        "input_schema": {
            "type": "object",
            "properties": {
                "uri": {
                    "type": "string",
                    "description": "Memory URI to delete",
                },
            },
            "required": ["uri"],
        },
    },
    {
        "name": "memory_list",
        "description": "List memories under a URI prefix",
        "input_schema": {
            "type": "object",
            "properties": {
                "uri_prefix": {
                    "type": "string",
                    "description": "URI prefix to list under",
                },
                "context_type": {
                    "type": "string",
                    "enum": ["memory", "resource", "skill"],
                    "description": "Filter by context type",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results",
                    "default": 20,
                },
                "offset": {
                    "type": "integer",
                    "description": "Offset for pagination",
                    "default": 0,
                },
            },
        },
    },
    {
        "name": "memory_stats",
        "description": "Get statistics about stored memories",
        "input_schema": {
            "type": "object",
            "properties": {
                "tenant_id": {
                    "type": "string",
                    "description": "Tenant ID for multi-tenancy",
                },
            },
        },
    },
]


def get_tool_by_name(name: str) -> dict | None:
    """Get a tool definition by name."""
    for tool in TOOL_DEFINITIONS:
        if tool["name"] == name:
            return tool
    return None


def validate_tool_input(tool_name: str, input_data: dict) -> tuple[bool, str | None]:
    """
    Validate input data against tool schema.

    Returns (is_valid, error_message).
    """
    tool = get_tool_by_name(tool_name)
    if not tool:
        return False, f"Unknown tool: {tool_name}"

    schema = tool["input_schema"]
    required = schema.get("required", [])

    # Check required fields
    for field in required:
        if field not in input_data:
            return False, f"Missing required field: {field}"

    # Type checking (basic)
    properties = schema.get("properties", {})
    for field, value in input_data.items():
        if field in properties:
            expected_type = properties[field].get("type")
            if expected_type:
                # Handle enum specially
                if "enum" in properties[field]:
                    if value not in properties[field]["enum"]:
                        return False, f"Invalid value for {field}: {value}"
                # Basic type check
                elif expected_type == "string" and not isinstance(value, str):
                    return False, f"Expected string for {field}"
                elif expected_type == "integer" and not isinstance(value, int):
                    return False, f"Expected integer for {field}"
                elif expected_type == "array" and not isinstance(value, list):
                    return False, f"Expected array for {field}"
                elif expected_type == "object" and not isinstance(value, dict):
                    return False, f"Expected object for {field}"

    return True, None
