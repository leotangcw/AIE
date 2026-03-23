"""SQLite database connection management."""

import asyncio
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import aiosqlite

from ..models.config import StorageConfig


class Database:
    """Async SQLite database manager."""

    def __init__(self, config: StorageConfig):
        self.config = config
        self.db_path = Path(config.db_path)
        self._lock = asyncio.Lock()
        self._connection: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Initialize database and create tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = await self.get_connection()
        await self._create_tables(conn)
        # Don't close the connection, keep it for later use

    async def get_connection(self) -> aiosqlite.Connection:
        """Get a database connection."""
        async with self._lock:
            if self._connection is None:
                self._connection = await aiosqlite.connect(
                    str(self.db_path),
                    isolation_level=None,
                )
                self._connection.row_factory = aiosqlite.Row
            return self._connection

    async def close(self) -> None:
        """Close the database connection."""
        async with self._lock:
            if self._connection:
                await self._connection.close()
                self._connection = None

    async def _create_tables(self, conn: aiosqlite.Connection) -> None:
        """Create all required tables."""
        await conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                uri TEXT UNIQUE NOT NULL,
                parent_uri TEXT,
                context_type TEXT NOT NULL CHECK(context_type IN ('memory', 'resource', 'skill')),
                level INTEGER NOT NULL CHECK(level IN (0, 1, 2)),
                abstract TEXT,
                overview TEXT,
                content TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL,
                description TEXT,
                tags TEXT DEFAULT '[]',
                source TEXT DEFAULT 'unknown',
                metadata TEXT DEFAULT '{}',
                vector_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                active_count INTEGER DEFAULT 0,
                tenant_id TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_memories_uri ON memories(uri);
            CREATE INDEX IF NOT EXISTS idx_memories_parent_uri ON memories(parent_uri);
            CREATE INDEX IF NOT EXISTS idx_memories_context_type ON memories(context_type);
            CREATE INDEX IF NOT EXISTS idx_memories_level ON memories(level);
            CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at);
            CREATE INDEX IF NOT EXISTS idx_memories_tenant_id ON memories(tenant_id);
        """)

        await conn.execute("PRAGMA foreign_keys = ON;")

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Context manager for database transactions."""
        conn = await self.get_connection()
        try:
            await conn.execute("BEGIN")
            yield conn
            await conn.execute("COMMIT")
        except Exception:
            await conn.execute("ROLLBACK")
            raise

    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        """Execute a single statement."""
        conn = await self.get_connection()
        return await conn.execute(sql, params)

    async def executemany(self, sql: str, params_list: list[tuple]) -> aiosqlite.Cursor:
        """Execute a statement with multiple parameter sets."""
        conn = await self.get_connection()
        return await conn.executemany(sql, params_list)

    async def fetchone(self, sql: str, params: tuple = ()) -> aiosqlite.Row | None:
        """Fetch a single row."""
        conn = await self.get_connection()
        cursor = await conn.execute(sql, params)
        return await cursor.fetchone()

    async def fetchall(self, sql: str, params: tuple = ()) -> list[aiosqlite.Row]:
        """Fetch all rows."""
        conn = await self.get_connection()
        cursor = await conn.execute(sql, params)
        return await cursor.fetchall()

    async def getsize(self) -> int:
        """Get database file size in bytes."""
        if self.db_path.exists():
            return self.db_path.stat().st_size
        return 0
