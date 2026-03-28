# AIE 模型提供商架构设计

> 设计日期: 2026-03-26
> 状态: 待审批
> 版本: 1.1

## 1. 背景

### 1.1 当前问题

AIE 系统中存在多套模型配置和实现：

| 模块 | LLM 配置 | Embedding 模型 | 维度 | 方式 |
|------|----------|----------------|------|------|
| Agent 主对话 | 配置文件 | - | - | LiteLLM |
| GraphRAG | 硬编码 OpenAI | text-embedding-3-small | 1536 | 远程 API |
| SQLite Vector | - | bge-small-zh-v1.5 | 512 | 本地 |
| Memory MCP Server | - | bge-m3 | 1024 | 本地 |

> **注意**: GraphRAG 配置文件中声明的维度 (1536) 与实际使用的 text-embedding-v3 (1024) 不一致，这是历史遗留问题。统一后将使用 BGE-M3 的 1024 维。

**问题**：
1. LLM 配置分散，GraphRAG 需要单独传递
2. 三套 Embedding 模型，维度不一致，内存浪费
3. 向量不兼容，无法跨模块检索
4. 缺乏统一的模型管理入口

### 1.2 设计目标

1. **统一模型注册** - 单一配置入口，所有模块共享
2. **统一 Embedding** - BGE-M3 1024 维，本地优先，支持 API 回退
3. **分层架构** - 模型层与基础设施层解耦
4. **懒加载** - 内置模型按需加载，减少启动开销
5. **优雅降级** - 可选模型缺失不影响核心功能

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Application Layer                       │
│  (Agent, Chat, KnowledgeHub, GraphRAG, Memory, Scheduler)   │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    Model Registry (统一入口)                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │ Main LLM    │ │ Sub LLM     │ │ Built-in    │            │
│  │ (Required)  │ │ (Optional)  │ │ Models      │            │
│  └─────────────┘ └─────────────┘ └─────────────┘            │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    Provider Adapters                         │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐    │
│  │ DashScope│ │ OpenAI │ │ Ollama │ │ Local  │ │ Custom │    │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘    │
└─────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    Infrastructure Layer                      │
│  ┌─────────────────────┐  ┌─────────────────────┐          │
│  │ SQLite + Vector     │  │ Built-in Models     │          │
│  │ (存储基础设施)        │  │ (Embed/ASR/TTS/...) │          │
│  └─────────────────────┘  └─────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心原则

1. **单一职责** - 每层只负责自己的功能
2. **依赖注入** - 模块通过注册中心获取依赖
3. **懒加载** - 内置模型首次使用时加载
4. **优雅降级** - 可选功能失败时静默处理

## 3. 模型分类

### 3.1 模型职责矩阵

| 分类 | 模型类型 | 必要性 | 提供方式 | 说明 |
|------|----------|--------|----------|------|
| **核心模型** | Main Agent LLM | 必须 | 远程 API | 主对话、推理 |
| | Sub Agent LLM | 可选 | 远程 API | 后台任务、并行处理 |
| **内置模型** | Embedding (BGE-M3) | 必须 | 本地优先 | 向量检索、知识图谱 |
| | ASR (Whisper) | 可选 | 本地 | 语音识别 |
| | TTS | 可选 | 本地/API | 语音合成 |
| | Image Gen | 可选 | API | 图像生成 |
| **基础设施** | SQLite | 必须 | 内置 | 数据持久化 |
| | SQLite Vector | 必须 | 内置 | 向量存储 |

### 3.2 统一 Embedding 方案

**选定模型**: BAAI/bge-m3

| 特性 | 值 |
|------|-----|
| 向量维度 | 1024 |
| 最大上下文 | 8192 tokens |
| 支持语言 | 100+ (含中英文原生支持) |
| 模型大小 | ~2.2GB (FP16) / ~1.1GB (INT8) |
| MTEB 排名 | 开源模型前列 |

**优先级策略**:
1. 本地 GPU (CUDA) - 最快
2. 本地 CPU - 稍慢但无需网络
3. 远程 API - 用户配置的备选方案

**涉及的模块迁移**:

| 模块 | 原模型 | 原维度 | 迁移后 |
|------|--------|--------|--------|
| GraphRAG | text-embedding-v3 (API) | 1024 | BGE-M3 本地 |
| SQLite Vector | bge-small-zh-v1.5 | 512 | BGE-M3 本地 |
| Memory MCP | bge-m3 | 1024 | 无需迁移 |

## 4. 配置结构

### 4.1 配置模型定义

```python
# backend/core/config.py

from pydantic import BaseModel, Field
from typing import Optional

class ModelConfig(BaseModel):
    """主模型配置"""
    provider: str = "dashscope"
    model: str = "qwen3.5-plus"
    temperature: float = 0.7
    max_tokens: int = 4096

class SubAgentConfig(BaseModel):
    """子代理模型配置"""
    enabled: bool = False
    provider: str = "dashscope"
    model: str = "qwen-turbo"
    max_concurrent: int = 3
    temperature: float = 0.5
    max_tokens: int = 2048

class DatabaseConfig(BaseModel):
    """数据库配置"""
    path: str = Field(default="data/aie.db", description="SQLite 数据库路径")
    echo: bool = False  # SQL 日志

class EmbeddingConfig(BaseModel):
    """Embedding 配置 - 统一 BGE-M3"""
    # 模型设置
    model: str = "BAAI/bge-m3"
    dimension: int = 1024
    max_length: int = 8192

    # 运行设置
    device: str = "auto"  # auto / cpu / cuda
    use_fp16: bool = True
    cache_dir: Optional[str] = None  # 模型缓存目录，默认 ~/.cache/huggingface

    # ModelScope 配置（国内加速）
    use_modelscope: bool = True
    modelscope_endpoint: Optional[str] = None  # 自定义镜像

    # API 回退（可选）- API Key 从 providers 中获取
    api_fallback: Optional[APIFallbackConfig] = None

class APIFallbackConfig(BaseModel):
    """Embedding API 回退配置

    注意: api_key 和 api_base 从 providers 配置中获取，
    此处 provider 字段对应 providers 字典的 key。
    """
    provider: str = "dashscope"  # 对应 providers 字典的 key
    model: str = "text-embedding-v3"
    # 如需覆盖 providers 中的配置，可在此指定
    api_key: Optional[str] = None
    api_base: Optional[str] = None

class BuiltInModelConfig(BaseModel):
    """内置模型配置"""
    embedding: EmbeddingConfig = EmbeddingConfig()
    asr: Optional[ASRConfig] = None
    tts: Optional[TTSConfig] = None
    image_gen: Optional[ImageGenConfig] = None

class ProviderConfig(BaseModel):
    """提供商配置"""
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    default_model: Optional[str] = None

class AppConfig(BaseModel):
    """应用总配置"""
    model: ModelConfig = ModelConfig()
    sub_agent: SubAgentConfig = SubAgentConfig()
    database: DatabaseConfig = DatabaseConfig()
    built_in: BuiltInModelConfig = BuiltInModelConfig()
    providers: dict[str, ProviderConfig] = {}
```

### 4.2 配置文件示例

```yaml
# config.yaml

model:
  provider: dashscope
  model: qwen3.5-plus
  temperature: 0.7
  max_tokens: 4096

sub_agent:
  enabled: true
  provider: dashscope
  model: qwen-turbo
  max_concurrent: 3

built_in:
  embedding:
    model: BAAI/bge-m3
    device: auto
    use_fp16: true
    api_fallback:
      provider: dashscope
      model: text-embedding-v3

providers:
  dashscope:
    api_key: ${DASHSCOPE_API_KEY}
    api_base: https://dashscope.aliyuncs.com/compatible-mode/v1
```

## 5. 模型注册中心

### 5.1 核心实现

```python
# backend/core/model_registry.py

from typing import Any, Optional, TYPE_CHECKING
from loguru import logger

from .config import AppConfig, EmbeddingConfig

if TYPE_CHECKING:
    from .llm_client import LLMClient
    from .built_in.embedders import UnifiedEmbedder

class ModelRegistry:
    """统一模型注册中心

    单例管理：仅使用模块级 _registry 变量，
    不使用类级 _instance 变量避免混淆。
    """

    def __init__(self, config: AppConfig):
        self._config = config

        # LLM 客户端
        self._llm_client: Optional["LLMClient"] = None
        self._sub_llm_client: Optional["LLMClient"] = None

        # 内置模型（懒加载）
        self._embedder: Optional["UnifiedEmbedder"] = None
        self._asr: Optional[Any] = None
        self._tts: Optional[Any] = None

    # ========== LLM ==========

    async def get_llm(self) -> "LLMClient":
        """获取主 LLM 客户端（必须可用）"""
        if self._llm_client is None:
            self._llm_client = await self._create_llm_client(
                self._config.model
            )
        return self._llm_client

    async def get_sub_llm(self) -> Optional["LLMClient"]:
        """获取子代理 LLM（可选）"""
        if not self._config.sub_agent.enabled:
            return None
        if self._sub_llm_client is None:
            self._sub_llm_client = await self._create_llm_client(
                self._config.sub_agent
            )
        return self._sub_llm_client

    async def _create_llm_client(self, config) -> "LLMClient":
        """创建 LLM 客户端"""
        from .llm_client import LLMClient
        provider_config = self._config.providers.get(config.provider)

        return LLMClient(
            provider=config.provider,
            model=config.model,
            api_key=provider_config.api_key if provider_config else None,
            api_base=provider_config.api_base if provider_config else None,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

    # ========== Embedding（统一 BGE-M3）==========

    async def get_embedder(self) -> "UnifiedEmbedder":
        """获取统一 Embedder"""
        if self._embedder is None:
            self._embedder = await self._create_embedder()
        return self._embedder

    async def _create_embedder(self) -> "UnifiedEmbedder":
        """创建 Embedder（本地优先，API 回退）

        加载顺序:
        1. 本地模型 (GPU/CPU)
        2. API 回退（使用 providers 配置中的 API key）
        3. 抛出 EmbedderUnavailableError（非致命，禁用向量功能）
        """
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
                # 从 providers 获取 API 配置
                provider = config.api_fallback.provider
                provider_config = self._config.providers.get(provider)

                # 合并配置：API fallback 中的设置优先
                api_key = config.api_fallback.api_key or (
                    provider_config.api_key if provider_config else None
                )
                api_base = config.api_fallback.api_base or (
                    provider_config.api_base if provider_config else None
                )

                if api_key:
                    logger.info(f"Falling back to API embedder: {provider}")
                    return await UnifiedEmbedder.create_api(
                        config,
                        api_key=api_key,
                        api_base=api_base,
                    )

            # 无可用 Embedder - 抛出非致命错误
            raise EmbedderUnavailableError(
                "No embedder available. Vector search features will be disabled. "
                "Install FlagEmbedding (pip install FlagEmbedding) or configure "
                "API fallback in built_in.embedding.api_fallback"
            )

    # ========== 可选内置模型 ==========

    async def get_asr(self) -> Optional[Any]:
        """获取 ASR 模型（可选，懒加载）"""
        if self._config.built_in.asr is None:
            return None
        if self._asr is None:
            self._asr = await self._load_asr()
        return self._asr

    async def get_tts(self) -> Optional[Any]:
        """获取 TTS 模型（可选，懒加载）"""
        if self._config.built_in.tts is None:
            return None
        if self._tts is None:
            self._tts = await self._load_tts()
        return self._tts


class EmbedderUnavailableError(Exception):
    """Embedder 不可用异常（非致命）"""
    pass


# 全局单例（仅使用模块级变量）

_registry: Optional[ModelRegistry] = None


def get_model_registry() -> ModelRegistry:
    """获取模型注册中心"""
    if _registry is None:
        raise RuntimeError("ModelRegistry not initialized")
    return _registry


async def init_model_registry(config: AppConfig) -> ModelRegistry:
    """初始化模型注册中心"""
    global _registry
    _registry = ModelRegistry(config)

    # 预热必要组件
    await _registry.get_llm()  # 确保 LLM 可用

    logger.info("ModelRegistry initialized")
    return _registry
```

### 5.2 统一 Embedder 实现

```python
# backend/core/built_in/embedders.py

import os
import numpy as np
from typing import Optional, Any
from loguru import logger

from ..config import EmbeddingConfig, APIFallbackConfig

class UnifiedEmbedder:
    """统一 Embedder - BGE-M3 本地优先，支持 API 回退

    特性:
    - 支持 ModelScope 镜像下载（国内加速）
    - 支持 GPU/CPU 自动检测
    - 支持 API 回退
    """

    def __init__(self, dimension: int = 1024):
        self._dimension = dimension
        self._local_model: Optional[Any] = None
        self._api_client: Optional[dict] = None

    @property
    def dimension(self) -> int:
        return self._dimension

    # ========== 创建方法 ==========

    @classmethod
    async def create_local(cls, config: EmbeddingConfig) -> "UnifiedEmbedder":
        """创建本地 Embedder"""
        instance = cls(config.dimension)
        await instance._load_local_model(config)
        return instance

    @classmethod
    async def create_api(
        cls,
        config: EmbeddingConfig,
        api_key: str,
        api_base: Optional[str] = None,
    ) -> "UnifiedEmbedder":
        """创建 API Embedder

        Args:
            config: Embedding 配置
            api_key: API 密钥（从 providers 配置获取）
            api_base: API 基础 URL
        """
        instance = cls(config.dimension)
        await instance._setup_api_client(
            config.api_fallback,
            api_key=api_key,
            api_base=api_base,
        )
        return instance

    # ========== 本地模型加载 ==========

    async def _load_local_model(self, config: EmbeddingConfig):
        """加载 BGE-M3 本地模型

        加载顺序:
        1. 设置 ModelScope 镜像（如果启用）
        2. 尝试 FlagEmbedding 库
        3. 回退到 sentence-transformers
        """
        # 设置 ModelScope 镜像（国内加速）
        if config.use_modelscope:
            await self._setup_modelscope(config)

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
            await self._load_with_sentence_transformers(config)

    async def _setup_modelscope(self, config: EmbeddingConfig):
        """设置 ModelScope 镜像加速

        ModelScope 是国内的模型托管平台，可以加速模型下载。
        设置环境变量后，transformers/FlagEmbedding 会自动使用。
        """
        if config.modelscope_endpoint:
            # 自定义镜像
            os.environ["HF_ENDPOINT"] = config.modelscope_endpoint
        elif config.use_modelscope:
            # 默认 ModelScope 镜像
            os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

        logger.debug(f"Model mirror set: {os.environ.get('HF_ENDPOINT', 'default')}")

    async def _load_with_sentence_transformers(self, config: EmbeddingConfig):
        """使用 sentence-transformers 加载"""
        from sentence_transformers import SentenceTransformer

        device = self._resolve_device(config.device)
        self._local_model = SentenceTransformer(
            config.model,
            device=device,
        )
        logger.info(f"Embedder loaded via sentence-transformers on {device}")

    def _resolve_device(self, device: str) -> str:
        """解析设备"""
        if device == "auto":
            try:
                import torch
                return "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                return "cpu"
        return device

    # ========== API 客户端 ==========

    async def _setup_api_client(
        self,
        config: Optional[APIFallbackConfig],
        api_key: str,
        api_base: Optional[str] = None,
    ):
        """设置 API 客户端

        Args:
            config: API 回退配置
            api_key: API 密钥（必填，从 providers 获取）
            api_base: API 基础 URL
        """
        if config is None:
            raise ValueError("API fallback config is required")

        self._api_client = {
            "provider": config.provider,
            "model": config.model,
            "api_key": api_key,
            "api_base": api_base,
        }
        logger.info(f"API embedder configured: {config.provider}/{config.model}")

    # ========== 嵌入接口 ==========

    async def embed(self, texts: list[str]) -> np.ndarray:
        """生成嵌入向量

        Args:
            texts: 文本列表

        Returns:
            numpy array of shape (len(texts), dimension)
        """
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
```

## 6. 基础设施层

### 6.1 基础设施管理

```python
# backend/infrastructure/__init__.py

from typing import Optional, TYPE_CHECKING
from loguru import logger

from backend.core.config import AppConfig

if TYPE_CHECKING:
    from .database import SQLiteDatabase
    from .vector_store import SQLiteVectorStore
    from .cache import SQLiteCache

class Infrastructure:
    """共享基础设施

    注意: backend/infrastructure/ 是新建目录，
    需要创建以下文件:
    - __init__.py (本文件)
    - database.py (从现有迁移)
    - vector_store.py (从现有迁移并修改为 1024 维)
    - cache.py (新建)
    """

    def __init__(self, config: AppConfig):
        self._config = config
        self._db: Optional["SQLiteDatabase"] = None
        self._vector_store: Optional["SQLiteVectorStore"] = None
        self._cache: Optional["SQLiteCache"] = None

    async def get_database(self) -> "SQLiteDatabase":
        """获取数据库连接"""
        if self._db is None:
            from .database import SQLiteDatabase
            self._db = SQLiteDatabase(self._config.database.path)
        return self._db

    async def get_vector_store(self) -> "SQLiteVectorStore":
        """获取向量存储（统一 1024 维）"""
        if self._vector_store is None:
            from .vector_store import SQLiteVectorStore
            db = await self.get_database()
            self._vector_store = SQLiteVectorStore(
                dimension=1024,  # BGE-M3 维度
                db=db,
            )
        return self._vector_store

    async def get_cache(self) -> "SQLiteCache":
        """获取缓存"""
        if self._cache is None:
            from .cache import SQLiteCache
            db = await self.get_database()
            self._cache = SQLiteCache(db)
        return self._cache

    async def initialize(self):
        """初始化基础设施"""
        await self.get_database()
        await self.get_vector_store()
        logger.info("Infrastructure initialized")

    async def finalize(self):
        """清理资源"""
        if self._db:
            await self._db.close()

# 全局单例

_infra: Optional[Infrastructure] = None

def get_infrastructure() -> Infrastructure:
    """获取基础设施"""
    if _infra is None:
        raise RuntimeError("Infrastructure not initialized")
    return _infra

async def init_infrastructure(config: AppConfig) -> Infrastructure:
    """初始化基础设施"""
    global _infra
    _infra = Infrastructure(config)
    await _infra.initialize()
    return _infra
```

## 7. 模块集成

### 7.1 GraphRAG 集成

```python
# backend/modules/graph_rag/core.py 修改

class GraphRAGClient:
    async def initialize(self) -> bool:
        from backend.core.model_registry import get_model_registry
        from backend.infrastructure import get_infrastructure

        registry = get_model_registry()
        infra = get_infrastructure()

        # 使用统一 LLM
        llm_client = await registry.get_llm()
        self._llm_func = llm_client.complete

        # 使用统一 Embedder
        embedder = await registry.get_embedder()
        self._embed_func = embedder.embed

        # 使用统一向量存储
        self._vector_store = await infra.get_vector_store()

        # 初始化 LightRAG...
```

### 7.2 Agent 模块集成

```python
# backend/modules/agent/memory.py 修改

class AgentMemory:
    async def _get_embedder(self):
        from backend.core.model_registry import get_model_registry
        registry = get_model_registry()
        return await registry.get_embedder()

    async def add_memory(self, content: str, metadata: dict = None):
        embedder = await self._get_embedder()
        embedding = await embedder.embed_single(content)

        # 存储到向量数据库
        await self._vector_store.insert(
            content=content,
            embedding=embedding,
            metadata=metadata,
        )
```

### 7.3 Memory MCP Server 集成

```python
# backend/modules/memory_mcp_server/utils/embedder.py 修改

class UnifiedEmbedderWrapper:
    """适配器：将统一 Embedder 包装为 Memory MCP 接口"""

    async def embed(self, texts: list[str]) -> np.ndarray:
        from backend.core.model_registry import get_model_registry
        registry = get_model_registry()
        embedder = await registry.get_embedder()
        return await embedder.embed(texts)
```

## 8. 迁移策略

### 8.1 阶段规划

| 阶段 | 任务 | 影响 |
|------|------|------|
| Phase 1 | 创建 ModelRegistry 和 Infrastructure | 无 |
| Phase 2 | 迁移 GraphRAG | 需要重新索引 |
| Phase 3 | 迁移 Agent Vector Store | 需要重新索引 |
| Phase 4 | 迁移 Memory MCP Server | 无（已是 BGE-M3） |
| Phase 5 | 清理冗余代码 | - |

### 8.2 数据迁移

对于已有 512 维向量的数据：

```bash
# 提供迁移命令
aie migrate-vectors --namespace default --force
```

**CLI 命令实现**:

```python
# backend/cli/commands/migrate_vectors.py

import asyncio
import click
from pathlib import Path
from datetime import datetime
from loguru import logger

@click.command("migrate-vectors")
@click.option("--namespace", default="default", help="命名空间")
@click.option("--force", is_flag=True, help="强制迁移（覆盖已有数据）")
@click.option("--backup/--no-backup", default=True, help="是否备份原始数据")
def migrate_vectors(namespace: str, force: bool, backup: bool):
    """迁移向量数据从 512 维到 1024 维

    流程:
    1. 检测现有向量维度
    2. 备份原始数据（可选）
    3. 使用新 Embedder 重新生成向量
    4. 更新向量存储
    5. 验证迁移结果
    """
    asyncio.run(_migrate_vectors_async(namespace, force, backup))

async def _migrate_vectors_async(namespace: str, force: bool, backup: bool):
    from backend.core.model_registry import get_model_registry
    from backend.infrastructure import get_infrastructure

    vector_store = await get_infrastructure().get_vector_store()

    # 1. 检测现有向量
    stats = await vector_store.get_stats(namespace)
    if stats.get("dimension") == 1024 and not force:
        click.echo("向量已是 1024 维，无需迁移。使用 --force 强制重新生成。")
        return

    click.echo(f"开始迁移 {stats.get('count', 0)} 条向量数据...")

    # 2. 备份原始数据
    backup_path = None
    if backup:
        backup_path = Path(f"data/backups/{namespace}_{datetime.now():%Y%m%d_%H%M%S}.json")
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        await vector_store.export_backup(namespace, backup_path)
        click.echo(f"备份已保存到: {backup_path}")

    # 3. 获取新 Embedder
    embedder = await get_model_registry().get_embedder()

    # 4. 重新生成向量
    migrated = 0
    async for batch in vector_store.iter_documents(namespace):
        texts = [doc.content for doc in batch]
        new_embeddings = await embedder.embed(texts)

        for doc, embedding in zip(batch, new_embeddings):
            await vector_store.update_embedding(
                doc_id=doc.id,
                embedding=embedding,
                dimension=1024,
            )
            migrated += 1

        click.echo(f"\r已迁移: {migrated}/{stats.get('count', 0)}", nl=False)

    click.echo(f"\n迁移完成: {migrated} 条记录")

    # 5. 验证
    new_stats = await vector_store.get_stats(namespace)
    click.echo(f"新维度: {new_stats.get('dimension')}")

def rollback_vectors(backup_path: Path, namespace: str):
    """回滚到备份数据

    使用方法:
        aie migrate-vectors --rollback data/backups/default_20260326_120000.json
    """
    asyncio.run(_rollback_async(backup_path, namespace))

async def _rollback_async(backup_path: Path, namespace: str):
    from backend.infrastructure import get_infrastructure

    vector_store = await get_infrastructure().get_vector_store()
    await vector_store.import_backup(namespace, backup_path)
    click.echo(f"已从备份恢复: {backup_path}")
```

**备份存储策略**:
- 备份目录: `data/backups/`
- 命名格式: `{namespace}_{YYYYMMDD_HHMMSS}.json`
- 保留期限: 30 天（可配置）
- 清理命令: `aie cleanup-backups --older-than 30d`

### 8.3 GraphRAG 迁移特殊处理

GraphRAG 使用 LightRAG 管理独立的向量存储：

```
memory/
└── graph_rag/
    └── {workspace}/
        └── {namespace}/
            ├── vdb_chunks.json
            ├── vdb_entities.json
            └── vdb_relationships.json
```

**迁移方案**:
1. 删除旧向量文件（LightRAG 会自动重建）
2. 或者使用 `aie rebuild-graph --namespace xxx` 重新索引原始文档

### 8.4 回滚方案

保留旧配置兼容：
- 检测到 512 维向量时，提示用户迁移
- 迁移命令可逆（通过备份恢复）
- 清理冗余代码前确认所有模块正常

## 9. 文件结构

```
backend/
├── core/
│   ├── config.py              # 扩展配置模型（新增 DatabaseConfig 等）
│   ├── model_registry.py      # 新增：模型注册中心
│   ├── llm_client.py          # 新增：LLM 客户端封装
│   └── built_in/
│       ├── __init__.py        # 新增
│       └── embedders.py       # 新增：统一 Embedder
├── infrastructure/            # 新建目录
│   ├── __init__.py            # 新增：基础设施管理
│   ├── database.py            # 从现有迁移
│   ├── vector_store.py        # 从现有迁移，修改为 1024 维
│   └── cache.py               # 新增：缓存
├── cli/
│   └── commands/
│       └── migrate_vectors.py # 新增：迁移命令
└── modules/
    ├── graph_rag/
    │   └── core.py            # 修改：使用 ModelRegistry
    ├── agent/
    │   └── memory.py          # 修改：使用 ModelRegistry
    └── memory_mcp_server/
        └── utils/embedder.py  # 修改：适配器模式
```

**新建目录说明**:
- `backend/infrastructure/` - 基础设施层（全新创建）
- `backend/core/built_in/` - 内置模型管理（全新创建）
- `backend/cli/commands/` - CLI 命令（可能已存在）

## 10. 验收标准

1. **功能验收**
   - [ ] GraphRAG 使用统一 Embedder
   - [ ] Agent Vector Store 使用统一 Embedder
   - [ ] Memory MCP Server 使用统一 Embedder
   - [ ] 支持 API 回退
   - [ ] 验证所有模块使用同一 Embedder 实例（单例检查）
   - [ ] 验证向量维度统一为 1024

2. **性能验收**
   - [ ] 首次加载 BGE-M3 < 10s（CPU）/ < 5s（GPU）
   - [ ] 嵌入速度 > 100 docs/s（GPU）/ > 20 docs/s（CPU）
   - [ ] 内存增量 < 500MB（单模型 vs 多模型）

3. **兼容性验收**
   - [ ] 旧配置文件可正常加载
   - [ ] 迁移命令正常工作
   - [ ] API 回退自动触发（本地模型不可用时）
   - [ ] Embedder 不可用时系统正常降级（非致命错误）

4. **验证命令**
   ```bash
   # 验证 Embedder 单例
   aie check-embedder --verify-singleton

   # 验证向量维度
   aie check-vectors --dimension

   # 测试 API 回退
   aie check-embedder --force-api-fallback
   ```

## 11. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| BGE-M3 下载慢 | 首次启动慢 | ModelScope 镜像（国内加速） |
| 512→1024 数据迁移 | 历史数据需处理 | 提供自动迁移命令 + 备份 |
| 内存不足 | 模型加载失败 | API 回退 + EmbedderUnavailableError（非致命） |
| GraphRAG 向量不兼容 | 知识图谱需重建 | 删除旧向量文件，LightRAG 自动重建 |
| 多 Embedder 实例 | 内存浪费 | 单例模式确保唯一实例 |

**下载加速选项**:
1. **ModelScope**（默认）- 国内直连，约 5-10 MB/s
2. **HuggingFace Mirror** - 设置 `HF_ENDPOINT=https://hf-mirror.com`
3. **手动下载** - 用户预先下载到 `cache_dir`

## 12. 后续优化

1. **模型量化** - INT8 量化减少内存（约 50% 内存节省）
2. **批量优化** - 大批量嵌入性能优化
3. **缓存策略** - 常用文本嵌入缓存（基于 hash）
4. **多语言索引** - 利用 BGE-M3 多语言能力
5. **异步预热** - 启动时后台加载 Embedder，不阻塞服务
