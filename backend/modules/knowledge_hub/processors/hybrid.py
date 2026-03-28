"""混合检索处理器

结合向量检索和关键词检索，使用 RRF (Reciprocal Rank Fusion) 或加权融合。
"""

import time
from loguru import logger
from typing import Optional
from collections import defaultdict

from .base import BaseProcessor, KnowledgeResult
from .direct import DirectProcessor
from .vector import VectorProcessor


class HybridProcessor(BaseProcessor):
    """混合检索模式 - 向量 + 关键词"""

    def __init__(self, config: dict, hub=None):
        super().__init__(config)
        self.config = config
        self.hub = hub

        # 子处理器
        self._vector_processor = VectorProcessor(config, hub)
        self._direct_processor = DirectProcessor(config, hub)

        # 融合参数
        self.vector_weight = config.get("vector_weight", 0.7)
        self.keyword_weight = config.get("keyword_weight", 0.3)
        self.rrf_k = config.get("rrf_k", 60)  # RRF 常数

    async def process(self, query: str, chunks: list = None, **kwargs) -> KnowledgeResult:
        """混合检索处理"""
        start_time = time.time()

        top_k = kwargs.get("top_k", self.config.get("top_k", 10))
        fusion_method = kwargs.get("fusion_method", "weighted")  # weighted 或 rrf

        if chunks is not None:
            # 如果传入了 chunks，直接格式化返回
            content = self._format_results(chunks)
            return KnowledgeResult(
                content=content,
                sources=chunks,
                mode="hybrid",
                processing_time=time.time() - start_time,
            )

        # 并行执行两种检索
        import asyncio

        vector_task = self._vector_processor.process(query, top_k=top_k * 2)
        keyword_task = self._direct_processor.process(query, top_k=top_k * 2)

        try:
            vector_result, keyword_result = await asyncio.gather(
                vector_task, keyword_task, return_exceptions=True
            )
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return KnowledgeResult(
                content="",
                sources=[],
                mode="hybrid",
                processing_time=time.time() - start_time,
            )

        # 处理异常结果
        if isinstance(vector_result, Exception):
            logger.warning(f"Vector search failed: {vector_result}")
            vector_result = KnowledgeResult(content="", sources=[], mode="vector")

        if isinstance(keyword_result, Exception):
            logger.warning(f"Keyword search failed: {keyword_result}")
            keyword_result = KnowledgeResult(content="", sources=[], mode="direct")

        # 提取结果
        vector_docs = vector_result.sources if hasattr(vector_result, "sources") else []
        keyword_docs = keyword_result.sources if hasattr(keyword_result, "sources") else []

        # 融合结果
        if fusion_method == "rrf":
            fused = self._rrf_fusion(vector_docs, keyword_docs, top_k)
        else:
            fused = self._weighted_fusion(vector_docs, keyword_docs, top_k)

        # 格式化输出
        content = self._format_results(fused)

        processing_time = time.time() - start_time

        logger.info(
            f"Hybrid search: vector={len(vector_docs)}, keyword={len(keyword_docs)}, "
            f"fused={len(fused)}, time={processing_time:.3f}s"
        )

        return KnowledgeResult(
            content=content,
            sources=fused,
            mode="hybrid",
            processing_time=processing_time,
        )

    def _weighted_fusion(
        self,
        vector_docs: list[dict],
        keyword_docs: list[dict],
        top_k: int,
    ) -> list[dict]:
        """加权融合"""
        # 使用内容前缀作为去重键
        doc_scores: dict[str, dict] = {}

        # 添加向量检索结果
        for doc in vector_docs:
            key = self._get_doc_key(doc)
            score = doc.get("score", 0.5)

            if key not in doc_scores:
                doc_scores[key] = {"doc": doc, "vector_score": 0, "keyword_score": 0}

            doc_scores[key]["vector_score"] = score

        # 添加关键词检索结果
        for doc in keyword_docs:
            key = self._get_doc_key(doc)
            score = doc.get("score", 0.5)

            if key not in doc_scores:
                doc_scores[key] = {"doc": doc, "vector_score": 0, "keyword_score": 0}

            doc_scores[key]["keyword_score"] = score

        # 计算融合分数
        for key, item in doc_scores.items():
            item["final_score"] = (
                item["vector_score"] * self.vector_weight +
                item["keyword_score"] * self.keyword_weight
            )

        # 排序
        sorted_items = sorted(
            doc_scores.values(),
            key=lambda x: x["final_score"],
            reverse=True
        )

        # 构建结果
        results = []
        for item in sorted_items[:top_k]:
            doc = item["doc"].copy()
            doc["score"] = item["final_score"]
            doc["vector_score"] = item["vector_score"]
            doc["keyword_score"] = item["keyword_score"]
            results.append(doc)

        return results

    def _rrf_fusion(
        self,
        vector_docs: list[dict],
        keyword_docs: list[dict],
        top_k: int,
    ) -> list[dict]:
        """RRF (Reciprocal Rank Fusion) 融合

        RRF score = sum(1 / (k + rank)) for each ranking
        """
        # 使用内容前缀作为去重键
        doc_scores: dict[str, dict] = {}

        # 计算向量检索的 RRF 分数
        for rank, doc in enumerate(vector_docs, 1):
            key = self._get_doc_key(doc)
            rrf_score = 1 / (self.rrf_k + rank)

            if key not in doc_scores:
                doc_scores[key] = {"doc": doc, "vector_rank": rank, "keyword_rank": float("inf")}

            doc_scores[key]["vector_rank"] = rank
            doc_scores[key]["vector_rrf"] = rrf_score

        # 计算关键词检索的 RRF 分数
        for rank, doc in enumerate(keyword_docs, 1):
            key = self._get_doc_key(doc)
            rrf_score = 1 / (self.rrf_k + rank)

            if key not in doc_scores:
                doc_scores[key] = {"doc": doc, "vector_rank": float("inf"), "keyword_rank": rank}

            doc_scores[key]["keyword_rank"] = rank
            doc_scores[key]["keyword_rrf"] = rrf_score

        # 计算总 RRF 分数
        for key, item in doc_scores.items():
            vector_rrf = item.get("vector_rrf", 0)
            keyword_rrf = item.get("keyword_rrf", 0)
            item["final_score"] = vector_rrf + keyword_rrf

        # 排序
        sorted_items = sorted(
            doc_scores.values(),
            key=lambda x: x["final_score"],
            reverse=True
        )

        # 构建结果
        results = []
        for item in sorted_items[:top_k]:
            doc = item["doc"].copy()
            doc["score"] = item["final_score"]
            doc["vector_rank"] = item.get("vector_rank", float("inf"))
            doc["keyword_rank"] = item.get("keyword_rank", float("inf"))
            results.append(doc)

        return results

    def _get_doc_key(self, doc: dict) -> str:
        """获取文档去重键"""
        content = doc.get("content", "")
        source = doc.get("source", "")
        # 使用内容前 100 字符 + source 作为键
        return f"{source}:{content[:100]}"

    def _format_results(self, results: list[dict]) -> str:
        """格式化检索结果"""
        if not results:
            return ""

        formatted = []
        for i, r in enumerate(results, 1):
            content = r.get("content", "")
            source = r.get("source", "unknown")
            score = r.get("score", 0)

            # 显示详细的分数信息
            score_info = f"相关度: {score:.3f}"
            if "vector_score" in r and "keyword_score" in r:
                score_info += f" (向量: {r['vector_score']:.3f}, 关键词: {r['keyword_score']:.3f})"

            formatted.append(
                f"【结果 {i}】{score_info} 来源: {source}\n{content}"
            )

        return "\n\n".join(formatted)
