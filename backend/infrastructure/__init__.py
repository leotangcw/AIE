# backend/infrastructure/__init__.py

"""基础设施层"""

import asyncio
import threading
from typing import Optional
from loguru import logger

from .database import SQLiteDatabase
from .vector_store import SQLiteVectorStore
from .cache import SQLiteCache


class Infrastructure:
    """共享基础设施"""

    def __init__(self, config):
        self._config = config
        self._db: Optional[SQLiteDatabase] = None
        self._vector_store: Optional[SQLiteVectorStore] = None
        self._cache: Optional[SQLiteCache] = None
        self._lock = asyncio.Lock()  # Thread safety lock

    async def get_database(self) -> SQLiteDatabase:
        """获取数据库连接"""
        if self._db is None:
            async with self._lock:
                if self._db is None:  # Double-check after lock
                    self._db = SQLiteDatabase(self._config.database.path)
        return self._db

    async def get_vector_store(self) -> SQLiteVectorStore:
        """获取向量存储（统一 1024 维）"""
        if self._vector_store is None:
            async with self._lock:
                if self._vector_store is None:  # Double-check after lock
                    db = await self.get_database()
                    self._vector_store = SQLiteVectorStore(db, dimension=1024)
                    await self._vector_store.initialize()
        return self._vector_store

    async def get_cache(self) -> SQLiteCache:
        """获取缓存"""
        if self._cache is None:
            async with self._lock:
                if self._cache is None:  # Double-check after lock
                    db = await self.get_database()
                    self._cache = SQLiteCache(db)
                    await self._cache.initialize()
        return self._cache

    async def initialize(self):
        """初始化基础设施"""
        await self.get_database()
        await self.get_vector_store()
        await self.get_cache()
        logger.info("Infrastructure initialized")

    async def finalize(self):
        """清理资源"""
        if self._db:
            await self._db.close()
        self._db = None
        self._vector_store = None
        self._cache = None
        logger.info("Infrastructure finalized")


# 全局单例
_infra: Optional[Infrastructure] = None
_infra_lock = threading.Lock()


def get_infrastructure() -> Infrastructure:
    """获取基础设施"""
    with _infra_lock:
        if _infra is None:
            raise RuntimeError("Infrastructure not initialized")
        return _infra


async def init_infrastructure(config) -> Infrastructure:
    """初始化基础设施"""
    global _infra
    with _infra_lock:
        if _infra is not None:
            return _infra  # Already initialized
        _infra = Infrastructure(config)
    await _infra.initialize()
    return _infra


__all__ = [
    "SQLiteDatabase",
    "SQLiteVectorStore",
    "SQLiteCache",
    "Infrastructure",
    "get_infrastructure",
    "init_infrastructure",
]
