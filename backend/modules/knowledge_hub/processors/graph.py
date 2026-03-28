"""知识图谱处理器

基于 GraphRAG 的知识检索处理器。
"""

import time
from typing import Any, Optional

from loguru import logger

from .base import BaseProcessor, KnowledgeResult


class GraphProcessor(BaseProcessor):
    """知识图谱检索处理器

    使用 GraphRAG 进行基于知识图谱的检索，
    支持多跳推理和实体关系查询。
    """

    def __init__(self, config: dict, hub: Any):
        super().__init__(config)
        self.hub = hub
        self._client = None

        # GraphRAG 配置
        graph_config = config.get("graph_rag", {})
        self.enabled = graph_config.get("enabled", True)
        self.default_mode = graph_config.get("default_mode", "hybrid")
        self.top_k = graph_config.get("top_k", 10)
        self.namespace = graph_config.get("namespace", "knowledge_hub")

    async def _get_client(self):
        """获取 GraphRAG 客户端"""
        if self._client is not None:
            return self._client

        if not self.enabled:
            return None

        try:
            from backend.modules.graph_rag import get_graph_rag

            self._client = await get_graph_rag(
                namespace=self.namespace,
                workspace="knowledge_hub",
            )
            return self._client

        except Exception as e:
            logger.error(f"Failed to initialize GraphRAG client: {e}")
            return None

    async def process(
        self,
        query: str,
        chunks: list = None,
        mode: str = None,
        top_k: int = None,
        **kwargs,
    ) -> KnowledgeResult:
        """处理知识检索

        Args:
            query: 查询文本
            chunks: 可用的文档块（可选，用于混合模式）
            mode: 查询模式 (local/global/hybrid/naive/mix)
            top_k: 返回结果数量

        Returns:
            KnowledgeResult: 检索结果
        """
        start_time = time.time()

        client = await self._get_client()

        if client is None:
            return KnowledgeResult(
                content="GraphRAG 不可用",
                sources=[],
                mode="graph",
                processing_time=time.time() - start_time,
            )

        try:
            # 执行查询
            result = await client.query(
                query=query,
                mode=mode or self.default_mode,
                top_k=top_k or self.top_k,
            )

            # 构建来源列表
            sources = []

            # 添加相关文档块
            if hasattr(result, "chunks") and result.chunks:
                for chunk in result.chunks:
                    sources.append({
                        "content": chunk.get("content", ""),
                        "source": chunk.get("source", "knowledge_graph"),
                        "score": chunk.get("score", 0.0),
                        "type": "chunk",
                    })

            # 添加相关实体
            if hasattr(result, "entities") and result.entities:
                for entity in result.entities[:5]:  # 限制数量
                    sources.append({
                        "content": entity.get("description", ""),
                        "source": entity.get("name", "unknown"),
                        "type": "entity",
                    })

            # 添加相关关系
            if hasattr(result, "relations") and result.relations:
                for relation in result.relations[:5]:
                    sources.append({
                        "content": f"{relation.get('src_id')} -> {relation.get('tgt_id')}: {relation.get('description', '')}",
                        "source": "knowledge_graph",
                        "type": "relation",
                    })

            return KnowledgeResult(
                content=result.content if hasattr(result, "content") else str(result),
                sources=sources,
                mode="graph",
                processing_time=time.time() - start_time,
                llm_used=True,  # GraphRAG 使用 LLM
            )

        except Exception as e:
            logger.error(f"GraphProcessor failed: {e}")
            return KnowledgeResult(
                content=f"知识图谱检索失败: {str(e)}",
                sources=[],
                mode="graph",
                processing_time=time.time() - start_time,
            )

    async def index_document(
        self,
        content: str,
        source_id: str = None,
        metadata: dict = None,
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
        documents: list[dict],
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

    async def get_stats(self) -> dict:
        """获取统计信息"""
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
