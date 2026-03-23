"""Memory entity and related models."""

import json
import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Memory(BaseModel):
    """Memory entity with L0/L1/L2 hierarchy."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    uri: str
    parent_uri: Optional[str] = None

    # Context type
    context_type: Literal["memory", "resource", "skill"]

    # L0/L1/L2 hierarchy levels
    # L0 = abstract (one sentence summary)
    # L1 = overview (paragraph summary)
    # L2 = full content
    level: Literal[0, 1, 2] = 2
    abstract: Optional[str] = None
    overview: Optional[str] = None
    content: str = ""

    # Metadata
    name: str
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    source: str = "unknown"  # chat, document, event, etc.
    metadata: dict = Field(default_factory=dict)

    # Vector reference
    vector_id: Optional[str] = None

    # Audit fields
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    active_count: int = 0

    # Tenant isolation
    tenant_id: Optional[str] = None

    def to_storage_dict(self) -> dict:
        """Convert to dictionary for SQLite storage."""
        return {
            "id": self.id,
            "uri": self.uri,
            "parent_uri": self.parent_uri,
            "context_type": self.context_type,
            "level": self.level,
            "abstract": self.abstract,
            "overview": self.overview,
            "content": self.content,
            "name": self.name,
            "description": self.description,
            "tags": json.dumps(self.tags),
            "source": self.source,
            "metadata": json.dumps(self.metadata),
            "vector_id": self.vector_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "active_count": self.active_count,
            "tenant_id": self.tenant_id,
        }

    @classmethod
    def from_storage_dict(cls, data: dict) -> "Memory":
        """Create from SQLite storage dictionary."""
        return cls(
            id=data["id"],
            uri=data["uri"],
            parent_uri=data["parent_uri"],
            context_type=data["context_type"],
            level=data["level"],
            abstract=data["abstract"],
            overview=data["overview"],
            content=data["content"] or "",
            name=data["name"],
            description=data["description"],
            tags=json.loads(data["tags"]) if data["tags"] else [],
            source=data["source"] or "unknown",
            metadata=json.loads(data["metadata"]) if data["metadata"] else {},
            vector_id=data["vector_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            active_count=data["active_count"] or 0,
            tenant_id=data.get("tenant_id"),
        )

    def get_text_for_embedding(self) -> str:
        """Get text content for embedding generation."""
        if self.level == 0:
            return self.abstract or ""
        elif self.level == 1:
            return self.overview or self.abstract or self.content
        else:
            return self.content

    def format_for_context(self, level: int | None = None) -> str:
        """Format memory for injection into agent context."""
        target_level = level if level is not None else self.level
        if target_level == 0:
            text = self.abstract or ""
        elif target_level == 1:
            text = self.overview or self.abstract or self.content
        else:
            text = self.content

        return f"[{self.name}] {text}"


class MemoryCreate(BaseModel):
    """Model for creating a new memory."""
    content: str
    name: str
    context_type: Literal["memory", "resource", "skill"] = "memory"
    uri: Optional[str] = None
    parent_uri: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    source: str = "unknown"
    metadata: dict = Field(default_factory=dict)
    tenant_id: Optional[str] = None


class MemoryUpdate(BaseModel):
    """Model for updating a memory."""
    content: Optional[str] = None
    name: Optional[str] = None
    abstract: Optional[str] = None
    overview: Optional[str] = None
    tags: Optional[list[str]] = None
    metadata: Optional[dict] = None
