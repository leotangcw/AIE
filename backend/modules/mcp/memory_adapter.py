"""Memory Adapter - 使用 MemoryPlugin 调用 MCP Server."""

from pathlib import Path
from typing import Any, Literal, Optional

from loguru import logger


class MemoryAdapter:
    """
    Memory Adapter - 通过 MemoryPlugin 获取 MCP Client 调用记忆服务.

    简化后的接口，隐藏 MCP 通信细节。
    """

    def __init__(self, plugin=None):
        """
        初始化 Memory Adapter.

        Args:
            plugin: MemoryPlugin 实例
        """
        self._plugin = plugin
        self._client = None

    def set_plugin(self, plugin) -> None:
        """设置 MemoryPlugin 实例."""
        self._plugin = plugin
        self._client = None  # 重置 client

    @property
    def client(self):
        """获取 MCP Client."""
        if self._client is None and self._plugin:
            self._client = self._plugin.get_mcp_client()
        return self._client

    @property
    def is_available(self) -> bool:
        """检查 MCP Server 是否可用."""
        return self.client is not None and self._plugin and self._plugin.is_running

    # ==================== Memory Operations ====================

    async def store(
        self,
        content: str,
        name: str,
        context_type: Literal["memory", "resource", "skill"] = "memory",
        uri: str | None = None,
        parent_uri: str | None = None,
        tags: list[str] | None = None,
        source: str = "chat",
        metadata: dict | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> dict | None:
        """存储新记忆."""
        if not self.is_available:
            logger.warning("Memory-MCP-Server not available")
            return None

        try:
            import uuid
            if uri is None:
                if session_id:
                    uri = f"viking://session/{session_id}/memories/{name.replace(' ', '_')}"
                elif user_id:
                    uri = f"viking://user/{user_id}/memories/{name.replace(' ', '_')}"
                else:
                    uri = f"viking://memory/{uuid.uuid4()}"

            args = {
                "content": content,
                "name": name,
                "context_type": context_type,
                "uri": uri,
                "tags": tags or [],
                "source": source,
                "metadata": metadata or {},
            }
            if parent_uri is not None:
                args["parent_uri"] = parent_uri

            result = await self.client.call_tool("memory_store", args)
            return result
        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            return None

    async def recall(
        self,
        query: str,
        context_type: Literal["memory", "resource", "skill", "all"] = "all",
        user_id: str | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
        limit: int = 5,
        level: int = 2,
        context: str | None = None,
    ) -> dict | None:
        """检索相关记忆."""
        if not self.is_available:
            logger.warning("Memory-MCP-Server not available")
            return None

        try:
            args = {
                "query": query,
                "context_type": context_type,
                "limit": limit,
                "level": level,
            }
            if user_id is not None:
                args["user_id"] = user_id
            if agent_id is not None:
                args["agent_id"] = agent_id
            if session_id is not None:
                args["session_id"] = session_id
            if context is not None:
                args["context"] = context

            result = await self.client.call_tool("memory_recall", args)
            return result
        except Exception as e:
            logger.error(f"Failed to recall memories: {e}")
            return None

    async def get(
        self,
        uri: str,
        level: int | None = None,
    ) -> dict | None:
        """获取指定记忆."""
        if not self.is_available:
            return None

        try:
            args = {"uri": uri}
            if level is not None:
                args["level"] = level

            return await self.client.call_tool("memory_get", args)
        except Exception as e:
            logger.error(f"Failed to get memory: {e}")
            return None

    async def update(
        self,
        uri: str,
        content: str | None = None,
        name: str | None = None,
        tags: list[str] | None = None,
        metadata: dict | None = None,
    ) -> dict | None:
        """更新记忆."""
        if not self.is_available:
            return None

        try:
            args = {"uri": uri}
            if content is not None:
                args["content"] = content
            if name is not None:
                args["name"] = name
            if tags is not None:
                args["tags"] = tags
            if metadata is not None:
                args["metadata"] = metadata

            return await self.client.call_tool("memory_update", args)
        except Exception as e:
            logger.error(f"Failed to update memory: {e}")
            return None

    async def delete(self, uri: str) -> bool:
        """删除记忆."""
        if not self.is_available:
            return False

        try:
            result = await self.client.call_tool("memory_delete", {"uri": uri})
            return result.get("deleted", False) if result else False
        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
            return False

    async def list_memories(
        self,
        uri_prefix: str | None = None,
        context_type: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        """列出记忆."""
        if not self.is_available:
            return []

        try:
            args = {
                "limit": limit,
                "offset": offset,
            }
            if uri_prefix is not None:
                args["uri_prefix"] = uri_prefix
            if context_type is not None:
                args["context_type"] = context_type

            result = await self.client.call_tool("memory_list", args)
            return result.get("memories", []) if result else []
        except Exception as e:
            logger.error(f"Failed to list memories: {e}")
            return []

    async def stats(self) -> dict | None:
        """获取统计信息."""
        if not self.is_available:
            return None

        try:
            return await self.client.call_tool("memory_stats", {})
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return None

    # ==================== Convenience Methods ====================

    def format_memories_for_context(
        self,
        recall_result: dict,
        max_items: int = 3,
    ) -> str:
        """格式化记忆用于注入到 Agent 上下文."""
        if not recall_result or "results" not in recall_result:
            return ""

        results = recall_result["results"][:max_items]
        if not results:
            return ""

        lines = ["Relevant memories:"]
        for r in results:
            lines.append(f"- {r.get('name', 'Unknown')}: {r.get('content', '')}")

        return "\n".join(lines)


# 全局适配器实例
_memory_adapter: Optional[MemoryAdapter] = None


def get_memory_adapter() -> MemoryAdapter:
    """获取全局 MemoryAdapter 实例."""
    global _memory_adapter
    if _memory_adapter is None:
        _memory_adapter = MemoryAdapter()
    return _memory_adapter


def init_memory_adapter_with_plugin(plugin) -> MemoryAdapter:
    """用 MemoryPlugin 初始化 MemoryAdapter."""
    global _memory_adapter
    _memory_adapter = MemoryAdapter(plugin=plugin)
    return _memory_adapter
