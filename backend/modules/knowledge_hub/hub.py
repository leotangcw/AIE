"""KnowledgeHub 核心类

企业知识聚合配置入口，提供多元化的知识访问能力。
"""

import hashlib
from dataclasses import asdict
from typing import Optional, Any
from pathlib import Path
from loguru import logger

from .config import (
    KnowledgeHubConfig,
    SourceConfig,
    RetrievalMode,
    RerankConfig,
)
from .processors import (
    DirectProcessor,
    LLMProcessor,
    VectorProcessor,
    HybridProcessor,
    GraphProcessor,
)
from .processors.base import KnowledgeResult
from .connectors import LocalConnector
from .connectors.database import DatabaseConnector
from .connectors.web_search import WebSearchConnector
from .storage.cache import SimpleCache
from .storage.vector import VectorStoreWrapper
from .reranker import Reranker, create_reranker


class KnowledgeHub:
    """企业知识中枢 - 可插拔独立模块

    支持多种知识源：
    - 本地文件
    - 数据库
    - 网络搜索

    支持多种检索模式：
    - direct: 关键词检索
    - vector: 向量检索
    - hybrid: 混合检索
    - llm: LLM 处理
    """

    def __init__(self, config: KnowledgeHubConfig = None):
        self.config = config or KnowledgeHubConfig()
        self._initialized = False

        # 存储层
        storage_dir = Path(self.config.storage_dir)
        storage_dir.mkdir(parents=True, exist_ok=True)

        self.cache = SimpleCache(config=self.config.cache.model_dump())
        self.vector_store = VectorStoreWrapper(str(storage_dir))

        # 连接器
        self.connectors: dict[str, Any] = {}

        # 处理器
        self.processors: dict[str, Any] = {}

        # 重排序器
        self.reranker: Reranker | None = None

    async def initialize(self):
        """初始化模块"""
        if self._initialized:
            return

        logger.info("Initializing KnowledgeHub...")

        # 初始化连接器
        await self._init_connectors()

        # 初始化处理器
        self._init_processors()

        # 初始化重排序器
        if self.config.default_retrieval.rerank.enabled:
            self.reranker = create_reranker(self.config.default_retrieval.rerank)

        self._initialized = True
        logger.info(f"KnowledgeHub initialized with {len(self.connectors)} connectors")

    async def _init_connectors(self):
        """初始化所有知识源连接器"""
        for source in self.config.sources:
            if not source.enabled:
                continue

            connector = await self._create_connector(source)
            if connector:
                self.connectors[source.id] = connector
                logger.debug(f"Initialized connector: {source.id} ({source.source_type})")

    async def _create_connector(self, source: SourceConfig):
        """创建知识源连接器"""
        try:
            if source.source_type == "local":
                config = source.local.model_dump() if source.local else source.config
                return LocalConnector(config)

            elif source.source_type == "database":
                config = source.database.model_dump() if source.database else source.config
                connector = DatabaseConnector(config)
                if await connector.connect():
                    return connector
                logger.warning(f"Failed to connect database: {source.id}")
                return None

            elif source.source_type == "web_search":
                config = source.web_search.model_dump() if source.web_search else source.config
                return WebSearchConnector(config)

            else:
                logger.warning(f"Unknown source type: {source.source_type}")
                return None

        except Exception as e:
            logger.error(f"Failed to create connector {source.id}: {e}")
            return None

    def _init_processors(self):
        """初始化所有处理器"""
        config_dict = self.config.model_dump()

        self.processors[RetrievalMode.DIRECT] = DirectProcessor(config_dict, self)
        self.processors[RetrievalMode.VECTOR] = VectorProcessor(config_dict, self)
        self.processors[RetrievalMode.HYBRID] = HybridProcessor(config_dict, self)
        self.processors[RetrievalMode.LLM] = LLMProcessor(
            {**config_dict, **self.config.llm.model_dump()},
            self
        )

        # GraphRAG 处理器（可选）
        try:
            from .processors.graph import GraphProcessor
            self.processors[RetrievalMode.GRAPH] = GraphProcessor(config_dict, self)
            logger.debug("GraphProcessor initialized")
        except ImportError:
            logger.debug("GraphProcessor not available (GraphRAG not installed)")

    async def retrieve(
        self,
        query: str,
        mode: str | RetrievalMode = None,
        use_cache: bool = True,
        **options,
    ) -> KnowledgeResult:
        """检索知识

        Args:
            query: 查询文本
            mode: 检索模式 (direct/vector/hybrid/llm)
            use_cache: 是否使用缓存
            **options: 其他选项

        Returns:
            KnowledgeResult: 检索结果
        """
        if not self._initialized:
            await self.initialize()

        # 确定检索模式
        if mode is None:
            mode = self.config.default_mode
        if isinstance(mode, str):
            mode = RetrievalMode(mode)

        # 检查缓存
        if use_cache and self.config.cache.cache_queries:
            cache_key = self._cache_key(query, mode.value, options)
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for query: {query[:50]}...")
                return KnowledgeResult(**cached)

        # 获取处理器
        processor = self.processors.get(mode)
        if processor is None:
            logger.warning(f"Processor not found for mode: {mode}, falling back to direct")
            processor = self.processors.get(RetrievalMode.DIRECT)

        if processor is None:
            return KnowledgeResult(
                content="知识模块未正确初始化",
                sources=[],
                mode="error",
            )

        # 执行检索
        result = await processor.process(query, **options)

        # 重排序
        if self.reranker and result.sources:
            reranked = self.reranker.rerank(
                [{"content": s.get("content", ""), **s} for s in result.sources],
                query,
            )
            result.sources = [
                {
                    "content": r.content,
                    "source": r.source,
                    "score": r.final_score,
                    "original_score": r.original_score,
                    "score_breakdown": r.score_breakdown,
                }
                for r in reranked
            ]

        # 缓存结果
        if use_cache and self.config.cache.cache_queries:
            self.cache.set(cache_key, asdict(result))

        return result

    def _cache_key(self, query: str, mode: str, options: dict) -> str:
        """生成缓存键"""
        key_str = f"{mode}:{query}:{sorted(options.items())}"
        return hashlib.md5(key_str.encode()).hexdigest()

    async def query_database(self, question: str, source_id: str = None) -> dict:
        """智能数据库查询

        Args:
            question: 自然语言问题
            source_id: 指定数据库源 ID（可选）

        Returns:
            dict: 查询结果
        """
        if not self._initialized:
            await self.initialize()

        # 查找数据库连接器
        db_connectors = [
            (sid, c) for sid, c in self.connectors.items()
            if isinstance(c, DatabaseConnector)
        ]

        if not db_connectors:
            return {"error": "没有配置数据库知识源"}

        # 使用指定的或第一个数据库连接器
        if source_id:
            connector = self.connectors.get(source_id)
            if not connector or not isinstance(connector, DatabaseConnector):
                return {"error": f"数据库源 {source_id} 不存在"}
        else:
            source_id, connector = db_connectors[0]

        return await connector.execute_query(question)

    def add_source(self, source: SourceConfig) -> bool:
        """添加知识源

        Args:
            source: 知识源配置

        Returns:
            bool: 是否成功
        """
        try:
            # 创建连接器
            import asyncio
            connector = asyncio.get_event_loop().run_until_complete(
                self._create_connector(source)
            )

            if connector:
                self.connectors[source.id] = connector
                self.config.sources.append(source)
                logger.info(f"Added knowledge source: {source.id}")
                return True
            else:
                logger.warning(f"Failed to create connector for source: {source.id}")
                return False

        except Exception as e:
            logger.error(f"Failed to add source {source.id}: {e}")
            return False

    def remove_source(self, source_id: str) -> bool:
        """移除知识源

        Args:
            source_id: 知识源 ID

        Returns:
            bool: 是否成功
        """
        if source_id in self.connectors:
            connector = self.connectors.pop(source_id)
            if hasattr(connector, "disconnect"):
                import asyncio
                asyncio.get_event_loop().run_until_complete(connector.disconnect())
            logger.info(f"Removed knowledge source: {source_id}")
            return True

        # 从配置中移除
        self.config.sources = [s for s in self.config.sources if s.id != source_id]
        return True

    def get_sources(self) -> list[SourceConfig]:
        """获取所有知识源配置"""
        return self.config.sources

    def get_source(self, source_id: str) -> SourceConfig | None:
        """获取指定知识源配置"""
        return self.config.get_source(source_id)

    async def sync_source(self, source_id: str) -> int:
        """同步知识源

        Args:
            source_id: 知识源 ID

        Returns:
            int: 同步的分段数量
        """
        connector = self.connectors.get(source_id)
        if not connector:
            logger.warning(f"Source not found: {source_id}")
            return 0

        if not hasattr(connector, "sync"):
            logger.warning(f"Source {source_id} does not support sync")
            return 0

        count = await connector.sync()

        # 如果有向量存储，同步到向量索引
        if count > 0 and self.vector_store:
            await self._sync_to_vector_store(source_id, connector)

        return count

    async def _sync_to_vector_store(self, source_id: str, connector):
        """将知识源同步到向量存储"""
        try:
            docs = await connector.fetch()
            added = 0

            for doc in docs:
                chunks = doc.get("chunks", [])
                if not chunks:
                    chunks = [{"content": c, "metadata": {}} for c in doc.get("content", [])]

                for chunk in chunks:
                    content = chunk.get("content", "") if isinstance(chunk, dict) else chunk
                    if not content:
                        continue

                    self.vector_store.add(
                        content=content,
                        metadata=chunk.get("metadata", {}) if isinstance(chunk, dict) else {},
                        source_type="knowledge",
                        source_id=source_id,
                    )
                    added += 1

            logger.info(f"Synced {added} chunks to vector store for source {source_id}")

        except Exception as e:
            logger.error(f"Failed to sync to vector store: {e}")

    async def refresh_cache(self, cache_type: str = "all"):
        """刷新缓存

        Args:
            cache_type: 缓存类型 (all/queries/documents)
        """
        if cache_type in ["all", "queries"]:
            self.cache.clear()
            logger.info("Cleared query cache")

    def save_config(self, path: str = None):
        """保存配置

        Args:
            path: 配置文件路径（可选）
        """
        config_path = path or str(Path(self.config.storage_dir) / "config.json")
        self.config.save(config_path)
        logger.info(f"Config saved to {config_path}")

    @classmethod
    def load(cls, path: str) -> "KnowledgeHub":
        """从配置文件加载

        Args:
            path: 配置文件路径

        Returns:
            KnowledgeHub: 实例
        """
        config = KnowledgeHubConfig.load(path)
        return cls(config)
