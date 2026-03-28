"""向量检索处理器

纯向量检索模式，使用语义相似度进行检索。
"""

import time
from loguru import logger
from typing import Optional

from .base import BaseProcessor, KnowledgeResult


class VectorProcessor(BaseProcessor):
    """向量检索模式 - 语义相似度检索"""

    def __init__(self, config: dict, hub=None):
        super().__init__(config)
        self.config = config
        self.hub = hub
        self._vector_store = None

    @property
    def vector_store(self):
        """延迟获取向量存储"""
        if self._vector_store is None and self.hub:
            self._vector_store = self.hub.vector_store
        return self._vector_store

    async def process(self, query: str, chunks: list = None, **kwargs) -> KnowledgeResult:
        """向量检索处理"""
        start_time = time.time()

        top_k = kwargs.get("top_k", self.config.get("top_k", 10))
        min_score = kwargs.get("min_score", self.config.get("min_score", 0.3))

        # 如果传入了 chunks，直接使用
        if chunks is not None:
            results = chunks
        else:
            # 执行向量检索
            results = await self._vector_search(query, top_k, min_score)

        if not results:
            return KnowledgeResult(
                content="",
                sources=[],
                mode="vector",
                processing_time=time.time() - start_time,
            )

        # 格式化输出
        content = self._format_results(results)
        sources = [
            {
                "content": r.get("content", "")[:500],  # 截断过长的内容
                "source": r.get("source", "unknown"),
                "score": r.get("score", 0),
            }
            for r in results
        ]

        processing_time = time.time() - start_time

        logger.info(f"Vector search: {len(results)} results in {processing_time:.3f}s")

        return KnowledgeResult(
            content=content,
            sources=sources,
            mode="vector",
            processing_time=processing_time,
        )

    async def _vector_search(self, query: str, top_k: int, min_score: float) -> list[dict]:
        """执行向量检索"""
        if not self.vector_store:
            logger.warning("Vector store not available")
            return []

        try:
            # 调用向量存储的搜索方法
            results = self.vector_store.search(query, top_k=top_k)

            # 过滤低分结果
            filtered = [r for r in results if r.get("score", 0) >= min_score]

            logger.debug(f"Vector search: {len(filtered)}/{len(results)} results passed threshold {min_score}")

            return filtered

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    def _format_results(self, results: list[dict]) -> str:
        """格式化检索结果"""
        if not results:
            return ""

        formatted = []
        for i, r in enumerate(results, 1):
            content = r.get("content", "")
            source = r.get("source", "unknown")
            score = r.get("score", 0)

            formatted.append(
                f"【结果 {i}】相关度: {score:.2f} 来源: {source}\n{content}"
            )

        return "\n\n".join(formatted)

    async def add_to_index(self, documents: list[dict]) -> int:
        """将文档添加到向量索引"""
        if not self.vector_store:
            logger.warning("Vector store not available")
            return 0

        count = 0
        for doc in documents:
            try:
                content = doc.get("content", "")
                if not content:
                    continue

                metadata = doc.get("metadata", {})
                source_type = doc.get("source_type", "knowledge")
                source_id = doc.get("source_id", doc.get("source", ""))

                self.vector_store.add(
                    content=content,
                    metadata=metadata,
                    source_type=source_type,
                    source_id=source_id,
                )
                count += 1

            except Exception as e:
                logger.warning(f"Failed to add document to index: {e}")

        logger.info(f"Added {count} documents to vector index")
        return count

    async def remove_from_index(self, source_id: str) -> int:
        """从向量索引中删除文档"""
        if not self.vector_store:
            return 0

        try:
            count = self.vector_store.delete_by_source_id(source_id)
            logger.info(f"Removed {count} documents from vector index for source {source_id}")
            return count
        except Exception as e:
            logger.error(f"Failed to remove documents from index: {e}")
            return 0
