"""知识检索增强处理器

将 GraphRAG 集成到 knowledge_hub，提供知识图谱增强的检索能力。
"""

import time
from typing import Any, Optional
from loguru import logger

from ..core import GraphRAGClient, get_graph_rag
from ..config import QueryResult


class GraphEnhancedProcessor:
    """基于知识图谱的增强检索处理器

    将 GraphRAG 集成到 knowledge_hub，提供：
    - 实体关系抽取
    - 多跳推理检索
    - 混合检索模式

    Example:
        ```python
        processor = GraphEnhancedProcessor(config, hub)

        # 处理查询
        result = await processor.process("项目的主要功能是什么？")
        ```
    """

    def __init__(self, config: dict[str, Any], hub: Any):
        """初始化处理器

        Args:
            config: 配置字典
            hub: KnowledgeHub 实例
        """
        self.config = config
        self.hub = hub
        self._client: GraphRAGClient | None = None

        # 从配置获取参数
        graph_config = config.get("graph_rag", {})
        self.enabled = graph_config.get("enabled", True)
        self.default_mode = graph_config.get("default_mode", "hybrid")
        self.top_k = graph_config.get("top_k", 10)

    async def _get_client(self) -> GraphRAGClient | None:
        """获取 GraphRAG 客户端"""
        if not self.enabled:
            return None

        if self._client is None:
            try:
                self._client = await get_graph_rag(
                    namespace="knowledge_hub",
                    workspace="default"
                )
            except Exception as e:
                logger.error(f"Failed to initialize GraphRAG client: {e}")
                return None

        return self._client

    async def process(
        self,
        query: str,
        mode: str | None = None,
        top_k: int | None = None,
        **options,
    ) -> dict[str, Any]:
        """处理查询

        Args:
            query: 查询文本
            mode: 检索模式
            top_k: 返回结果数
            **options: 其他选项

        Returns:
            处理结果
        """
        start_time = time.time()

        result = {
            "content": "",
            "sources": [],
            "mode": mode or self.default_mode,
            "processing_time": 0.0,
            "graph_enhanced": False,
        }

        client = await self._get_client()

        if client is None:
            # GraphRAG 不可用，返回空结果
            result["error"] = "GraphRAG not available"
            result["processing_time"] = time.time() - start_time
            return result

        try:
            # 执行查询
            query_result = await client.query(
                query,
                mode=mode or self.default_mode,
                top_k=top_k or self.top_k,
                only_need_context=False,
            )

            result["content"] = query_result.content
            result["graph_enhanced"] = True

            # 提取来源信息
            if query_result.chunks:
                for chunk in query_result.chunks:
                    result["sources"].append({
                        "content": chunk.get("content", ""),
                        "source": chunk.get("source", "knowledge_graph"),
                        "score": chunk.get("score", 0.0),
                        "type": "chunk",
                    })

            if query_result.entities:
                for entity in query_result.entities[:5]:  # 限制实体数量
                    result["sources"].append({
                        "content": entity.get("description", ""),
                        "source": entity.get("name", "unknown"),
                        "type": "entity",
                    })

            if query_result.relations:
                for relation in query_result.relations[:5]:
                    result["sources"].append({
                        "content": f"{relation.get('src_id')} -> {relation.get('tgt_id')}: {relation.get('description', '')}",
                        "source": "knowledge_graph",
                        "type": "relation",
                    })

        except Exception as e:
            logger.error(f"GraphRAG query failed: {e}")
            result["error"] = str(e)

        result["processing_time"] = time.time() - start_time
        return result

    async def index_document(
        self,
        content: str,
        source_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """索引文档到知识图谱

        Args:
            content: 文档内容
            source_id: 来源 ID
            metadata: 元数据

        Returns:
            是否成功
        """
        client = await self._get_client()

        if client is None:
            return False

        try:
            # 添加元数据标记
            if metadata:
                content = f"[来源: {source_id or 'unknown'}]\n[元数据: {metadata}]\n\n{content}"

            result = await client.insert(content)
            return result.success

        except Exception as e:
            logger.error(f"Failed to index document to GraphRAG: {e}")
            return False

    async def index_batch(
        self,
        documents: list[dict[str, Any]],
    ) -> int:
        """批量索引文档

        Args:
            documents: 文档列表，每项包含 'content' 和可选的 'source_id', 'metadata'

        Returns:
            成功索引的文档数
        """
        client = await self._get_client()

        if client is None:
            return 0

        success_count = 0

        for doc in documents:
            content = doc.get("content", "")
            source_id = doc.get("source_id")
            metadata = doc.get("metadata")

            if content:
                if await self.index_document(content, source_id, metadata):
                    success_count += 1

        return success_count

    async def get_stats(self) -> dict[str, Any]:
        """获取统计信息

        Returns:
            统计信息
        """
        client = await self._get_client()

        if client is None:
            return {
                "available": False,
                "reason": "GraphRAG not enabled or not available",
            }

        stats = await client.get_stats()
        return {
            "available": stats.available,
            "node_count": stats.node_count,
            "edge_count": stats.edge_count,
            "document_count": stats.document_count,
            "error": stats.error,
        }


class HybridRetriever:
    """混合检索器

    结合传统向量检索和知识图谱检索。
    """

    def __init__(
        self,
        vector_retriever: Any,
        graph_processor: GraphEnhancedProcessor,
        config: dict[str, Any] | None = None,
    ):
        """初始化混合检索器

        Args:
            vector_retriever: 向量检索器
            graph_processor: 图谱处理器
            config: 配置
        """
        self.vector_retriever = vector_retriever
        self.graph_processor = graph_processor
        self.config = config or {}

        # 权重配置
        self.vector_weight = self.config.get("vector_weight", 0.4)
        self.graph_weight = self.config.get("graph_weight", 0.6)

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        **options,
    ) -> dict[str, Any]:
        """执行混合检索

        Args:
            query: 查询文本
            top_k: 返回结果数

        Returns:
            检索结果
        """
        import asyncio

        start_time = time.time()

        # 并行执行两种检索
        vector_task = self._vector_search(query, top_k)
        graph_task = self._graph_search(query, top_k)

        vector_result, graph_result = await asyncio.gather(
            vector_task, graph_task, return_exceptions=True
        )

        # 合并结果
        merged = self._merge_results(
            vector_result if not isinstance(vector_result, Exception) else None,
            graph_result if not isinstance(graph_result, Exception) else None,
        )

        merged["processing_time"] = time.time() - start_time
        return merged

    async def _vector_search(self, query: str, top_k: int) -> dict[str, Any]:
        """执行向量检索"""
        if self.vector_retriever is None:
            return {"sources": [], "content": ""}

        try:
            if hasattr(self.vector_retriever, 'search'):
                results = await self.vector_retriever.search(query, top_k=top_k)
            elif hasattr(self.vector_retriever, 'retrieve'):
                results = await self.vector_retriever.retrieve(query, top_k=top_k)
            else:
                results = []

            return {
                "sources": results,
                "content": self._format_sources(results),
            }
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return {"sources": [], "content": "", "error": str(e)}

    async def _graph_search(self, query: str, top_k: int) -> dict[str, Any]:
        """执行图谱检索"""
        return await self.graph_processor.process(query, top_k=top_k)

    def _merge_results(
        self,
        vector_result: dict[str, Any] | None,
        graph_result: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """合并检索结果"""
        merged = {
            "content": "",
            "sources": [],
            "mode": "hybrid",
        }

        # 合并内容
        contents = []
        if graph_result and graph_result.get("content"):
            contents.append(f"[知识图谱]\n{graph_result['content']}")
        if vector_result and vector_result.get("content"):
            contents.append(f"[向量检索]\n{vector_result['content']}")

        merged["content"] = "\n\n".join(contents) if contents else ""

        # 合并来源（去重）
        seen_sources = set()
        all_sources = []

        for source in (graph_result or {}).get("sources", []):
            key = source.get("content", "")[:100]
            if key not in seen_sources:
                seen_sources.add(key)
                source["weight"] = self.graph_weight
                all_sources.append(source)

        for source in (vector_result or {}).get("sources", []):
            key = source.get("content", "")[:100]
            if key not in seen_sources:
                seen_sources.add(key)
                source["weight"] = self.vector_weight
                all_sources.append(source)

        # 按权重排序
        all_sources.sort(key=lambda x: x.get("score", 0) * x.get("weight", 1), reverse=True)
        merged["sources"] = all_sources[:20]  # 限制数量

        return merged

    def _format_sources(self, sources: list) -> str:
        """格式化来源列表"""
        if not sources:
            return ""

        lines = []
        for i, source in enumerate(sources[:5], 1):
            content = source.get("content", "")[:200]
            score = source.get("score", 0)
            lines.append(f"{i}. [{score:.2f}] {content}...")

        return "\n".join(lines)


# 便捷函数
async def create_graph_processor(
    config: dict[str, Any],
    hub: Any,
) -> GraphEnhancedProcessor:
    """创建图谱增强处理器

    Args:
        config: 配置
        hub: KnowledgeHub 实例

    Returns:
        GraphEnhancedProcessor
    """
    processor = GraphEnhancedProcessor(config, hub)
    return processor
