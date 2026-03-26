"""会话知识图谱

基于 GraphRAG 构建会话级别的知识图谱，用于：
- 从对话历史中抽取关键实体和关系
- 支持上下文感知的对话
- 多轮对话知识积累
"""

from datetime import datetime
from typing import Any, Optional
from loguru import logger

from ..core import GraphRAGClient, get_graph_rag
from ..config import QueryResult


class SessionKnowledgeGraph:
    """会话级知识图谱

    为每个会话维护一个独立的知识图谱，用于：
    - 存储对话中提到的关键信息
    - 支持基于上下文的智能检索
    - 多轮对话中的信息关联

    Example:
        ```python
        session_kg = SessionKnowledgeGraph(session_id="session_123")

        # 添加对话
        await session_kg.add_exchange(
            user_msg="我想开发一个 AI 助手项目",
            assistant_msg="好的，我来帮你规划..."
        )

        # 获取相关上下文
        context = await session_kg.get_context_for_query("项目开发")
        ```
    """

    def __init__(
        self,
        session_id: str,
        user_id: str | None = None,
    ):
        """初始化会话知识图谱

        Args:
            session_id: 会话 ID
            user_id: 用户 ID（可选，用于关联用户画像）
        """
        self.session_id = session_id
        self.user_id = user_id

        self._client: GraphRAGClient | None = None
        self._exchange_count = 0

    async def _get_client(self) -> GraphRAGClient:
        """获取 GraphRAG 客户端"""
        if self._client is None:
            self._client = await get_graph_rag(
                namespace=self.session_id,
                workspace="sessions"
            )
        return self._client

    async def add_exchange(
        self,
        user_msg: str,
        assistant_msg: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """添加对话交换到知识图谱

        Args:
            user_msg: 用户消息
            assistant_msg: 助手消息
            metadata: 元数据

        Returns:
            是否成功
        """
        try:
            client = await self._get_client()

            # 构建对话内容
            timestamp = datetime.now().isoformat()
            content = f"""[时间: {timestamp}]
用户: {user_msg}
助手: {assistant_msg}
"""
            if metadata:
                content += f"[元数据: {metadata}]\n"

            # 插入到图谱
            result = await client.insert(
                content,
                file_paths=[f"exchange_{self._exchange_count}"]
            )

            if result.success:
                self._exchange_count += 1

            return result.success

        except Exception as e:
            logger.error(f"Failed to add exchange to session KG: {e}")
            return False

    async def add_context(
        self,
        context: str,
        context_type: str = "background",
    ) -> bool:
        """添加背景上下文

        Args:
            context: 上下文内容
            context_type: 上下文类型

        Returns:
            是否成功
        """
        try:
            client = await self._get_client()

            content = f"[背景信息: {context_type}]\n{context}"

            result = await client.insert(content)
            return result.success

        except Exception as e:
            logger.error(f"Failed to add context to session KG: {e}")
            return False

    async def get_context_for_query(
        self,
        query: str,
        max_tokens: int = 4000,
    ) -> str:
        """获取与查询相关的会话上下文

        Args:
            query: 当前查询
            max_tokens: 最大 Token 数

        Returns:
            相关上下文
        """
        try:
            client = await self._get_client()

            result = await client.query(
                query,
                mode="local",
                only_need_context=True,
            )

            return result.context or ""

        except Exception as e:
            logger.error(f"Failed to get session context: {e}")
            return ""

    async def get_related_entities(
        self,
        entity_hint: str,
    ) -> list[dict]:
        """获取相关实体

        Args:
            entity_hint: 实体提示

        Returns:
            相关实体列表
        """
        try:
            client = await self._get_client()

            result = await client.query(
                f"与 {entity_hint} 相关的内容和信息",
                mode="local",
                only_need_context=True,
            )

            # 返回上下文中的实体信息
            if result.entities:
                return result.entities

            return []

        except Exception as e:
            logger.error(f"Failed to get related entities: {e}")
            return []

    async def get_session_summary(self) -> str:
        """获取会话摘要

        Returns:
            会话摘要
        """
        try:
            client = await self._get_client()

            result = await client.query(
                "请总结本次对话的主要内容、讨论的话题和达成的结论。",
                mode="global",
            )

            return result.content

        except Exception as e:
            logger.error(f"Failed to get session summary: {e}")
            return ""

    async def get_key_points(self) -> list[str]:
        """获取对话关键点

        Returns:
            关键点列表
        """
        try:
            client = await self._get_client()

            result = await client.query(
                "本次对话中讨论的关键点有哪些？请逐一列出。",
                mode="hybrid",
            )

            # 解析列表
            points = []
            for line in result.content.split("\n"):
                line = line.strip()
                if line.startswith("- ") or line.startswith("* "):
                    points.append(line[2:].strip())
                elif line and line[0].isdigit() and ". " in line:
                    points.append(line.split(". ", 1)[1].strip())

            return [p for p in points if p]

        except Exception as e:
            logger.error(f"Failed to get key points: {e}")
            return []

    async def query(
        self,
        query: str,
        mode: str = "hybrid",
    ) -> QueryResult:
        """通用查询

        Args:
            query: 查询问题
            mode: 查询模式

        Returns:
            QueryResult
        """
        client = await self._get_client()
        return await client.query(query, mode=mode)

    async def clear(self) -> bool:
        """清空会话知识图谱

        Returns:
            是否成功
        """
        client = await self._get_client()
        return await client.clear()

    async def get_stats(self) -> dict[str, Any]:
        """获取会话统计

        Returns:
            统计信息
        """
        client = await self._get_client()
        stats = await client.get_stats()

        return {
            "session_id": self.session_id,
            "exchange_count": self._exchange_count,
            "graph_stats": stats.model_dump(),
        }


# 便捷函数
async def get_session_kg(session_id: str) -> SessionKnowledgeGraph:
    """获取会话知识图谱

    Args:
        session_id: 会话 ID

    Returns:
        SessionKnowledgeGraph
    """
    return SessionKnowledgeGraph(session_id)


async def add_session_exchange(
    session_id: str,
    user_msg: str,
    assistant_msg: str,
) -> bool:
    """添加会话交换

    Args:
        session_id: 会话 ID
        user_msg: 用户消息
        assistant_msg: 助手消息

    Returns:
        是否成功
    """
    kg = SessionKnowledgeGraph(session_id)
    return await kg.add_exchange(user_msg, assistant_msg)


async def get_session_context(session_id: str, query: str) -> str:
    """获取会话上下文

    Args:
        session_id: 会话 ID
        query: 查询

    Returns:
        上下文
    """
    kg = SessionKnowledgeGraph(session_id)
    return await kg.get_context_for_query(query)
