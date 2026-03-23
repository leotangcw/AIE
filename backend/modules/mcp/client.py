"""MCP Client for communicating with MCP servers."""

import asyncio
import json
import subprocess
from typing import Any, Optional

from loguru import logger


class MCPClient:
    """
    MCP Protocol Client for communicating with MCP servers.

    Supports both stdio and HTTP modes for server communication.
    """

    def __init__(
        self,
        server_command: list[str] | None = None,
        server_url: str | None = None,
        timeout: float = 120.0,  # 2 min timeout for slow operations
    ):
        """
        Initialize MCP client.

        Args:
            server_command: Command to start MCP server (for stdio mode)
            server_url: URL of MCP server (for HTTP mode)
            timeout: Timeout for tool calls in seconds
        """
        if server_command is None and server_url is None:
            raise ValueError("Must provide either server_command or server_url")

        self.server_command = server_command
        self.server_url = server_url
        self.timeout = timeout
        self.process: subprocess.Popen | None = None
        self._request_id = 0
        self._initialized = False

    async def start(self) -> None:
        """Start the MCP server process."""
        if self.server_command is None:
            return

        self.process = subprocess.Popen(
            self.server_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            bufsize=1,  # Line buffered
        )
        logger.info(f"Started MCP server with command: {' '.join(self.server_command)}")

    async def stop(self) -> None:
        """Stop the MCP server process."""
        if self.process:
            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            except Exception as e:
                logger.warning(f"Error stopping MCP server: {e}")
            finally:
                self.process = None
                logger.info("Stopped MCP server")

    def _is_process_alive(self) -> bool:
        """Check if the subprocess is still running."""
        return self.process is not None and self.process.poll() is None

    async def _send_request(self, method: str, params: dict | None = None) -> dict:
        """Send a JSON-RPC request and get response with timeout."""
        if not self._is_process_alive():
            raise RuntimeError("MCP server process is not running")

        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {},
        }

        if self.process:
            # Stdio mode
            request_str = json.dumps(request) + "\n"
            try:
                # Use asyncio to run subprocess I/O with timeout
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: self.process.stdin.write(request_str.encode())
                )
                await loop.run_in_executor(None, self.process.stdin.flush)

                # Read response with timeout
                response_line = await asyncio.wait_for(
                    loop.run_in_executor(None, self.process.stdout.readline),
                    timeout=self.timeout
                )

                if not response_line:
                    raise RuntimeError("No response from MCP server")
                return json.loads(response_line)
            except asyncio.TimeoutError:
                raise RuntimeError(f"MCP server timeout after {self.timeout}s")
            except BrokenPipeError:
                raise RuntimeError("MCP server pipe broken")
        else:
            # HTTP mode
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.server_url}/rpc",
                    json=request,
                    timeout=self.timeout,
                )
                return response.json()

    async def initialize(self) -> dict:
        """Initialize connection with MCP server."""
        if self._initialized:
            return {"status": "already_initialized"}

        if self.process:
            result = await self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "aie", "version": "1.0.0"},
            })
            self._initialized = True
            return result
        return {"status": "http_mode"}

    async def list_tools(self) -> list[dict]:
        """List available tools from MCP server."""
        if not self._initialized:
            await self.initialize()

        result = await self._send_request("tools/list")
        if "result" in result:
            return result["result"].get("tools", [])
        return []

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict,
    ) -> Any:
        """
        Call a tool on the MCP server.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            Tool execution result
        """
        if not self._initialized:
            await self.initialize()

        if not self._is_process_alive():
            raise RuntimeError("MCP server process is not running")

        result = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })

        if "error" in result:
            raise RuntimeError(f"Tool call failed: {result['error']}")

        return result.get("result")

    async def ping(self) -> bool:
        """Ping the MCP server to check connectivity."""
        try:
            result = await self._send_request("ping")
            return "result" in result
        except Exception:
            return False


class MCPClientPool:
    """Pool of MCP clients for managing multiple server connections."""

    def __init__(self):
        self._clients: dict[str, MCPClient] = {}

    def add_client(self, name: str, client: MCPClient) -> None:
        """Add a client to the pool."""
        self._clients[name] = client

    def get_client(self, name: str) -> MCPClient | None:
        """Get a client by name."""
        return self._clients.get(name)

    def remove_client(self, name: str) -> None:
        """Remove a client from the pool."""
        if name in self._clients:
            del self._clients[name]

    async def start_all(self) -> None:
        """Start all clients in the pool."""
        for client in self._clients.values():
            await client.start()

    async def stop_all(self) -> None:
        """Stop all clients in the pool."""
        for client in self._clients.values():
            await client.stop()
