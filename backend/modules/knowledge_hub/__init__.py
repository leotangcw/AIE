"""KnowledgeHub - 企业知识中枢模块

提供多元化的知识聚合和访问能力，支持：
- 本地文件知识源
- 数据库知识源
- 网络搜索知识源

检索模式：
- direct: 关键词检索
- vector: 向量检索
- hybrid: 混合检索
- llm: LLM 处理
"""

from .hub import KnowledgeHub
from .config import (
    KnowledgeHubConfig,
    LLMConfig,
    CacheConfig,
    SourceConfig,
    LocalSourceConfig,
    DatabaseSourceConfig,
    WebSearchSourceConfig,
    ChunkConfig,
    ChunkStrategy,
    RetrievalMode,
    RetrievalConfig,
    RerankConfig,
    VectorStoreConfig,
)
from .reranker import Reranker, RerankResult, create_reranker

__all__ = [
    # 核心类
    "KnowledgeHub",
    # 配置类
    "KnowledgeHubConfig",
    "LLMConfig",
    "CacheConfig",
    "SourceConfig",
    "LocalSourceConfig",
    "DatabaseSourceConfig",
    "WebSearchSourceConfig",
    "ChunkConfig",
    "ChunkStrategy",
    "RetrievalMode",
    "RetrievalConfig",
    "RerankConfig",
    "VectorStoreConfig",
    # 重排序
    "Reranker",
    "RerankResult",
    "create_reranker",
]
