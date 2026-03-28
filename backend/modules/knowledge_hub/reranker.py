"""重排序模块

多维度结果重排序，参考 Memory-MCP-Server 的实现：
- 语义相似度
- 时间新近度
- 热度评分
- 来源优先级
"""

import math
from datetime import datetime, timezone
from typing import Optional, Any
from loguru import logger
from dataclasses import dataclass, field

from .config import RerankConfig


@dataclass
class RerankResult:
    """重排序结果"""
    content: str
    source: str
    original_score: float
    final_score: float
    score_breakdown: dict[str, float]
    metadata: dict = field(default_factory=dict)


class Reranker:
    """多维度重排序器"""

    def __init__(self, config: RerankConfig | None = None):
        self.config = config or RerankConfig()

    def rerank(
        self,
        results: list[dict],
        query: str = "",
        context: dict | None = None,
    ) -> list[RerankResult]:
        """
        对检索结果进行重排序

        Args:
            results: 原始检索结果
            query: 查询文本
            context: 额外上下文（用户偏好、会话信息等）

        Returns:
            重排序后的结果列表
        """
        if not results:
            return []

        if not self.config.enabled:
            # 不启用重排序，直接返回
            return [
                RerankResult(
                    content=r.get("content", r.get("snippet", "")),
                    source=r.get("source", "unknown"),
                    original_score=r.get("score", 0.5),
                    final_score=r.get("score", 0.5),
                    score_breakdown={},
                    metadata=r,
                )
                for r in results
            ]

        scored_results = []
        for result in results:
            scores = self._calculate_dimension_scores(result, query, context or {})
            final_score = self._combine_scores(scores)

            scored_results.append(RerankResult(
                content=result.get("content", result.get("snippet", "")),
                source=result.get("source", "unknown"),
                original_score=result.get("score", 0.5),
                final_score=final_score,
                score_breakdown=scores,
                metadata=result,
            ))

        # 按最终分数排序
        scored_results.sort(key=lambda r: r.final_score, reverse=True)

        logger.debug(f"Reranked {len(scored_results)} results")
        return scored_results

    def _calculate_dimension_scores(
        self,
        result: dict,
        query: str,
        context: dict,
    ) -> dict[str, float]:
        """计算各维度分数"""
        scores = {}

        # 1. 语义分数（原始检索分数）
        scores["semantic"] = float(result.get("score", 0.5))

        # 2. 时间新近度
        scores["recency"] = self._calc_recency(result)

        # 3. 热度（基于访问次数）
        scores["hotness"] = self._calc_hotness(result)

        # 4. 来源优先级
        scores["source"] = self._calc_source_priority(result, context)

        # 5. 查询相关性（关键词匹配度）
        if query:
            scores["query_match"] = self._calc_query_match(result, query)
        else:
            scores["query_match"] = 0.5

        return scores

    def _combine_scores(self, scores: dict[str, float]) -> float:
        """融合各维度分数"""
        total = 0.0
        total_weight = 0.0

        weight_map = {
            "semantic": self.config.semantic_weight,
            "recency": self.config.recency_weight,
            "hotness": self.config.hotness_weight,
            "source": self.config.source_weight,
            "query_match": self.config.semantic_weight * 0.5,  # 查询匹配作为语义的补充
        }

        for dim, score in scores.items():
            weight = weight_map.get(dim, 0.0)
            total += score * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return min(1.0, total / total_weight)

    @staticmethod
    def _calc_recency(result: dict) -> float:
        """
        计算时间新近度分数

        基于文档更新时间，使用指数衰减
        半衰期设为 30 天
        """
        timestamp_str = result.get("timestamp") or result.get("modified_time") or result.get("created_at")

        if not timestamp_str:
            return 0.5  # 无时间信息，返回中等分数

        try:
            if isinstance(timestamp_str, (int, float)):
                updated_at = datetime.fromtimestamp(timestamp_str, tz=timezone.utc)
            else:
                # 尝试解析 ISO 格式
                updated_at = datetime.fromisoformat(str(timestamp_str).replace("Z", "+00:00"))
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
        except Exception:
            return 0.5

        now = datetime.now(timezone.utc)
        delta_days = (now - updated_at).days

        # 指数衰减：score = exp(-days / half_life)
        half_life = 30  # 30 天半衰期
        score = math.exp(-delta_days / half_life)

        return max(0.0, min(1.0, score))

    @staticmethod
    def _calc_hotness(result: dict) -> float:
        """
        计算热度分数

        基于访问次数，使用对数尺度
        """
        access_count = result.get("access_count", result.get("view_count", 0))

        try:
            access_count = int(access_count)
        except (ValueError, TypeError):
            access_count = 0

        # 对数尺度：hotness = log(1 + count) / log(max_expected)
        # 假设最大访问次数约 1000
        raw = math.log(1 + access_count)
        normalized = raw / math.log(1001)  # log(1001) ≈ 6.9

        return min(1.0, normalized)

    @staticmethod
    def _calc_source_priority(result: dict, context: dict) -> float:
        """
        计算来源优先级分数

        基于知识源的配置优先级
        """
        priority = result.get("priority", 5)

        try:
            priority = int(priority)
        except (ValueError, TypeError):
            priority = 5

        # 归一化：1-10 映射到 0.1-1.0
        normalized = (priority - 1) / 9

        return max(0.1, min(1.0, normalized))

    @staticmethod
    def _calc_query_match(result: dict, query: str) -> float:
        """
        计算查询关键词匹配度

        简单的关键词匹配算法
        """
        content = result.get("content", result.get("snippet", ""))
        if not content or not query:
            return 0.5

        content_lower = content.lower()
        query_terms = set(query.lower().split())

        if not query_terms:
            return 0.5

        # 计算匹配的词数比例
        matched = sum(1 for term in query_terms if term in content_lower)
        match_ratio = matched / len(query_terms)

        # 考虑词频
        total_occurrences = sum(content_lower.count(term) for term in query_terms)
        frequency_bonus = min(0.2, total_occurrences * 0.02)  # 最多加 0.2

        score = match_ratio * 0.8 + frequency_bonus
        return min(1.0, score)


class HybridReranker(Reranker):
    """混合重排序器 - 支持自定义权重"""

    def __init__(
        self,
        config: RerankConfig | None = None,
        custom_weights: dict[str, float] | None = None,
    ):
        super().__init__(config)
        self.custom_weights = custom_weights or {}

    def _combine_scores(self, scores: dict[str, float]) -> float:
        """融合分数，支持自定义权重覆盖"""
        total = 0.0
        total_weight = 0.0

        # 默认权重
        default_weights = {
            "semantic": self.config.semantic_weight,
            "recency": self.config.recency_weight,
            "hotness": self.config.hotness_weight,
            "source": self.config.source_weight,
            "query_match": self.config.semantic_weight * 0.5,
        }

        # 合并自定义权重
        weights = {**default_weights, **self.custom_weights}

        for dim, score in scores.items():
            weight = weights.get(dim, 0.0)
            total += score * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return min(1.0, total / total_weight)


def create_reranker(
    config: RerankConfig | None = None,
    custom_weights: dict[str, float] | None = None,
) -> Reranker:
    """创建重排序器工厂函数"""
    if custom_weights:
        return HybridReranker(config, custom_weights)
    return Reranker(config)
