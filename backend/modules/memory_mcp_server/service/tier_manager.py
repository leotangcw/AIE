"""Tier Manager for L0/L1/L2 hierarchy management."""

import uuid
from datetime import datetime
from typing import Optional

from loguru import logger

from ..models.config import TierConfig
from ..models.memory import Memory
from ..storage.memory_store import MemoryStore
from ..utils.llm import LLMClient, generate_l0, generate_l1


class TierManager:
    """
    Manages L0/L1/L2 tier hierarchy for memories.

    L0 = Abstract (one sentence summary)
    L1 = Overview (paragraph summary)
    L2 = Full content
    """

    def __init__(
        self,
        memory_store: MemoryStore,
        llm: LLMClient,
        config: TierConfig,
    ):
        self.memory_store = memory_store
        self.llm = llm
        self.config = config

    async def store(
        self,
        content: str,
        name: str,
        context_type: str,
        uri: str | None = None,
        parent_uri: str | None = None,
        tags: list[str] | None = None,
        source: str = "unknown",
        metadata: dict | None = None,
        tenant_id: str | None = None,
    ) -> Memory:
        """
        Store a memory and auto-generate L0/L1 tiers.

        The main memory (L2) is stored first, then L0/L1 are generated
        and stored as separate linked memories.
        """
        # Generate URI if not provided
        if uri is None:
            memory_id = str(uuid.uuid4())
            uri = f"viking://memory/{memory_id}"

        # Create L2 memory (full content)
        l2_memory = Memory(
            id=str(uuid.uuid4()),
            uri=uri,
            parent_uri=parent_uri,
            context_type=context_type,
            level=2,
            content=content,
            name=name,
            tags=tags or [],
            source=source,
            metadata=metadata or {},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            tenant_id=tenant_id,
        )

        # Store L2
        await self.memory_store.create(l2_memory)

        # Auto-generate L0 and L1 if enabled
        if self.config.auto_generate_l0:
            l0_content = generate_l0(content, self.llm)
            await self._create_tier_memory(
                level=0,
                abstract=l0_content,
                parent_uri=uri,
                name=f"{name} (Abstract)",
                tags=tags,
                source=source,
                tenant_id=tenant_id,
            )

        if self.config.auto_generate_l1:
            l1_content = generate_l1(content, self.llm)
            await self._create_tier_memory(
                level=1,
                overview=l1_content,
                parent_uri=uri,
                name=f"{name} (Overview)",
                tags=tags,
                source=source,
                tenant_id=tenant_id,
            )

        return l2_memory

    async def _create_tier_memory(
        self,
        level: int,
        parent_uri: str,
        name: str,
        tags: list[str] | None = None,
        source: str = "unknown",
        abstract: str | None = None,
        overview: str | None = None,
        tenant_id: str | None = None,
    ) -> Memory:
        """Create a tier memory (L0 or L1)."""
        tier_uri = f"{parent_uri}/.level_{level}"

        tier_memory = Memory(
            id=str(uuid.uuid4()),
            uri=tier_uri,
            parent_uri=parent_uri,
            context_type="memory",
            level=level,
            abstract=abstract,
            overview=overview,
            content="",  # Tiers don't have full content
            name=name,
            tags=tags or [],
            source=source,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            tenant_id=tenant_id,
        )

        await self.memory_store.create(tier_memory)
        return tier_memory

    async def get(
        self,
        uri: str,
        level: int | None = None,
    ) -> Memory | None:
        """
        Get a memory at a specific level.

        If level is None, returns the memory as-is.
        If level is specified, tries to get that tier first,
        then falls back to other tiers if not found.
        """
        if level is not None:
            # Try specific level first
            memory = await self.memory_store.get_by_uri(uri, level)
            if memory:
                return memory

            # Fall back: if asking for L0/L1, try to get from parent
            if level in (0, 1):
                # Get the L2 parent
                l2_memory = await self.memory_store.get_by_uri(uri, 2)
                if l2_memory:
                    # Return appropriate tier
                    if level == 0:
                        return Memory(
                            id=l2_memory.id,
                            uri=l2_memory.uri,
                            parent_uri=l2_memory.parent_uri,
                            context_type=l2_memory.context_type,
                            level=0,
                            abstract=l2_memory.abstract or "",
                            overview=None,
                            content="",
                            name=f"{l2_memory.name} (Abstract)",
                            tags=l2_memory.tags,
                            source=l2_memory.source,
                            created_at=l2_memory.created_at,
                            updated_at=l2_memory.updated_at,
                            tenant_id=l2_memory.tenant_id,
                        )
                    else:  # level == 1
                        return Memory(
                            id=l2_memory.id,
                            uri=l2_memory.uri,
                            parent_uri=l2_memory.parent_uri,
                            context_type=l2_memory.context_type,
                            level=1,
                            abstract=l2_memory.abstract,
                            overview=l2_memory.overview or "",
                            content="",
                            name=f"{l2_memory.name} (Overview)",
                            tags=l2_memory.tags,
                            source=l2_memory.source,
                            created_at=l2_memory.created_at,
                            updated_at=l2_memory.updated_at,
                            tenant_id=l2_memory.tenant_id,
                        )

                # If L2 doesn't exist, try getting tier directly
                tier_uri = f"{uri}/.level_{level}"
                return await self.memory_store.get_by_uri(tier_uri)

        # No level specified, get as-is
        return await self.memory_store.get_by_uri(uri)

    async def get_with_context(
        self,
        uri: str,
        min_level: int = 0,
    ) -> Memory:
        """
        Get a memory with context filled in from available tiers.

        If a higher tier's content is missing but available in a lower tier,
        it will be promoted.
        """
        # First try to get L2
        memory = await self.memory_store.get_by_uri(uri, 2)

        if memory is None:
            # Try any level
            memory = await self.memory_store.get_by_uri(uri)

        if memory is None:
            raise ValueError(f"Memory not found: {uri}")

        # Ensure we have content at the requested minimum level
        if min_level == 0 and not memory.abstract:
            # Try to get L0 from tier
            l0 = await self.memory_store.get_by_uri(f"{uri}/.level_0")
            if l0:
                memory.abstract = l0.abstract
            elif self.config.auto_generate_l0 and memory.content:
                memory.abstract = generate_l0(memory.content, self.llm)

        if min_level >= 1 and not memory.overview:
            # Try to get L1 from tier
            l1 = await self.memory_store.get_by_uri(f"{uri}/.level_1")
            if l1:
                memory.overview = l1.overview
            elif self.config.auto_generate_l1 and memory.content:
                memory.overview = generate_l1(memory.content, self.llm)

        return memory

    async def update_content(
        self,
        uri: str,
        new_content: str,
    ) -> Memory | None:
        """Update memory content and regenerate tiers."""
        # Get existing L2
        l2 = await self.memory_store.get_by_uri(uri, 2)
        if not l2:
            return None

        # Update L2 content
        from ..models.memory import MemoryUpdate
        updated = await self.memory_store.update(uri, MemoryUpdate(content=new_content))

        if updated:
            # Regenerate L0/L1
            if self.config.auto_generate_l0:
                l0_content = generate_l0(new_content, self.llm)
                l0_uri = f"{uri}/.level_0"
                existing_l0 = await self.memory_store.get_by_uri(l0_uri)
                if existing_l0:
                    await self.memory_store.update(l0_uri, MemoryUpdate(abstract=l0_content))
                else:
                    await self._create_tier_memory(
                        level=0,
                        parent_uri=uri,
                        name=f"{updated.name} (Abstract)",
                        abstract=l0_content,
                        tags=updated.tags,
                        source=updated.source,
                        tenant_id=updated.tenant_id,
                    )

            if self.config.auto_generate_l1:
                l1_content = generate_l1(new_content, self.llm)
                l1_uri = f"{uri}/.level_1"
                existing_l1 = await self.memory_store.get_by_uri(l1_uri)
                if existing_l1:
                    await self.memory_store.update(l1_uri, MemoryUpdate(overview=l1_content))
                else:
                    await self._create_tier_memory(
                        level=1,
                        parent_uri=uri,
                        name=f"{updated.name} (Overview)",
                        overview=l1_content,
                        tags=updated.tags,
                        source=updated.source,
                        tenant_id=updated.tenant_id,
                    )

        return updated

    def format_for_context(self, memory: Memory, level: int | None = None) -> str:
        """Format a memory for injection into agent context."""
        return memory.format_for_context(level)
