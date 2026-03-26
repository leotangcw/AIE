# backend/core/built_in/embedders.py

"""统一 Embedder - BGE-M3 本地优先，支持 API 回退"""

import os
import numpy as np
from typing import Optional, Any
from loguru import logger


class UnifiedEmbedder:
    """统一 Embedder - BGE-M3 本地优先，支持 API 回退"""

    def __init__(self, dimension: int = 1024):
        self._dimension = dimension
        self._local_model: Optional[Any] = None
        self._api_client: Optional[dict] = None

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
        """加载 BGE-M3 本地模型"""
        # 设置 ModelScope 镜像（国内加速）
        if config.use_modelscope:
            endpoint = config.modelscope_endpoint or "https://hf-mirror.com"
            os.environ["HF_ENDPOINT"] = endpoint
            logger.debug(f"HF mirror set: {endpoint}")

        # 尝试 FlagEmbedding
        try:
            from FlagEmbedding import BGEM3FlagModel

            device = self._resolve_device(config.device)
            self._local_model = BGEM3FlagModel(
                config.model,
                use_fp16=config.use_fp16,
                device=device,
            )
            logger.info(f"BGE-M3 loaded on {device}")
            return

        except ImportError:
            logger.warning("FlagEmbedding not installed, trying sentence-transformers")

        # 回退到 sentence-transformers
        try:
            from sentence_transformers import SentenceTransformer

            device = self._resolve_device(config.device)
            self._local_model = SentenceTransformer(config.model, device=device)
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
        if self._local_model is not None:
            return await self._embed_local(texts)
        elif self._api_client is not None:
            return await self._embed_api(texts)
        else:
            raise RuntimeError("No embedder available")

    async def _embed_local(self, texts: list[str]) -> np.ndarray:
        """本地嵌入"""
        if hasattr(self._local_model, 'encode'):
            # FlagEmbedding BGEM3
            output = self._local_model.encode(
                texts,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )
            return output['dense_vecs']
        else:
            # sentence-transformers
            embeddings = self._local_model.encode(texts)
            return np.array(embeddings, dtype=np.float32)

    async def _embed_api(self, texts: list[str]) -> np.ndarray:
        """API 嵌入"""
        import litellm

        response = await litellm.aembedding(
            model=f"openai/{self._api_client['model']}",
            input=texts,
            api_key=self._api_client['api_key'],
            api_base=self._api_client['api_base'],
        )

        embeddings = [item["embedding"] for item in response.data]
        return np.array(embeddings, dtype=np.float32)

    async def embed_single(self, text: str) -> np.ndarray:
        """嵌入单个文本"""
        result = await self.embed([text])
        return result[0]
