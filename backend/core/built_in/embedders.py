# backend/core/built_in/embedders.py

"""统一 Embedder - BGE-M3 本地优先，支持 API 回退"""

import asyncio
import os
import threading
import numpy as np
from typing import Optional, Any
from loguru import logger


class UnifiedEmbedder:
    """统一 Embedder - BGE-M3 本地优先，支持 API 回退"""

    def __init__(self, dimension: int = 1024):
        self._dimension = dimension
        self._local_model: Optional[Any] = None
        self._api_client: Optional[dict] = None
        self._model_lock = threading.Lock()  # Thread safety for model loading

    @property
    def dimension(self) -> int:
        return self._dimension

    @classmethod
    async def create_local(cls, config) -> "UnifiedEmbedder":
        """创建本地 Embedder"""
        instance = cls(config.dimension)
        await instance._load_local_model(config)
        return instance

    @classmethod
    async def create_api(
        cls,
        config,
        api_key: str,
        api_base: Optional[str] = None,
    ) -> "UnifiedEmbedder":
        """创建 API Embedder"""
        instance = cls(config.dimension)
        instance._api_client = {
            "provider": config.api_fallback.provider if config.api_fallback else "openai",
            "model": config.api_fallback.model if config.api_fallback else "text-embedding-v3",
            "api_key": api_key,
            "api_base": api_base,
        }
        logger.info(f"API embedder configured: {instance._api_client['provider']}/{instance._api_client['model']}")
        return instance

    async def _load_local_model(self, config):
        """加载 BGE-M3 本地模型（线程安全）"""
        # Double-check pattern for thread safety
        if self._local_model is not None:
            return

        with self._model_lock:
            if self._local_model is not None:
                return

            # 设置缓存目录（关键：避免每次重新下载）
            cache_dir = config.get_cache_dir() if hasattr(config, 'get_cache_dir') else getattr(config, 'cache_dir', None)
            if cache_dir:
                os.environ["HF_HOME"] = cache_dir
                os.environ["TRANSFORMERS_CACHE"] = cache_dir
                os.environ["SENTENCE_TRANSFORMERS_HOME"] = cache_dir
                logger.info(f"Model cache directory set: {cache_dir}")

            # 设置 ModelScope 镜像（国内加速）
            if config.use_modelscope:
                endpoint = config.modelscope_endpoint or "https://hf-mirror.com"
                os.environ["HF_ENDPOINT"] = endpoint
                logger.debug(f"HF mirror set: {endpoint}")

            # 尝试 FlagEmbedding
            try:
                from FlagEmbedding import BGEM3FlagModel

                device = self._resolve_device(config.device)

                # CPU/GPU-bound operation - run in thread pool
                def load_bge_model():
                    return BGEM3FlagModel(
                        config.model,
                        use_fp16=config.use_fp16,
                        device=device,
                        cache_dir=cache_dir,  # 添加缓存目录
                    )

                self._local_model = await asyncio.to_thread(load_bge_model)
                logger.info(f"BGE-M3 loaded on {device}")
                return

            except ImportError:
                logger.warning("FlagEmbedding not installed, trying sentence-transformers")

            # 回退到 sentence-transformers
            try:
                from sentence_transformers import SentenceTransformer

                device = self._resolve_device(config.device)

                # CPU/GPU-bound operation - run in thread pool
                def load_st_model():
                    return SentenceTransformer(
                        config.model,
                        device=device,
                        cache_folder=cache_dir,  # 添加缓存目录
                    )

                self._local_model = await asyncio.to_thread(load_st_model)
                logger.info(f"Embedder loaded via sentence-transformers on {device}")
            except ImportError:
                raise ImportError(
                    "No embedding library available. "
                    "Install FlagEmbedding (pip install FlagEmbedding) or "
                    "sentence-transformers (pip install sentence-transformers)"
                )

    def _resolve_device(self, device: str) -> str:
        """解析设备"""
        if device == "auto":
            try:
                import torch
                return "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                return "cpu"
        return device

    async def embed(self, texts: list[str]) -> np.ndarray:
        """生成嵌入向量"""
        if not texts:
            raise ValueError("texts cannot be empty")

        if self._local_model is not None:
            return await self._embed_local(texts)
        elif self._api_client is not None:
            return await self._embed_api(texts)
        else:
            raise RuntimeError("No embedder available")

    async def _embed_local(self, texts: list[str]) -> np.ndarray:
        """本地嵌入（非阻塞）"""
        model = self._local_model

        def _do_encode():
            if hasattr(model, 'encode'):
                # FlagEmbedding BGEM3
                output = model.encode(
                    texts,
                    return_dense=True,
                    return_sparse=False,
                    return_colbert_vecs=False,
                )
                return output['dense_vecs']
            else:
                # sentence-transformers
                embeddings = model.encode(texts)
                return np.array(embeddings, dtype=np.float32)

        return await asyncio.to_thread(_do_encode)

    async def _embed_api(self, texts: list[str]) -> np.ndarray:
        """API 嵌入"""
        import litellm

        # Use provider from config, not hardcoded
        provider = self._api_client.get("provider", "openai")
        model_name = self._api_client["model"]

        # Build model string based on provider
        if provider in ("azure", "openai"):
            model_str = f"{provider}/{model_name}"
        else:
            model_str = f"openai/{model_name}"  # Default to OpenAI-compatible

        response = await litellm.aembedding(
            model=model_str,
            input=texts,
            api_key=self._api_client['api_key'],
            api_base=self._api_client.get('api_base'),
        )

        embeddings = [item["embedding"] for item in response.data]
        return np.array(embeddings, dtype=np.float32)

    async def embed_single(self, text: str) -> np.ndarray:
        """嵌入单个文本"""
        result = await self.embed([text])
        return result[0]
