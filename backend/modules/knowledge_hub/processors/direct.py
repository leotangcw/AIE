"""直接检索处理器"""

import time
from typing import Optional
from loguru import logger

from .base import BaseProcessor, KnowledgeResult


class DirectProcessor(BaseProcessor):
    """直接检索模式 - 快速返回原始结果"""

    def __init__(self, config, retrievers=None):
        super().__init__(config)
        self.retrievers = retrievers or {}

    async def process(self, query: str, chunks: list = None) -> KnowledgeResult:
        """直接检索处理"""
        start_time = time.time()

        # 如果没有传入chunks，需要从检索器获取
        if chunks is None:
            chunks = await self._retrieve_chunks(query)

        # 格式化输出
        content = self._format_chunks(chunks)

        processing_time = time.time() - start_time

        return KnowledgeResult(
            content=content,
            sources=[{"content": c.get("content", ""), "source": c.get("source", "")} for c in chunks],
            mode="direct",
            processing_time=processing_time,
            llm_used=False
        )

    async def _retrieve_chunks(self, query: str) -> list:
        """检索知识块"""
        results = []
        for name, retriever in self.retrievers.items():
            try:
                if hasattr(retriever, 'retrieve'):
                    chunks = await retriever.retrieve(query)
                    results.extend(chunks)
            except Exception as e:
                logger.warning(f"Retriever {name} failed: {e}")
        return results[:self.config.get("top_k", 10)]

    def _format_chunks(self, chunks: list) -> str:
        """格式化知识块"""
        if not chunks:
            return ""

        formatted = []
        for i, chunk in enumerate(chunks, 1):
            content = chunk.get("content", "")
            source = chunk.get("source", "unknown")
            formatted.append(f"【知识 {i} 来源: {source}】\n{content}")

        return "\n\n".join(formatted)
