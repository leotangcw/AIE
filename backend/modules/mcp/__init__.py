"""MCP (Model Context Protocol) module for AIE.

提供 MCP 协议客户端和可拔插的 MCP 组件支持。
"""

from .client import MCPClient, MCPClientPool
from .memory_adapter import (
    MemoryAdapter,
    get_memory_adapter,
    init_memory_adapter_with_plugin,
)
from .memory_plugin import (
    MemoryPlugin,
    get_memory_plugin,
    init_memory_plugin,
    close_memory_plugin,
)

__all__ = [
    # Client
    "MCPClient",
    "MCPClientPool",
    # Adapter
    "MemoryAdapter",
    "get_memory_adapter",
    "init_memory_adapter_with_plugin",
    # Plugin
    "MemoryPlugin",
    "get_memory_plugin",
    "init_memory_plugin",
    "close_memory_plugin",
]
