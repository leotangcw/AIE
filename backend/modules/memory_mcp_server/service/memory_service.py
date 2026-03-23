"""Memory Service - Main facade composing all sub-modules."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from loguru import logger

from ..models.config import (
    Config,
    EmbeddingConfig,
    LLMConfig,
    RetrievalConfig,
    RerankConfig,
    StorageConfig,
    TierConfig,
)
from ..models.memory import Memory, MemoryCreate, MemoryUpdate
from ..models.query import (
    IntentResult,
    MemoryStats,
    QueryResult,
    RetrievalResult,
    TypedQuery,
)
from ..storage.database import Database
from ..storage.memory_store import MemoryStore
from ..storage.vector_index import VectorIndex
from ..utils.embedder import Embedder, create_embedder
from ..utils.llm import LLMClient
from .intent_analyzer import IntentAnalyzer
from .rerank_module import RerankModule
from .retrieval_engine import RetrievalEngine
from .tier_manager import TierManager


class MemoryService:
    """
    Main facade for the memory system.

    Composes:
    - TierManager (L0/L1/L2 hierarchy)
    - IntentAnalyzer (query understanding)
    - RetrievalEngine (hierarchical search)
    - RerankModule (result ranking)
    - MemoryStore (persistence)
    - VectorIndex (semantic search via AIE's bge-small-zh-v1.5)
    - Embedder (bge-small-zh-v1.5 by default)
    - LLMClient (content generation)
    """

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

        # Initialize storage
        self.db = Database(self.config.storage)
        self.memory_store = MemoryStore(self.db)
        # VectorIndex uses db_path directly
        self.vector_index = VectorIndex(
            db_path=self.config.storage.db_path,
            config=self.config.storage,
        )

        # Initialize embedder (default: BAAI/bge-m3 on CPU, local path preferred)
        self.embedder: Embedder = create_embedder(
            provider=self.config.embedding.provider,
            model=self.config.embedding.model,
            dim=self.config.storage.vector_dim,
            batch_size=self.config.embedding.batch_size,
            device=self.config.embedding.device,
            local_path=self.config.embedding.model_path,
        )

        # Initialize LLM (for intent analysis and L0/L1 generation)
        self.llm = LLMClient(
            provider=self.config.llm.provider,
            model=self.config.llm.model,
            api_key_env=self.config.llm.api_key_env,
            enabled=self.config.llm.enabled,
        )

        # Initialize service modules
        self.tier_manager = TierManager(
            memory_store=self.memory_store,
            llm=self.llm,
            config=self.config.tier,
        )
        self.intent_analyzer = IntentAnalyzer(llm=self.llm)
        self.retrieval_engine = RetrievalEngine(
            vector_index=self.vector_index,
            memory_store=self.memory_store,
            embedder=self.embedder,
            config=self.config.retrieval,
        )
        self.rerank_module = RerankModule(config=self.config.rerank)

        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the service (create tables, etc.)."""
        if self._initialized:
            return

        await self.db.initialize()
        await self.vector_index.initialize()
        self._initialized = True
        logger.info("MemoryService initialized with bge-small-zh-v1.5 embeddings")

    async def close(self) -> None:
        """Close the service and cleanup resources."""
        await self.db.close()
        self._initialized = False
        logger.info("MemoryService closed")

    # ==================== Store Operations ====================

    async def store(
        self,
        content: str,
        name: str,
        context_type: Literal["memory", "resource", "skill"] = "memory",
        uri: str | None = None,
        parent_uri: str | None = None,
        tags: list[str] | None = None,
        source: str = "unknown",
        metadata: dict | None = None,
        tenant_id: str | None = None,
        generate_vector: bool = True,
    ) -> Memory:
        """
        Store a new memory with automatic L0/L1 generation.

        Args:
            content: Full content of the memory
            name: Name/title of the memory
            context_type: Type of context (memory/resource/skill)
            uri: Optional custom URI
            parent_uri: Parent memory URI for hierarchy
            tags: Optional tags
            source: Source of the memory (chat, document, event)
            metadata: Optional metadata dict
            tenant_id: Optional tenant ID for multi-tenancy
            generate_vector: Whether to generate embedding (disable for bulk import)

        Returns:
            Created memory
        """
        # Store via TierManager (handles L0/L1 auto-generation)
        memory = await self.tier_manager.store(
            content=content,
            name=name,
            context_type=context_type,
            uri=uri,
            parent_uri=parent_uri,
            tags=tags,
            source=source,
            metadata=metadata,
            tenant_id=tenant_id,
        )

        # Generate and store vector
        if generate_vector and memory.level == 2:
            try:
                vector = self.embedder.embed(content)
                vector_id = await self.vector_index.insert(
                    memory_id=memory.id,
                    uri=memory.uri,
                    level=memory.level,
                    context_type=context_type,
                    content=content,
                    vector=vector,
                    tenant_id=tenant_id,
                )
                memory.vector_id = vector_id
            except Exception as e:
                logger.warning(f"Failed to generate vector for {memory.uri}: {e}")

        return memory

    async def get(
        self,
        uri: str,
        level: int | None = None,
        tenant_id: str | None = None,
    ) -> Memory | None:
        """Get a memory by URI."""
        return await self.tier_manager.get(uri, level)

    async def update(
        self,
        uri: str,
        update: MemoryUpdate,
        regenerate_tiers: bool = True,
    ) -> Memory | None:
        """
        Update a memory.

        Args:
            uri: Memory URI
            update: Update data
            regenerate_tiers: Whether to regenerate L0/L1 after content update

        Returns:
            Updated memory or None if not found
        """
        # Get current memory to check content change
        current = await self.memory_store.get_by_uri(uri, 2)
        if not current:
            return None

        # Update via memory store
        updated = await self.memory_store.update(uri, update)

        if updated and update.content and regenerate_tiers:
            # Regenerate L0/L1 tiers
            await self.tier_manager.update_content(uri, update.content)

        return updated

    async def delete(self, uri: str) -> bool:
        """Delete a memory and its children."""
        # Delete vectors first
        await self.vector_index.delete_by_uri(uri)

        # Delete from store (cascade handles tier memories)
        return await self.memory_store.delete(uri)

    async def list_memories(
        self,
        uri_prefix: str | None = None,
        context_type: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Memory]:
        """List memories under a URI prefix."""
        if uri_prefix:
            return await self.memory_store.list_by_prefix(
                uri_prefix=uri_prefix,
                context_type=context_type,
                limit=limit,
                offset=offset,
            )
        elif context_type:
            return await self.memory_store.list_by_prefix(
                uri_prefix="viking://memory",
                context_type=context_type,
                limit=limit,
                offset=offset,
            )
        else:
            return await self.memory_store.list_by_prefix(
                uri_prefix="viking://",
                limit=limit,
                offset=offset,
            )

    # ==================== Recall Operations ====================

    async def recall(
        self,
        query: str,
        context_type: Literal["memory", "resource", "skill", "all"] = "all",
        user_id: str | None = None,
        agent_id: str | None = None,
        session_id: str | None = None,
        limit: int = 5,
        level: int = 2,
        tenant_id: str | None = None,
        context: str | None = None,
    ) -> QueryResult:
        """
        Recall relevant memories for a query.

        This is the main retrieval method that:
        1. Analyzes intent
        2. Performs hierarchical retrieval
        3. Reranks results

        Args:
            query: Query text
            context_type: Filter by type
            user_id: Filter by user
            agent_id: Filter by agent
            session_id: Filter by session
            limit: Max results
            level: Preferred content level
            tenant_id: Tenant ID
            context: Optional session context for intent analysis

        Returns:
            QueryResult with ranked memories
        """
        # Build typed query
        typed_query = TypedQuery(
            query_text=query,
            context_type=context_type,
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            limit=limit,
            level=level,
            tenant_id=tenant_id,
        )

        # Analyze intent
        intent = self.intent_analyzer.analyze(typed_query, context)

        # Perform retrieval
        results = await self.retrieval_engine.retrieve(typed_query, intent)

        # Rerank results
        reranked = self.rerank_module.rerank(results, typed_query, intent)

        return QueryResult(
            query=typed_query,
            results=reranked,
            intent=intent,
            total_found=len(reranked),
        )

    # ==================== Stats Operations ====================

    async def stats(self, tenant_id: str | None = None) -> MemoryStats:
        """Get memory statistics."""
        db_stats = await self.memory_store.get_stats(tenant_id)
        vector_count = await self.vector_index.count()
        db_size = await self.db.getsize()

        return MemoryStats(
            total_memories=db_stats["total"],
            by_context_type=db_stats["by_context_type"],
            by_level=db_stats["by_level"],
            by_source=db_stats["by_source"],
            total_vectors=vector_count,
            storage_size_bytes=db_size,
        )

    # ==================== Bulk Operations ====================

    async def bulk_store(
        self,
        memories: list[MemoryCreate],
        tenant_id: str | None = None,
    ) -> list[Memory]:
        """Bulk store multiple memories."""
        results = []
        for mem_create in memories:
            memory = await self.store(
                content=mem_create.content,
                name=mem_create.name,
                context_type=mem_create.context_type,
                uri=mem_create.uri,
                parent_uri=mem_create.parent_uri,
                tags=mem_create.tags,
                source=mem_create.source,
                metadata=mem_create.metadata,
                tenant_id=tenant_id or mem_create.tenant_id,
            )
            results.append(memory)
        return results
