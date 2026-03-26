"""GraphRAG Agent 工具

提供 Agent 可调用的知识图谱工具：
- graph_rag_index: 索引文档到知识图谱
- graph_rag_query: 查询知识图谱
- graph_rag_stats: 获取统计信息
"""

from typing import Any, Literal, Optional

from loguru import logger

from backend.modules.tools.base import Tool
from .core import GraphRAGClient, get_graph_rag, LIGHTERAG_AVAILABLE
from .config import QueryResult, InsertResult


class GraphRAGIndexTool(Tool):
    """知识图谱索引工具

    将文档内容索引到知识图谱，支持后续智能检索。
    自动从文档中抽取实体和关系。

    Example:
        User: "请帮我索引这份文档到知识库"
        Agent: [调用 graph_rag_index 工具]
    """

    @property
    def name(self) -> str:
        return "graph_rag_index"

    @property
    def description(self) -> str:
        return """将文档内容索引到知识图谱，支持后续智能检索。

自动从文档中抽取实体（人物、组织、地点、事件等）和关系，
构建结构化的知识图谱。

适用场景：
- 存储需要长期记忆的文档
- 构建知识库供后续查询
- 保存结构化信息以便推理

注意：索引过程需要调用 LLM 进行实体抽取，可能较慢。
"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "要索引的文档内容",
                },
                "namespace": {
                    "type": "string",
                    "description": "知识库命名空间，用于隔离不同知识库。默认为 'default'",
                    "default": "default",
                },
                "doc_type": {
                    "type": "string",
                    "description": "文档类型：document(普通文档)/conversation(对话)/code(代码)",
                    "default": "document",
                    "enum": ["document", "conversation", "code"],
                },
                "file_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "文件路径列表（用于引用来源）",
                },
            },
            "required": ["content"],
        }

    async def execute(
        self,
        content: str,
        namespace: str = "default",
        doc_type: str = "document",
        file_paths: list[str] | None = None,
    ) -> str:
        """执行索引操作"""
        if not LIGHTERAG_AVAILABLE:
            return "Error: LightRAG not installed. Install with: pip install lightrag-hku"

        try:
            client = await get_graph_rag(namespace=namespace)
            result: InsertResult = await client.insert(
                content=content,
                file_paths=file_paths,
                doc_type=doc_type,
            )

            if result.success:
                return (
                    f"Successfully indexed document to namespace '{namespace}'. "
                    f"Document count: {result.document_count}, "
                    f"Processing time: {result.processing_time:.2f}s"
                )
            else:
                return f"Failed to index document: {result.error}"

        except Exception as e:
            logger.error(f"GraphRAG index tool failed: {e}")
            return f"Error: {str(e)}"


class GraphRAGQueryTool(Tool):
    """知识图谱查询工具

    从知识图谱中检索相关信息，支持多种查询模式。

    Example:
        User: "根据知识库，项目的架构是什么？"
        Agent: [调用 graph_rag_query 工具]
    """

    @property
    def name(self) -> str:
        return "graph_rag_query"

    @property
    def description(self) -> str:
        return """从知识图谱中检索相关信息，支持多种查询模式。

查询模式说明：
- local: 基于实体的局部检索，适合具体事实查询（如"张三的职位是什么？"）
- global: 基于社区的全局检索，适合概括性问题（如"项目整体架构是什么？"）
- hybrid: 混合 local + global，平衡型查询（推荐）
- naive: 纯向量检索，适合简单相似度搜索
- mix: KG + 向量 + 重排序，最高质量（较慢）

返回内容为基于知识图谱的智能回答。
"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "查询问题",
                },
                "namespace": {
                    "type": "string",
                    "description": "知识库命名空间",
                    "default": "default",
                },
                "mode": {
                    "type": "string",
                    "description": "查询模式",
                    "default": "hybrid",
                    "enum": ["local", "global", "hybrid", "naive", "mix"],
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回结果数量",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 100,
                },
                "only_need_context": {
                    "type": "boolean",
                    "description": "仅返回上下文，不生成回答",
                    "default": False,
                },
            },
            "required": ["query"],
        }

    async def execute(
        self,
        query: str,
        namespace: str = "default",
        mode: Literal["local", "global", "hybrid", "naive", "mix"] = "hybrid",
        top_k: int = 10,
        only_need_context: bool = False,
    ) -> str:
        """执行查询操作"""
        if not LIGHTERAG_AVAILABLE:
            return "Error: LightRAG not installed. Install with: pip install lightrag-hku"

        try:
            client = await get_graph_rag(namespace=namespace)
            result: QueryResult = await client.query(
                query=query,
                mode=mode,
                top_k=top_k,
                only_need_context=only_need_context,
            )

            if result.error:
                return f"Query error: {result.error}"

            if only_need_context:
                return result.context or "No context found"

            return result.content

        except Exception as e:
            logger.error(f"GraphRAG query tool failed: {e}")
            return f"Error: {str(e)}"


class GraphRAGStatsTool(Tool):
    """知识图谱统计工具

    获取知识图谱的统计信息。
    """

    @property
    def name(self) -> str:
        return "graph_rag_stats"

    @property
    def description(self) -> str:
        return """获取知识图谱的统计信息。

返回节点数量、边数量、文档数量等统计信息。
"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "知识库命名空间",
                    "default": "default",
                },
            },
            "required": [],
        }

    async def execute(self, namespace: str = "default") -> str:
        """执行统计查询"""
        if not LIGHTERAG_AVAILABLE:
            return "Error: LightRAG not installed. Install with: pip install lightrag-hku"

        try:
            client = await get_graph_rag(namespace=namespace)
            stats = await client.get_stats()

            if stats.error:
                return f"Stats error: {stats.error}"

            return (
                f"Knowledge Graph Stats for '{namespace}':\n"
                f"- Available: {stats.available}\n"
                f"- Nodes: {stats.node_count}\n"
                f"- Edges: {stats.edge_count}\n"
                f"- Documents: {stats.document_count}"
            )

        except Exception as e:
            logger.error(f"GraphRAG stats tool failed: {e}")
            return f"Error: {str(e)}"


class GraphRAGClearTool(Tool):
    """知识图谱清空工具

    清空指定命名空间的知识图谱数据。
    """

    @property
    def name(self) -> str:
        return "graph_rag_clear"

    @property
    def description(self) -> str:
        return """清空指定命名空间的知识图谱数据。

警告：此操作将删除所有数据，不可恢复！
仅在用户明确要求清空知识库时使用。
"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "要清空的命名空间",
                    "default": "default",
                },
                "confirm": {
                    "type": "boolean",
                    "description": "确认清空（必须为 true）",
                },
            },
            "required": ["confirm"],
        }

    async def execute(self, namespace: str = "default", confirm: bool = False) -> str:
        """执行清空操作"""
        if not LIGHTERAG_AVAILABLE:
            return "Error: LightRAG not installed. Install with: pip install lightrag-hku"

        if not confirm:
            return "Error: Clear operation requires confirm=true"

        try:
            client = await get_graph_rag(namespace=namespace)
            success = await client.clear()

            if success:
                # 清除缓存的实例
                GraphRAGClient.clear_instance(namespace)
                return f"Successfully cleared namespace '{namespace}'"
            else:
                return f"Failed to clear namespace '{namespace}'"

        except Exception as e:
            logger.error(f"GraphRAG clear tool failed: {e}")
            return f"Error: {str(e)}"


# Tool registration function
def register_graph_rag_tools(registry) -> None:
    """注册 GraphRAG 工具到 ToolRegistry

    Args:
        registry: ToolRegistry 实例
    """
    if not LIGHTERAG_AVAILABLE:
        logger.debug(
            "LightRAG not installed. GraphRAG tools will not be registered. "
            "Install with: pip install lightrag-hku"
        )
        return

    tools = [
        GraphRAGIndexTool(),
        GraphRAGQueryTool(),
        GraphRAGStatsTool(),
        GraphRAGClearTool(),
    ]

    for tool in tools:
        try:
            registry.register(tool)
            logger.debug(f"Registered GraphRAG tool: {tool.name}")
        except ValueError as e:
            logger.warning(f"Failed to register tool {tool.name}: {e}")


# Export tools
__all__ = [
    "GraphRAGIndexTool",
    "GraphRAGQueryTool",
    "GraphRAGStatsTool",
    "GraphRAGClearTool",
    "register_graph_rag_tools",
]
