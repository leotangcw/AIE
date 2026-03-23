"""Rerank Module for multi-dimensional result ranking."""

import math
from datetime import datetime, timezone

from loguru import logger

from ..models.config import RerankConfig, RerankWeights
from ..models.query import IntentResult, RetrievalResult, TypedQuery


class RerankModule:
    """
    Multi-dimensional reranking for retrieval results.

    Factors:
    1. Semantic similarity (from vector search)
    2. Hotness (based on active_count)
    3. Recency (time since last update)
    4. Level preference (L1 preferred over L2 for overview queries)
    5. Type match (exact context_type match)
    """

    def __init__(self, config: RerankConfig | None = None):
        self.config = config or RerankConfig()
        self.weights = self.config.weights

    def rerank(
        self,
        results: list[RetrievalResult],
        query: TypedQuery,
        intent: IntentResult,
    ) -> list[RetrievalResult]:
        """
        Rerank results based on multiple dimensions.

        Args:
            results: Initial retrieval results
            query: Original typed query
            intent: Analyzed intent

        Returns:
            Reranked results with updated final_score
        """
        if not results:
            return results

        # Calculate dimension scores for each result
        scored_results = []
        for result in results:
            scores = self._calculate_dimension_scores(result, query, intent)
            final_score = self._combine_scores(scores)
            result.final_score = final_score
            scored_results.append(result)

        # Sort by final score
        scored_results.sort(key=lambda r: r.final_score, reverse=True)

        return scored_results

    def _calculate_dimension_scores(
        self,
        result: RetrievalResult,
        query: TypedQuery,
        intent: IntentResult,
    ) -> dict[str, float]:
        """Calculate individual dimension scores."""
        scores = {}

        # 1. Semantic score (already calculated)
        scores["semantic"] = result.score

        # 2. Hotness score (log scale of active count)
        scores["hotness"] = self._calc_hotness(result.memory.active_count)

        # 3. Recency score (newer is better)
        scores["recency"] = self._calc_recency(result.memory.updated_at)

        # 4. Level preference
        scores["level"] = self._calc_level_score(result.memory.level, query.level)

        # 5. Type match
        scores["type_match"] = self._calc_type_match(
            result.memory.context_type,
            intent.context_type,
        )

        return scores

    def _combine_scores(self, scores: dict[str, float]) -> float:
        """Combine dimension scores using weights."""
        total = 0.0
        total_weight = 0.0

        weight_map = {
            "semantic": self.weights.semantic,
            "hotness": self.weights.hotness,
            "recency": self.weights.recency,
            "level": self.weights.level,
            "type_match": self.weights.type_match,
        }

        for dim, score in scores.items():
            weight = weight_map.get(dim, 0.0)
            total += score * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return total / total_weight

    @staticmethod
    def _calc_hotness(active_count: int) -> float:
        """
        Calculate hotness score.

        Uses log scale: hotness = log(1 + active_count)
        Normalized to 0-1 range (assuming max ~1000 accesses)
        """
        raw = math.log(1 + active_count)
        # Normalize: log(1001) ≈ 6.9, so divide by 7
        return min(1.0, raw / 7.0)

    @staticmethod
    def _calc_recency(updated_at: datetime) -> float:
        """
        Calculate recency score.

        Based on days since last update.
        Exponential decay: score = exp(-days / half_life)
        """
        now = datetime.now(timezone.utc)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)

        delta = now - updated_at
        days = delta.total_seconds() / 86400

        # Half-life of 30 days
        half_life = 30.0
        return math.exp(-days / half_life)

    @staticmethod
    def _calc_level_score(memory_level: int, query_level: int) -> float:
        """
        Calculate level preference score.

        If query specifies a level, prefer that level.
        Otherwise, prefer L1 (overview) slightly over L2 (full content).
        """
        if query_level != 2:  # Query has specific level
            if memory_level == query_level:
                return 1.0
            elif abs(memory_level - query_level) == 1:
                return 0.5
            else:
                return 0.0

        # No specific level in query
        # Prefer L1 > L2 > L0
        level_prefs = {1: 1.0, 2: 0.8, 0: 0.6}
        return level_prefs.get(memory_level, 0.5)

    @staticmethod
    def _calc_type_match(
        memory_type: str,
        intent_type: str,
    ) -> float:
        """
        Calculate type match score.

        Exact match = 1.0
        Same category = 0.5
        Any/mismatch = 0.1
        """
        if intent_type == "all":
            return 0.5  # Neutral

        if memory_type == intent_type:
            return 1.0

        # Some types are related
        related_pairs = {
            ("resource", "skill"),
            ("skill", "resource"),
        }
        if (memory_type, intent_type) in related_pairs:
            return 0.3

        return 0.1

    def explain_ranking(self, result: RetrievalResult, query: TypedQuery, intent: IntentResult) -> dict:
        """
        Explain why a result has its ranking.

        Useful for debugging and transparency.
        """
        scores = self._calculate_dimension_scores(result, query, intent)
        weight_map = {
            "semantic": self.weights.semantic,
            "hotness": self.weights.hotness,
            "recency": self.weights.recency,
            "level": self.weights.level,
            "type_match": self.weights.type_match,
        }

        breakdown = {}
        total = 0.0

        for dim, score in scores.items():
            weight = weight_map.get(dim, 0.0)
            contribution = score * weight
            breakdown[dim] = {
                "raw_score": round(score, 4),
                "weight": weight,
                "contribution": round(contribution, 4),
            }
            total += contribution

        return {
            "uri": result.memory.uri,
            "name": result.memory.name,
            "final_score": round(total, 4),
            "breakdown": breakdown,
        }
