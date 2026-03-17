"""KnowledgeHub 核心类"""

from typing import Optional, Any
from loguru import logger

from .config import KnowledgeHubConfig, LLMConfig, CacheConfig, SourceConfig
from .processors import DirectProcessor
from .processors.base import KnowledgeResult
from .connectors import LocalConnector
from .storage.cache import SimpleCache
from .storage.vector import VectorStoreWrapper


class KnowledgeHub:
    """企业知识中枢 - 可插拔独立模块"""

    def __init__(self, config: KnowledgeHubConfig = None):
        self.config = config or KnowledgeHubConfig()
        self._initialized = False

        # 存储层
        self.cache = SimpleCache(config=self.config.cache)
        self.vector_store = VectorStoreWrapper(self.config.storage_dir)

        # 接入器
        self.connectors = {}

        # 处理器
        self.processors = {}

    async def initialize(self):
        """初始化模块"""
        if self._initialized:
            return

        logger.info("Initializing KnowledgeHub...")

        # 初始化接入器
        for source in self.config.sources:
            if source.enabled and source.source_type == "local":
                self.connectors[source.id] = LocalConnector(source.config)

        # 初始化处理器
        self.processors["direct"] = DirectProcessor({"top_k": 10})

        self._initialized = True

    async def retrieve(self, query: str, mode: str = None, **options) -> KnowledgeResult:
        """检索知识"""
        await self.initialize()

        mode = mode or self.config.default_mode
        processor = self.processors.get(mode) or self.processors.get("direct")

        if processor is None:
            # Fallback to direct if processor not found
            processor = self.processors.get("direct")
            if processor is None:
                return KnowledgeResult(
                    content="知识模块未正确初始化",
                    sources=[],
                    mode="error"
                )

        return await processor.process(query, **options)

    async def query_database(self, question: str) -> dict:
        """智能数据库查询"""
        # TODO: 实现数据库查询
        return {"error": "数据库查询功能尚未实现"}

    def add_source(self, source: SourceConfig):
        """添加知识源"""
        if source.source_type == "local" and source.enabled:
            self.connectors[source.id] = LocalConnector(source.config)
        self.config.sources.append(source)

    def get_sources(self) -> list[SourceConfig]:
        """获取所有知识源"""
        return self.config.sources

    async def sync_source(self, source_id: str) -> int:
        """同步知识源"""
        connector = self.connectors.get(source_id)
        if connector and hasattr(connector, 'sync'):
            return await connector.sync()
        return 0
