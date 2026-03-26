# backend/infrastructure/database.py

"""SQLite 数据库封装"""

import sqlite3
from pathlib import Path
from typing import Optional
from loguru import logger


class SQLiteDatabase:
    """SQLite 数据库连接管理"""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[sqlite3.Connection] = None
        logger.info(f"Database initialized at {self.db_path}")

    async def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._connection is None:
            self._connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
            )
            self._connection.row_factory = sqlite3.Row
        return self._connection

    async def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """执行 SQL"""
        conn = await self.get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return cursor

    async def fetchall(self, sql: str, params: tuple = ()) -> list:
        """查询所有行"""
        conn = await self.get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall()

    async def fetchone(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """查询单行"""
        conn = await self.get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchone()

    async def close(self):
        """关闭连接"""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("Database connection closed")
