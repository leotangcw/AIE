"""Vector Memory Tools - Integration with Memory-MCP-Server.

These tools provide hierarchical L0/L1/L2 memory capabilities to agents
via the Memory-MCP-Server MCP Protocol interface.
"""

from typing import Any

from loguru import logger

from backend.modules.mcp.memory_adapter import get_memory_adapter
from backend.modules.tools.base import Tool


class VectorMemoryStoreTool(Tool):
    """Store a memory to the vector memory system."""

    def __init__(self):
        self._channel: str | None = None

    def set_channel(self, channel: str | None) -> None:
        self._channel = channel

    @property
    def name(self) -> str:
        return "vector_memory_store"

    @property
    def description(self) -> str:
        return (
            "Store a memory to the hierarchical vector memory system. "
            "Automatically generates abstract (L0) and overview (L1) summaries. "
            "Use for: user preferences, important decisions, entity knowledge, patterns. "
            "NOT for: casual chat, test queries, one-time results."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Full content of the memory to store",
                },
                "name": {
                    "type": "string",
                    "description": "Name/title for this memory",
                },
                "context_type": {
                    "type": "string",
                    "enum": ["memory", "resource", "skill"],
                    "description": "Type of memory: memory (personal), resource (knowledge), skill (capability)",
                    "default": "memory",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags for categorization",
                },
            },
            "required": ["content", "name"],
        }

    def get_definition(self) -> dict[str, Any]:
        """Get tool definition for LLM function calling."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def execute(
        self,
        content: str,
        name: str,
        context_type: str = "memory",
        tags: list[str] | None = None,
        **kwargs,
    ) -> str:
        try:
            adapter = get_memory_adapter()
            result = await adapter.store(
                content=content,
                name=name,
                context_type=context_type,
                tags=tags or [],
                source=self._channel or "agent",
            )
            if result:
                return f"Memory stored: {name} (URI: {result.get('uri', 'N/A')})"
            else:
                return "Vector memory system not available"
        except Exception as e:
            logger.error(f"Vector memory store failed: {e}")
            return f"Failed to store memory: {e}"


class VectorMemoryRecallTool(Tool):
    """Recall relevant memories from the vector memory system."""

    def __init__(self):
        pass

    @property
    def name(self) -> str:
        return "vector_memory_recall"

    @property
    def description(self) -> str:
        return (
            "Recall relevant memories using semantic search. "
            "Uses L0/L1/L2 hierarchy for efficient retrieval. "
            "Returns memories ranked by relevance, hotness, and recency. "
            "Use for: finding related knowledge, user preferences, past decisions."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Query text to search for relevant memories",
                },
                "context_type": {
                    "type": "string",
                    "enum": ["memory", "resource", "skill", "all"],
                    "description": "Filter by memory type",
                    "default": "all",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results",
                    "default": 5,
                },
                "level": {
                    "type": "integer",
                    "enum": [0, 1, 2],
                    "description": "Content level: 0=abstract, 1=overview, 2=full",
                    "default": 1,
                },
            },
            "required": ["query"],
        }

    def get_definition(self) -> dict[str, Any]:
        """Get tool definition for LLM function calling."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def execute(
        self,
        query: str,
        context_type: str = "all",
        limit: int = 5,
        level: int = 1,
        **kwargs,
    ) -> str:
        try:
            adapter = get_memory_adapter()
            result = await adapter.recall(
                query=query,
                context_type=context_type,
                limit=limit,
                level=level,
            )
            if result is None:
                return "Vector memory system not available"

            results = result.get("results", [])
            if not results:
                return "No relevant memories found"

            lines = [f"Found {len(results)} relevant memories:"]
            for r in results:
                lines.append(f"\n- {r.get('name', 'Unknown')}")
                lines.append(f"  {r.get('content', '')}")
                lines.append(f"  [score: {r.get('final_score', 0):.2f}]")

            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Vector memory recall failed: {e}")
            return f"Failed to recall memories: {e}"


class VectorMemoryGetTool(Tool):
    """Get a specific memory by URI."""

    def __init__(self):
        pass

    @property
    def name(self) -> str:
        return "vector_memory_get"

    @property
    def description(self) -> str:
        return "Get a specific memory by its URI."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "uri": {
                    "type": "string",
                    "description": "Memory URI to retrieve",
                },
                "level": {
                    "type": "integer",
                    "enum": [0, 1, 2],
                    "description": "Content level: 0=abstract, 1=overview, 2=full",
                },
            },
            "required": ["uri"],
        }

    def get_definition(self) -> dict[str, Any]:
        """Get tool definition for LLM function calling."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def execute(self, uri: str, level: int | None = None, **kwargs) -> str:
        try:
            adapter = get_memory_adapter()
            result = await adapter.get(uri=uri, level=level)
            if result:
                return f"{result.get('name', 'Unknown')}\n\n{result.get('content', '')}"
            return "Memory not found"
        except Exception as e:
            logger.error(f"Vector memory get failed: {e}")
            return f"Failed to get memory: {e}"


class VectorMemoryStatsTool(Tool):
    """Get statistics about the vector memory system."""

    def __init__(self):
        pass

    @property
    def name(self) -> str:
        return "vector_memory_stats"

    @property
    def description(self) -> str:
        return "Get statistics about the vector memory store."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    def get_definition(self) -> dict[str, Any]:
        """Get tool definition for LLM function calling."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def execute(self, **kwargs) -> str:
        try:
            adapter = get_memory_adapter()
            result = await adapter.stats()
            if result:
                lines = ["Vector Memory Statistics:"]
                lines.append(f"Total memories: {result.get('total_memories', 0)}")
                lines.append(f"Total vectors: {result.get('total_vectors', 0)}")
                by_type = result.get("by_context_type", {})
                if by_type:
                    lines.append(f"By type: {by_type}")
                by_level = result.get("by_level", {})
                if by_level:
                    lines.append(f"By level: {by_level}")
                return "\n".join(lines)
            return "Vector memory system not available"
        except Exception as e:
            logger.error(f"Vector memory stats failed: {e}")
            return f"Failed to get stats: {e}"


def get_vector_memory_tools() -> list:
    """Get all vector memory tools."""
    return [
        VectorMemoryStoreTool(),
        VectorMemoryRecallTool(),
        VectorMemoryGetTool(),
        VectorMemoryStatsTool(),
    ]
