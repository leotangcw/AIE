# backend/core/model_registry.py

"""统一模型注册中心"""

from typing import Optional, Any, TYPE_CHECKING
from loguru import logger

if TYPE_CHECKING:
    from .built_in.embedders import UnifiedEmbedder


class EmbedderUnavailableError(Exception):
    """Embedder 不可用异常（非致命）"""
    pass


class ModelRegistry:
    """统一模型注册中心

    管理所有模型的创建和缓存：
    - LLM (主/子代理)
    - Embedder (BGE-M3 统一)
    """

    def __init__(self, config):
        self._config = config
        # LLM 客户端
        self._llm: Optional[Any] = None
        self._sub_llm: Optional[Any] = None
        # Embedder
        self._embedder: Optional["UnifiedEmbedder"] = None

    # ========== LLM ==========

    async def get_llm(self) -> Any:
        """获取主 LLM 客户端"""
        if self._llm is None:
            self._llm = await self._create_llm(self._config.model)
        return self._llm

    async def get_sub_llm(self) -> Optional[Any]:
        """获取子代理 LLM（可选）"""
        if not self._config.sub_agent.enabled:
            return None
        if self._sub_llm is None:
            self._sub_llm = await self._create_llm(self._config.sub_agent)
        return self._sub_llm

    async def _create_llm(self, model_config) -> Any:
        """创建 LLM 客户端（使用现有 provider 系统）"""
        from backend.modules.providers.factory import create_provider

        provider_id = model_config.provider
        provider_config = self._config.providers.get(provider_id)

        return create_provider(
            api_key=provider_config.api_key if provider_config else None,
            api_base=provider_config.api_base if provider_config else None,
            default_model=model_config.model,
            provider_id=provider_id,
        )

    # ========== Embedder ==========

    async def get_embedder(self) -> "UnifiedEmbedder":
        """获取统一 Embedder"""
        if self._embedder is None:
            self._embedder = await self._create_embedder()
        return self._embedder

    async def _create_embedder(self) -> "UnifiedEmbedder":
        """创建 Embedder（本地优先，API 回退）"""
        from .built_in.embedders import UnifiedEmbedder

        config = self._config.built_in.embedding

        # 尝试加载本地模型
        try:
            embedder = await UnifiedEmbedder.create_local(config)
            logger.info(f"Embedder loaded: {config.model} on {config.device}")
            return embedder
        except Exception as e:
            logger.warning(f"Failed to load local embedder: {e}")

        # 尝试 API 回退
        if config.api_fallback:
            provider = config.api_fallback.provider
            provider_config = self._config.providers.get(provider)

            api_key = config.api_fallback.api_key or (
                provider_config.api_key if provider_config else None
            )
            api_base = config.api_fallback.api_base or (
                provider_config.api_base if provider_config else None
            )

            if api_key:
                logger.info(f"Falling back to API embedder: {provider}")
                return await UnifiedEmbedder.create_api(
                    config, api_key=api_key, api_base=api_base
                )

        raise EmbedderUnavailableError(
            "No embedder available. Vector search features will be disabled. "
            "Install FlagEmbedding (pip install FlagEmbedding) or configure "
            "API fallback in built_in.embedding.api_fallback"
        )


# 全局单例
_registry: Optional[ModelRegistry] = None


def get_model_registry() -> ModelRegistry:
    """获取模型注册中心"""
    if _registry is None:
        raise RuntimeError("ModelRegistry not initialized")
    return _registry


async def init_model_registry(config) -> ModelRegistry:
    """初始化模型注册中心"""
    global _registry
    _registry = ModelRegistry(config)
    # 预热主 LLM
    await _registry.get_llm()
    logger.info("ModelRegistry initialized")
    return _registry
