# backend/infrastructure/cache.py

"""简单的 SQLite 缓存模块"""

import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Any
from loguru import logger

from .database import SQLiteDatabase


class SQLiteCache:
    """基于 SQLite 的缓存"""

    def __init__(self, db: SQLiteDatabase, table_name: str = "cache"):
        self._db = db
        self._table_name = table_name
        self._initialized = False

    async def initialize(self) -> "SQLiteCache":
        """初始化缓存表"""
        if self._initialized:
            return self

        await self._db.execute(f"""
            CREATE TABLE IF NOT EXISTS {self._table_name} (
                key TEXT PRIMARY KEY,
                value TEXT,
                expires_at TEXT,
                created_at TEXT
            )
        """)
        self._initialized = True
        logger.debug(f"Cache initialized: {self._table_name}")
        return self

    def _hash_key(self, key: str) -> str:
        """生成缓存 key 的 hash"""
        return hashlib.sha256(key.encode()).hexdigest()

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if not self._initialized:
            await self.initialize()

        hashed_key = self._hash_key(key)
        row = await self._db.fetchone(f"""
            SELECT value, expires_at FROM {self._table_name}
            WHERE key = ?
        """, (hashed_key,))

        if row is None:
            return None

        # 检查过期
        if row["expires_at"]:
            expires_at = datetime.fromisoformat(row["expires_at"])
            if datetime.now() > expires_at:
                await self.delete(key)
                return None

        try:
            return json.loads(row["value"])
        except json.JSONDecodeError:
            return row["value"]

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """设置缓存"""
        if not self._initialized:
            await self.initialize()

        hashed_key = self._hash_key(key)
        value_str = json.dumps(value) if not isinstance(value, str) else value

        expires_at = None
        if ttl_seconds:
            expires_at = (datetime.now() + timedelta(seconds=ttl_seconds)).isoformat()

        created_at = datetime.now().isoformat()

        await self._db.execute(f"""
            INSERT OR REPLACE INTO {self._table_name} (key, value, expires_at, created_at)
            VALUES (?, ?, ?, ?)
        """, (hashed_key, value_str, expires_at, created_at))

        return True

    async def delete(self, key: str) -> bool:
        """删除缓存"""
        if not self._initialized:
            await self.initialize()

        hashed_key = self._hash_key(key)
        await self._db.execute(f"DELETE FROM {self._table_name} WHERE key = ?", (hashed_key,))
        return True

    async def clear(self) -> int:
        """清空所有缓存"""
        await self._db.execute(f"DELETE FROM {self._table_name}")
        return 0

    async def cleanup_expired(self) -> int:
        """清理过期缓存"""
        now = datetime.now().isoformat()
        await self._db.execute(f"""
            DELETE FROM {self._table_name}
            WHERE expires_at IS NOT NULL AND expires_at < ?
        """, (now,))
        return 0
