"""Retrieval Engine with hierarchical search and score propagation."""

import math
from collections import deque
from typing import Optional

from loguru import logger

from ..models.config import RetrievalConfig
from ..models.memory import Memory
from ..models.query import IntentResult, RetrievalResult, TypedQuery
from ..storage.memory_store import MemoryStore
from ..storage.vector_index import VectorIndex
from ..utils.embedder import Embedder


class RetrievalEngine:
    """
    Hierarchical retrieval engine with score propagation.

    Implements:
    1. Semantic search via vector similarity
    2. Hierarchical URI-based traversal
    3. Score propagation from parent to children
    4. Convergence detection
    5. Fallback to keyword search
    """

    def __init__(
        self,
        vector_index: VectorIndex,
        memory_store: MemoryStore,
        embedder: Embedder,
        config: RetrievalConfig,
    ):
        self.vector_index = vector_index
        self.memory_store = memory_store
        self.embedder = embedder
        self.config = config

    async def retrieve(
        self,
        query: TypedQuery,
        intent: IntentResult,
    ) -> list[RetrievalResult]:
        """
        Perform hierarchical retrieval.

        Steps:
        1. Generate query embedding
        2. Semantic search to get initial candidates
        3. URI scope filtering based on intent
        4. Hierarchical expansion (traverse parent-child relationships)
        5. Score propagation (parent score influences child score)
        6. Convergence detection
        7. Return ranked results
        """
        # Generate query embedding
        query_vector = self.embedder.embed(query.query_text)

        # Determine URI prefix for scope filtering
        uri_prefix = self._get_uri_prefix(intent, query)

        # Step 1: Semantic search
        candidates = await self._semantic_search(
            query_vector=query_vector,
            intent=intent,
            uri_prefix=uri_prefix,
            limit=query.limit * 3,  # Get more candidates for filtering
        )

        if not candidates:
            # Fallback to keyword search
            logger.info("Vector search returned no results, falling back to keyword search")
            return await self._keyword_search_fallback(query, intent, uri_prefix)

        # Step 2: Hierarchical expansion with score propagation
        expanded = await self._hierarchical_expansion(
            candidates=candidates,
            query_vector=query_vector,
            alpha=self.config.alpha,
        )

        # Step 3: Convergence detection
        converged = self._detect_convergence(
            expanded,
            rounds=self.config.convergence_rounds,
        )

        # Step 4: Limit results
        results = expanded[:query.limit]

        # Increment active count for retrieved memories
        for result in results:
            await self.memory_store.increment_active_count(result.memory.uri)

        return results

    async def _semantic_search(
        self,
        query_vector: list[float],
        intent: IntentResult,
        uri_prefix: str | None,
        limit: int,
    ) -> list[RetrievalResult]:
        """Perform vector similarity search."""
        # Map intent context_type to filter
        context_type = None
        if intent.context_type != "all":
            context_type = intent.context_type

        try:
            # Search vector index
            hits = await self.vector_index.search(
                query_vector=query_vector,
                context_type=context_type,
                uri_prefix=uri_prefix,
                limit=limit,
            )

            # Fetch memories and build results
            results = []
            for hit in hits:
                memory = await self.memory_store.get_by_uri(hit["uri"])
                if memory:
                    result = RetrievalResult.from_memory(memory, score=hit["score"])
                    result.hotness_score = RetrievalResult._calc_hotness(memory.active_count)
                    result.final_score = (
                        self.config.alpha * hit["score"]
                        + (1 - self.config.alpha) * result.hotness_score
                    )
                    results.append(result)

            return results

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    async def _hierarchical_expansion(
        self,
        candidates: list[RetrievalResult],
        query_vector: list[float],
        alpha: float,
    ) -> list[RetrievalResult]:
        """
        Expand candidates hierarchically with score propagation.

        For each candidate:
        1. Check if it has parent (parent_uri)
        2. If parent exists, get parent's score
        3. Propagate: child_score = alpha * child_score + (1-alpha) * parent_score

        Also expands to children for better recall.
        """
        # Build a map of URI -> result
        uri_to_result = {r.memory.uri: r for r in candidates}

        # Queue for BFS expansion
        queue = deque(candidates)
        iteration = 0
        max_iterations = self.config.max_iterations

        while queue and iteration < max_iterations:
            iteration += 1
            current_batch = []
            new_candidates = []

            # Process current batch
            while queue:
                result = queue.popleft()
                current_batch.append(result.memory.uri)

                # Get children of current memory
                children = await self.memory_store.get_children(result.memory.uri)
                for child in children:
                    child_uri = child.uri
                    if child_uri in uri_to_result:
                        # Already have this candidate, update score
                        existing = uri_to_result[child_uri]
                        # Score propagation: parent's influence
                        propagated_score = (
                            alpha * existing.score
                            + (1 - alpha) * result.final_score * 0.5
                        )
                        existing.final_score = max(existing.final_score, propagated_score)
                    else:
                        # New candidate discovered through hierarchy
                        # Calculate its semantic score
                        child_text = child.get_text_for_embedding()
                        if child_text:
                            try:
                                child_vector = self.embedder.embed(child_text)
                                # Simple cosine similarity (approximation)
                                child_score = self._cosine_similarity(query_vector, child_vector)
                            except Exception:
                                child_score = result.final_score * 0.5

                        child_hotness = RetrievalResult._calc_hotness(child.active_count)
                        child_result = RetrievalResult(
                            memory=child,
                            score=child_score,
                            hotness_score=child_hotness,
                            final_score=alpha * child_score + (1 - alpha) * child_hotness,
                            level=child.level,
                        )

                        # Apply parent's propagated influence
                        child_result.final_score = (
                            alpha * child_result.final_score
                            + (1 - alpha) * result.final_score * 0.5
                        )

                        uri_to_result[child_uri] = child_result
                        new_candidates.append(child_result)

                        # Add to queue for further expansion
                        if child.level == 2:  # Only expand L2 nodes
                            queue.append(child_result)

                # Also get parent and propagate score upward
                if result.memory.parent_uri:
                    parent = await self.memory_store.get_by_uri(result.memory.parent_uri)
                    if parent and parent.uri not in uri_to_result:
                        parent_hotness = RetrievalResult._calc_hotness(parent.active_count)
                        parent_result = RetrievalResult(
                            memory=parent,
                            score=result.score * 0.8,  # Slight decay
                            hotness_score=parent_hotness,
                            final_score=result.final_score * 0.8,
                            level=parent.level,
                        )
                        uri_to_result[parent.uri] = parent_result
                        new_candidates.append(parent_result)

            # Add new candidates to queue for next iteration
            for candidate in new_candidates:
                queue.append(candidate)

        # Sort by final score
        all_results = list(uri_to_result.values())
        all_results.sort(key=lambda r: r.final_score, reverse=True)

        return all_results

    def _detect_convergence(
        self,
        results: list[RetrievalResult],
        rounds: int = 3,
    ) -> bool:
        """
        Detect if results have converged.

        Convergence = top-k remains unchanged for N consecutive rounds.
        This is checked externally by tracking previous top-k lists.
        """
        # Simple implementation: just return False to allow full expansion
        # A more sophisticated implementation would track history
        return False

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def _get_uri_prefix(
        self,
        intent: IntentResult,
        query: TypedQuery,
    ) -> str | None:
        """Determine URI prefix based on intent and query."""
        # Priority: explicit query params > inferred from intent

        if query.session_id:
            return f"viking://session/{query.session_id}"

        if query.user_id:
            return f"viking://user/{query.user_id}"

        if query.agent_id:
            return f"viking://agent/{query.agent_id}"

        # Infer from intent scope
        if intent.scope == "session" and query.session_id:
            return f"viking://session/{query.session_id}"
        elif intent.scope == "user" and query.user_id:
            return f"viking://user/{query.user_id}"
        elif intent.scope == "agent" and query.agent_id:
            return f"viking://agent/{query.agent_id}"

        # Global scope - no prefix filtering
        return None

    async def _keyword_search_fallback(
        self,
        query: TypedQuery,
        intent: IntentResult,
        uri_prefix: str | None,
    ) -> list[RetrievalResult]:
        """Fallback to simple keyword search."""
        keywords = query.query_text.split()

        context_type = None
        if intent.context_type != "all":
            context_type = intent.context_type

        memories = await self.memory_store.search_by_keywords(
            keywords=keywords,
            context_type=context_type,
            limit=query.limit,
        )

        results = []
        for memory in memories:
            result = RetrievalResult.from_memory(memory, score=0.5)
            results.append(result)

        return results
