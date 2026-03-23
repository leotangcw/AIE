"""Query and result models for retrieval."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

from .memory import Memory


class TypedQuery(BaseModel):
    """A typed query for memory retrieval."""

    query_text: str
    context_type: Literal["memory", "resource", "skill", "all"] = "all"
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    limit: int = 5
    level: Literal[0, 1, 2] = 2
    tenant_id: Optional[str] = None


class IntentResult(BaseModel):
    """Result of intent analysis."""

    intent: str
    optimized_query: str
    context_type: Literal["memory", "resource", "skill", "all"] = "all"
    scope: Literal["session", "user", "agent", "global"] = "global"
    entities: list[str] = Field(default_factory=list)
    confidence: float = 1.0


class RetrievalResult(BaseModel):
    """A single retrieval result with scores."""

    memory: Memory
    score: float = 0.0
    hotness_score: float = 0.0
    final_score: float = 0.0
    level: int = 2

    @classmethod
    def from_memory(cls, memory: Memory, score: float = 0.0) -> "RetrievalResult":
        """Create from a memory with default scores."""
        return cls(
            memory=memory,
            score=score,
            hotness_score=cls._calc_hotness(memory.active_count),
            final_score=score,
            level=memory.level,
        )

    @staticmethod
    def _calc_hotness(active_count: int) -> float:
        """Calculate hotness score from active count."""
        import math
        return math.log(1 + active_count)

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "uri": self.memory.uri,
            "name": self.memory.name,
            "context_type": self.memory.context_type,
            "level": self.level,
            "score": round(self.score, 4),
            "hotness_score": round(self.hotness_score, 4),
            "final_score": round(self.final_score, 4),
            "content": self.memory.format_for_context(self.level),
            "tags": self.memory.tags,
            "source": self.memory.source,
            "created_at": self.memory.created_at.isoformat(),
        }


class QueryResult(BaseModel):
    """Complete result of a query including all results and intent."""

    query: TypedQuery
    results: list[RetrievalResult] = Field(default_factory=list)
    intent: Optional[IntentResult] = None
    total_found: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "query": self.query.query_text,
            "intent": self.intent.model_dump() if self.intent else None,
            "results": [r.to_dict() for r in self.results],
            "total_found": self.total_found,
        }


class MemoryStats(BaseModel):
    """Statistics about memory storage."""

    total_memories: int = 0
    by_context_type: dict[str, int] = Field(default_factory=dict)
    by_level: dict[int, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    total_vectors: int = 0
    storage_size_bytes: int = 0
