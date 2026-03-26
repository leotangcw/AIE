# backend/core/__init__.py

"""核心模块 - 模型注册和统一 Embedder"""

from .model_registry import (
    ModelRegistry,
    EmbedderUnavailableError,
    get_model_registry,
    init_model_registry,
)

__all__ = [
    "ModelRegistry",
    "EmbedderUnavailableError",
    "get_model_registry",
    "init_model_registry",
]
