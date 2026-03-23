"""Embedding generation with multiple provider support.

Default: BAAI/bge-m3 (via local path or modelscope)
Supports local model paths for offline operation.
Uses modelscope as default download source (via MODELSCOPE_SDK_DEBUG=0).
"""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol

import numpy as np
from loguru import logger


# Default local models directory (AIE workspace)
DEFAULT_MODELS_DIR = Path(__file__).parent.parent.parent.parent / "models"


class Embedder(Protocol):
    """Protocol for embedding providers."""

    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        ...


class BaseEmbedder(ABC):
    """Base class for embedding providers."""

    def __init__(self, model: str, dim: int, batch_size: int = 32):
        self.model = model
        self.dim = dim
        self.batch_size = batch_size

    @abstractmethod
    def _call_api(self, texts: list[str]) -> list[list[float]]:
        """Call the embedding API."""
        ...

    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        return self._call_api([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts with batching."""
        if not texts:
            return []

        results = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            try:
                batch_results = self._call_api(batch)
                results.extend(batch_results)
            except Exception as e:
                logger.error(f"Error generating embeddings for batch {i}: {e}")
                # Return zero vectors for failed batch
                results.extend([[0.0] * self.dim for _ in batch])

        return results


class BGEEmbedder(BaseEmbedder):
    """
    BGE (BAAI General Embedding) model using sentence-transformers.

    Supports:
    - Local model path (e.g., /path/to/bge-m3)
    - Model ID (will download from modelscope if not cached)

    Default model: BAAI/bge-m3 (1024 dim)
    """

    def __init__(
        self,
        model: str = "BAAI/bge-m3",
        dim: int = 1024,
        batch_size: int = 32,
        device: str = "cpu",
        local_path: str | None = None,
    ):
        super().__init__(model, dim, batch_size)
        self.device = device
        self.local_path = local_path
        self._model = None

    def _get_model(self):
        """Lazy load sentence-transformers model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                # Determine model path
                model_path = self._resolve_model_path()

                logger.info(f"Loading embedding model from: {model_path} on {self.device}")
                self._model = SentenceTransformer(str(model_path), device=self.device)
                logger.info(f"Embedding model loaded successfully")
            except ImportError:
                raise ImportError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )
        return self._model

    def _resolve_model_path(self) -> Path:
        """
        Resolve model path with the following priority:
        1. Explicit local_path parameter
        2. LOCAL_MODELS_DIR/model_name (e.g., models/BAAI/bge-m3)
        3. Default modelscope cache location
        4. Raw model name (for modelscope download)
        """
        # 1. Check explicit local path
        if self.local_path:
            local = Path(self.local_path)
            if local.exists():
                return local

        # 2. Check DEFAULT_MODELS_DIR
        model_dir = DEFAULT_MODELS_DIR / self.model
        if model_dir.exists():
            return model_dir

        # 3. Check if model name is already a valid local path
        if Path(self.model).exists():
            return Path(self.model)

        # 4. Return model name for modelscope to download
        # Configure modelscope as default source
        return Path(self.model)

    def _call_api(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using local BGE model."""
        model = self._get_model()
        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=self.batch_size,
            show_progress_bar=False,
        )
        return embeddings.astype(np.float32).tolist()


class OpenAIEmbedder(BaseEmbedder):
    """OpenAI embedding provider (fallback option)."""

    def __init__(self, model: str = "text-embedding-3-small", dim: int = 1536, **kwargs):
        super().__init__(model, dim, **kwargs)
        self.client = None

    def _get_client(self):
        """Lazy load OpenAI client."""
        if self.client is None:
            from openai import OpenAI
            self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        return self._client

    def _call_api(self, texts: list[str]) -> list[list[float]]:
        """Call OpenAI embeddings API."""
        client = self._get_client()
        response = client.embeddings.create(
            model=self.model,
            input=texts,
        )
        return [item.embedding for item in response.data]


class JinaEmbedder(BaseEmbedder):
    """Jina AI embedding provider (fallback option)."""

    def __init__(
        self,
        model: str = "jina-embeddings-v3",
        dim: int = 1024,
        api_key: str | None = None,
        **kwargs,
    ):
        super().__init__(model, dim, **kwargs)
        self.api_key = api_key or os.environ.get("JINA_API_KEY")
        self.batch_size = min(self.batch_size, 16)  # Jina has lower batch limit

    def _call_api(self, texts: list[str]) -> list[list[float]]:
        """Call Jina embeddings API."""
        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": self.model,
            "input": texts,
            "task": "retrieval.passage",
        }

        response = httpx.post(
            "https://api.jina.ai/v1/embeddings",
            headers=headers,
            json=data,
            timeout=60.0,
        )
        response.raise_for_status()
        result = response.json()
        return [item["embedding"] for item in result["data"]]


class LocalEmbedder(BaseEmbedder):
    """
    Generic local embedding model using sentence-transformers.

    Use this for custom local models like:
    - moka-ai/m3e-base
    - shibing624/text2vec-base-chinese
    - etc.
    """

    def __init__(
        self,
        model: str = "all-MiniLM-L6-v2",
        dim: int = 384,
        device: str = "cpu",
        **kwargs,
    ):
        super().__init__(model, dim, **kwargs)
        self.device = device
        self._model = None

    def _get_model(self):
        """Lazy load sentence-transformers model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading local embedding model: {self.model} on {self.device}")
                self._model = SentenceTransformer(self.model, device=self.device)
            except ImportError:
                raise ImportError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )
        return self._model

    def _call_api(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using local model."""
        model = self._get_model()
        embeddings = model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()


class FallbackEmbedder(BaseEmbedder):
    """
    Fallback embedder using simple hash-based vectors.

    Used when primary embedder fails (e.g., network unavailable).
    Produces deterministic but not semantically meaningful embeddings.
    Allows the memory system to function for testing purposes.
    """

    def __init__(self, model: str = "fallback", dim: int = 512, batch_size: int = 32, **kwargs):
        super().__init__(model, dim, batch_size)

    def _call_api(self, texts: list[str]) -> list[list[float]]:
        """Generate deterministic hash-based embeddings."""
        import hashlib
        results = []
        for text in texts:
            # Create a deterministic seed from text hash
            text_hash = hashlib.sha256(text.encode()).digest()
            # Use hash bytes to generate pseudo-random but deterministic vector
            vec = []
            for i in range(self.dim):
                byte_idx = i % len(text_hash)
                vec.append((text_hash[byte_idx] / 127.5) - 1.0)  # Normalize to [-1, 1]
            results.append(vec)
        return results


def create_embedder(
    provider: str,
    model: str | None = None,
    dim: int | None = None,
    local_path: str | None = None,
    **kwargs,
) -> Embedder:
    """
    Factory function to create an embedder by provider name.

    Providers:
    - "bge" (default): BAAI/bge-m3, local model or modelscope download
    - "local": Custom sentence-transformers model (local path)
    - "openai": OpenAI embeddings API
    - "jina": Jina AI embeddings API
    - "fallback": Simple hash-based embedder (no network required)

    For local model support:
    - Set local_path to direct model path
    - Or place model in {AIE}/models/{model_name}/
    """
    providers = {
        # bge: use local path if available, otherwise bge-m3 (1024 dim)
        "bge": (BGEEmbedder, "BAAI/bge-m3", 1024),
        # local: custom local model
        "local": (LocalEmbedder, model or "all-MiniLM-L6-v2", dim or 384),
        "openai": (OpenAIEmbedder, model or "text-embedding-3-small", dim or 1536),
        "jina": (JinaEmbedder, model or "jina-embeddings-v3", dim or 1024),
        "fallback": (FallbackEmbedder, None, dim or 512),
    }

    if provider not in providers:
        raise ValueError(
            f"Unknown embedder provider: {provider}. "
            f"Available: {list(providers.keys())}"
        )

    embedder_class, default_model, default_dim = providers[provider]
    actual_model = model or default_model
    actual_dim = dim if dim is not None else default_dim

    logger.info(f"Creating embedder: provider={provider}, model={actual_model}, dim={actual_dim}, local_path={local_path}")

    try:
        return embedder_class(model=actual_model, dim=actual_dim, local_path=local_path, **kwargs)
    except Exception as e:
        logger.warning(f"Failed to create {provider} embedder: {e}")
        if provider != "fallback":
            logger.info("Falling back to hash-based embedder")
            return FallbackEmbedder(dim=actual_dim or 512)
        raise
