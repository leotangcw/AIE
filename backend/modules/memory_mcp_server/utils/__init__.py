"""Utility modules for embedding and LLM calls."""

from .embedder import (
    Embedder,
    EmbedderUnavailableError,
    UnifiedEmbedderAdapter,
    create_embedder,
    create_unified_adapter,
    BGE_M3_DIMENSION,
)

__all__ = [
    "Embedder",
    "EmbedderUnavailableError",
    "UnifiedEmbedderAdapter",
    "create_embedder",
    "create_unified_adapter",
    "BGE_M3_DIMENSION",
]
