"""Configuration models for Memory-MCP-Server."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    """Server configuration."""
    host: str = "0.0.0.0"
    port: int = 8765
    mode: Literal["stdio", "http"] = "stdio"


class StorageConfig(BaseModel):
    """Storage configuration."""
    db_path: str = "./data/memory.db"
    vector_dim: int = 512  # bge-small-zh-v1.5 = 512
    vector_table: str = "memory_vectors"


class EmbeddingConfig(BaseModel):
    """Embedding provider configuration.

    Default uses BAAI/bge-m3 via local path.
    Supports local model paths for offline operation.
    """
    provider: Literal["bge", "local", "openai", "jina", "fallback"] = "bge"
    model: str = "BAAI/bge-m3"
    model_path: str | None = None  # Local model path (e.g., /path/to/bge-m3)
    batch_size: int = 32
    device: str = "cpu"


class LLMConfig(BaseModel):
    """
    LLM configuration for intent analysis and L0/L1 generation.

    Falls back to local generation if LLM unavailable.
    """
    provider: Literal["openai", "volcengine", "litellm"] = "openai"
    model: str = "gpt-4o-mini"
    api_key_env: str = "OPENAI_API_KEY"
    enabled: bool = True  # Set to False to disable LLM-based features


class RetrievalConfig(BaseModel):
    """Retrieval engine configuration."""
    alpha: float = 0.7
    max_iterations: int = 10
    convergence_rounds: int = 3
    default_limit: int = 5


class RerankWeights(BaseModel):
    """Weights for reranking factors."""
    semantic: float = 0.5
    hotness: float = 0.2
    recency: float = 0.15
    level: float = 0.1
    type_match: float = 0.05


class RerankConfig(BaseModel):
    """Rerank module configuration."""
    weights: RerankWeights = Field(default_factory=RerankWeights)


class TierConfig(BaseModel):
    """Tier manager configuration."""
    auto_generate_l0: bool = True
    auto_generate_l1: bool = True
    generate_async: bool = False


class MultitenancyConfig(BaseModel):
    """Multitenancy configuration."""
    enabled: bool = True
    tenant_id_header: str = "X-Tenant-ID"


class Config(BaseModel):
    """Main configuration for Memory-MCP-Server."""
    server: ServerConfig = Field(default_factory=ServerConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    rerank: RerankConfig = Field(default_factory=RerankConfig)
    tier: TierConfig = Field(default_factory=TierConfig)
    multitenancy: MultitenancyConfig = Field(default_factory=MultitenancyConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        """Load configuration from YAML file."""
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    @classmethod
    def default(cls) -> "Config":
        """Get default configuration."""
        return cls()
