"""MCP Protocol Server implementation."""

import json
import sys
from typing import Any, AsyncGenerator

from loguru import logger

from ..models.memory import MemoryUpdate
from ..service.memory_service import MemoryService
from .tools import TOOL_DEFINITIONS, validate_tool_input


class MCPServer:
    """
    MCP Protocol Server for memory operations.

    Implements JSON-RPC 2.0 over stdio for local communication.
    """

    def __init__(self, memory_service: MemoryService):
        self.service = memory_service
        self._request_id = 0

    async def handle_request(self, request: dict) -> dict:
        """Handle a JSON-RPC 2.0 request."""
        method = request.get("method")
        request_id = request.get("id")

        # Handle methods
        if method == "initialize":
            return self._handle_initialize(request_id)

        elif method == "tools/list":
            return self._handle_tools_list(request_id)

        elif method == "tools/call":
            return await self._handle_tools_call(request_id, request.get("params", {}))

        elif method == "ping":
            return self._handle_pong(request_id)

        else:
            return self._error_response(
                request_id,
                -32601,
                f"Method not found: {method}",
            )

    def _handle_initialize(self, request_id: Any) -> dict:
        """Handle initialize request."""
        return self._success_response(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False},
                },
                "serverInfo": {
                    "name": "memory-mcp-server",
                    "version": "0.1.0",
                },
            },
        )

    def _handle_pong(self, request_id: Any) -> dict:
        """Handle ping request."""
        return self._success_response(request_id, {"status": "pong"})

    def _handle_tools_list(self, request_id: Any) -> dict:
        """Handle tools/list request."""
        return self._success_response(request_id, {"tools": TOOL_DEFINITIONS})

    async def _handle_tools_call(self, request_id: Any, params: dict) -> dict:
        """Handle tools/call request."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        # Validate tool exists
        from .tools import get_tool_by_name
        tool = get_tool_by_name(tool_name)
        if not tool:
            return self._error_response(request_id, -32601, f"Unknown tool: {tool_name}")

        # Validate input
        is_valid, error = validate_tool_input(tool_name, arguments)
        if not is_valid:
            return self._error_response(request_id, -32602, f"Invalid input: {error}")

        # Execute tool
        try:
            result = await self._execute_tool(tool_name, arguments)
            return self._success_response(request_id, result)
        except Exception as e:
            logger.exception(f"Tool execution failed: {tool_name}")
            return self._error_response(request_id, -32603, f"Execution error: {str(e)}")

    async def _execute_tool(self, tool_name: str, arguments: dict) -> Any:
        """Execute a tool and return its result."""
        if tool_name == "memory_store":
            memory = await self.service.store(
                content=arguments["content"],
                name=arguments["name"],
                context_type=arguments.get("context_type", "memory"),
                uri=arguments.get("uri"),
                parent_uri=arguments.get("parent_uri"),
                tags=arguments.get("tags"),
                source=arguments.get("source", "unknown"),
                metadata=arguments.get("metadata"),
                tenant_id=arguments.get("tenant_id"),
            )
            return {
                "id": memory.id,
                "uri": memory.uri,
                "created_at": memory.created_at.isoformat(),
            }

        elif tool_name == "memory_recall":
            result = await self.service.recall(
                query=arguments["query"],
                context_type=arguments.get("context_type", "all"),
                user_id=arguments.get("user_id"),
                agent_id=arguments.get("agent_id"),
                session_id=arguments.get("session_id"),
                limit=arguments.get("limit", 5),
                level=arguments.get("level", 2),
                tenant_id=arguments.get("tenant_id"),
                context=arguments.get("context"),
            )
            return result.to_dict()

        elif tool_name == "memory_get":
            memory = await self.service.get(
                uri=arguments["uri"],
                level=arguments.get("level"),
                tenant_id=arguments.get("tenant_id"),
            )
            if memory:
                return {
                    "id": memory.id,
                    "uri": memory.uri,
                    "name": memory.name,
                    "content": memory.format_for_context(),
                    "context_type": memory.context_type,
                    "level": memory.level,
                    "tags": memory.tags,
                    "created_at": memory.created_at.isoformat(),
                    "updated_at": memory.updated_at.isoformat(),
                }
            return None

        elif tool_name == "memory_update":
            update = MemoryUpdate(
                content=arguments.get("content"),
                name=arguments.get("name"),
                tags=arguments.get("tags"),
                metadata=arguments.get("metadata"),
            )
            memory = await self.service.update(arguments["uri"], update)
            if memory:
                return {
                    "id": memory.id,
                    "uri": memory.uri,
                    "updated_at": memory.updated_at.isoformat(),
                }
            return None

        elif tool_name == "memory_delete":
            deleted = await self.service.delete(arguments["uri"])
            return {"deleted": deleted}

        elif tool_name == "memory_list":
            memories = await self.service.list_memories(
                uri_prefix=arguments.get("uri_prefix"),
                context_type=arguments.get("context_type"),
                limit=arguments.get("limit", 20),
                offset=arguments.get("offset", 0),
            )
            return {
                "memories": [
                    {
                        "id": m.id,
                        "uri": m.uri,
                        "name": m.name,
                        "context_type": m.context_type,
                        "level": m.level,
                        "tags": m.tags,
                    }
                    for m in memories
                ],
                "count": len(memories),
            }

        elif tool_name == "memory_stats":
            stats = await self.service.stats(tenant_id=arguments.get("tenant_id"))
            return {
                "total_memories": stats.total_memories,
                "by_context_type": stats.by_context_type,
                "by_level": stats.by_level,
                "by_source": stats.by_source,
                "total_vectors": stats.total_vectors,
                "storage_size_bytes": stats.storage_size_bytes,
            }

        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    def _success_response(self, request_id: Any, result: Any) -> dict:
        """Create a success JSON-RPC response."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }

    def _error_response(self, request_id: Any, code: int, message: str) -> dict:
        """Create an error JSON-RPC response."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message,
            },
        }

    async def run_stdio(self) -> None:
        """Run the server using stdio communication."""
        await self.service.initialize()

        try:
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue

                try:
                    request = json.loads(line)
                    response = await self.handle_request(request)

                    # Send response
                    print(json.dumps(response), flush=True)

                except json.JSONDecodeError as e:
                    error_resp = self._error_response(None, -32700, f"Parse error: {e}")
                    print(json.dumps(error_resp), flush=True)

        finally:
            await self.service.close()


async def run_server(memory_service: MemoryService) -> None:
    """Run the MCP server."""
    server = MCPServer(memory_service)
    await server.run_stdio()
