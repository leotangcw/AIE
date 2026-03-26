# backend/infrastructure/vector_store.py

"""统一向量存储 - 1024 维 (BGE-M3)"""

import json
import uuid
import numpy as np
from datetime import datetime
from typing import Optional, Any
from loguru import logger

from .database import SQLiteDatabase


class SQLiteVectorStore:
    """向量存储（统一 1024 维）

    使用显式初始化模式，避免在 __init__ 中调用 asyncio.run()
    """

    def __init__(self, db: SQLiteDatabase, dimension: int = 1024):
        self._db = db
        self._dimension = dimension
        self._embedder: Optional[Any] = None
        self._initialized = False

    async def initialize(self) -> "SQLiteVectorStore":
        """异步初始化表结构（必须调用）"""
        if self._initialized:
            return self

        await self._db.execute(f"""
            CREATE TABLE IF NOT EXISTS vectors (
                id TEXT PRIMARY KEY,
                namespace TEXT DEFAULT 'default',
                content TEXT NOT NULL,
                metadata TEXT,
                vector BLOB,
                dimension INTEGER DEFAULT {self._dimension},
                source_type TEXT DEFAULT 'knowledge',
                source_id TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        await self._db.execute("CREATE INDEX IF NOT EXISTS idx_namespace ON vectors(namespace)")
        await self._db.execute("CREATE INDEX IF NOT EXISTS idx_source_type ON vectors(source_type)")
        self._initialized = True
        logger.info(f"Vector store initialized (dimension={self._dimension})")
        return self

    def set_embedder(self, embedder: Any):
        """设置 Embedder（由 ModelRegistry 注入）"""
        self._embedder = embedder

    def _vector_to_blob(self, vector: np.ndarray) -> bytes:
        return vector.astype(np.float32).tobytes()

    def _blob_to_vector(self, blob: bytes) -> np.ndarray:
        return np.frombuffer(blob, dtype=np.float32)

    async def add(
        self,
        content: str,
        embedding: Optional[np.ndarray] = None,
        metadata: Optional[dict] = None,
        namespace: str = "default",
        source_type: str = "knowledge",
        source_id: str = None,
    ) -> str:
        """添加向量"""
        if not self._initialized:
            await self.initialize()

        # Critical 1: Dimension validation
        if embedding is not None and len(embedding) != self._dimension:
            raise ValueError(f"Embedding dimension {len(embedding)} does not match expected {self._dimension}")

        entry_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        if embedding is None and self._embedder:
            embedding = await self._embedder.embed_single(content)

        vector_blob = self._vector_to_blob(embedding) if embedding is not None else None

        # Important 4: Error handling for JSON operations
        try:
            metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid metadata: {e}")

        await self._db.execute("""
            INSERT INTO vectors (id, namespace, content, metadata, vector, dimension, source_type, source_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry_id, namespace, content,
            metadata_json,
            vector_blob, self._dimension,
            source_type, source_id, now, now
        ))

        return entry_id

    async def search(
        self,
        query_embedding: np.ndarray,
        namespace: str = "default",
        top_k: int = 5,
        min_score: float = 0.5,
    ) -> list[dict]:
        """向量搜索"""
        if not self._initialized:
            await self.initialize()

        # Important 5: Search dimension validation
        if len(query_embedding) != self._dimension:
            raise ValueError(f"Query dimension {len(query_embedding)} does not match expected {self._dimension}")

        rows = await self._db.fetchall("""
            SELECT id, content, metadata, vector, source_type, source_id
            FROM vectors
            WHERE namespace = ? AND vector IS NOT NULL AND dimension = ?
        """, (namespace, self._dimension))

        results = []
        for row in rows:
            vector = self._blob_to_vector(row["vector"])
            score = float(np.dot(query_embedding, vector))
            if score >= min_score:
                results.append({
                    "id": row["id"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"] or "{}"),
                    "source_type": row["source_type"],
                    "source_id": row["source_id"],
                    "score": score,
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    async def delete(self, entry_id: str) -> bool:
        """删除向量"""
        await self._db.execute("DELETE FROM vectors WHERE id = ?", (entry_id,))
        return True

    async def delete_by_namespace(self, namespace: str) -> int:
        """删除命名空间下所有向量"""
        await self._db.execute("DELETE FROM vectors WHERE namespace = ?", (namespace,))
        return 0

    async def count(self, namespace: str = "default") -> int:
        """统计数量"""
        row = await self._db.fetchone(
            "SELECT COUNT(*) as cnt FROM vectors WHERE namespace = ?",
            (namespace,)
        )
        return row["cnt"] if row else 0

    async def get_stats(self, namespace: str = "default") -> dict:
        """获取统计信息"""
        row = await self._db.fetchone("""
            SELECT COUNT(*) as cnt, dimension
            FROM vectors
            WHERE namespace = ?
            GROUP BY dimension
        """, (namespace,))
        if row:
            return {"count": row["cnt"], "dimension": row["dimension"]}
        return {"count": 0, "dimension": self._dimension}

    async def iter_documents(self, namespace: str = "default", batch_size: int = 100):
        """迭代文档（用于迁移）"""
        offset = 0
        while True:
            rows = await self._db.fetchall("""
                SELECT id, content, metadata, source_type, source_id
                FROM vectors
                WHERE namespace = ?
                ORDER BY id
                LIMIT ? OFFSET ?
            """, (namespace, batch_size, offset))
            if not rows:
                break
            yield [dict(row) for row in rows]
            offset += batch_size

    async def update_embedding(self, doc_id: str, embedding: np.ndarray, dimension: int) -> bool:
        """更新向量"""
        # Critical 1: Dimension validation
        if len(embedding) != self._dimension:
            raise ValueError(f"Embedding dimension {len(embedding)} does not match expected {self._dimension}")

        vector_blob = self._vector_to_blob(embedding)
        now = datetime.now().isoformat()
        await self._db.execute("""
            UPDATE vectors SET vector = ?, dimension = ?, updated_at = ? WHERE id = ?
        """, (vector_blob, dimension, now, doc_id))
        return True
