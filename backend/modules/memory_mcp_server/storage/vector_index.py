"""Vector index adapter for AIE VectorStore.

This module provides an adapter that integrates with AIE's existing VectorStore
which uses SQLite + BAAI/bge-small-zh-v1.5 for CPU-efficient embeddings.
"""

import json
import sqlite3
from pathlib import Path
from typing import Optional

from loguru import logger

from ..models.config import StorageConfig


class VectorIndex:
    """
    Vector index using AIE's VectorStore approach.

    Uses SQLite BLOB storage + bge-small-zh-v1.5 embedding model.
    Compatible with AIE's existing vector database.
    """

    def __init__(self, db_path: str | Path, config: StorageConfig):
        self.db_path = Path(db_path)
        self.config = config
        self.dim = config.vector_dim or 512  # bge-small-zh-v1.5 = 512

    async def initialize(self) -> None:
        """Initialize the vector index table (compatible with AIE VectorStore schema)."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Create vector table compatible with AIE VectorStore
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vectors (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                metadata TEXT,
                vector BLOB,
                source_type TEXT DEFAULT 'knowledge',
                source_id TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_source_type ON vectors(source_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_source_id ON vectors(source_id)
        """)

        # Create memory-specific index for URI lookups
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_vectors (
                memory_id TEXT PRIMARY KEY,
                uri TEXT NOT NULL,
                level INTEGER DEFAULT 2,
                context_type TEXT,
                tenant_id TEXT,
                vector BLOB,
                created_at TEXT
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_uri ON memory_vectors(uri)
        """)

        conn.commit()
        conn.close()

        logger.info(f"VectorIndex initialized at {self.db_path}")

    def _get_embedding_model(self):
        """Lazy load AIE's bge-small-zh-v1.5 embedding model."""
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("BAAI/bge-small-zh-v1.5", device="cpu")
            logger.info("Loaded embedding model: BAAI/bge-small-zh-v1.5")
            return model
        except ImportError:
            logger.error("sentence-transformers not installed")
            raise

    def _encode(self, texts: list[str]) -> list:
        """Encode texts to vectors using bge-small-zh-v1.5."""
        import numpy as np
        model = self._get_embedding_model()
        embeddings = model.encode(texts, normalize_embeddings=True)
        return embeddings.astype(np.float32)

    def _vector_to_blob(self, vector) -> bytes:
        """Convert numpy array to blob."""
        import numpy as np
        return vector.astype(np.float32).tobytes()

    def _blob_to_vector(self, blob: bytes):
        """Convert blob to numpy array."""
        import numpy as np
        return np.frombuffer(blob, dtype=np.float32)

    async def insert(
        self,
        memory_id: str,
        uri: str,
        level: int,
        context_type: str,
        content: str,
        vector: list[float],
        tenant_id: str | None = None,
    ) -> str:
        """Insert a vector into the index."""
        import numpy as np
        from datetime import datetime

        now = datetime.now().isoformat()
        vector_array = np.array(vector, dtype=np.float32)
        vector_blob = self._vector_to_blob(vector_array)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO memory_vectors
            (memory_id, uri, level, context_type, tenant_id, vector, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (memory_id, uri, level, context_type, tenant_id, vector_blob, now))

        conn.commit()
        conn.close()

        return memory_id

    async def search(
        self,
        query_vector: list[float],
        context_type: str | None = None,
        uri_prefix: str | None = None,
        tenant_id: str | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """
        Search for similar vectors.

        Returns list of dicts with memory_id, uri, level, similarity score.
        """
        import numpy as np

        # Convert query vector
        query_array = np.array(query_vector, dtype=np.float32)
        query_norm = np.linalg.norm(query_array)
        if query_norm > 0:
            query_array = query_array / query_norm

        # Build SQL query
        sql = """
            SELECT memory_id, uri, level, context_type, vector
            FROM memory_vectors
            WHERE vector IS NOT NULL
        """
        params = []

        if context_type:
            sql += " AND context_type = ?"
            params.append(context_type)

        if tenant_id:
            sql += " AND tenant_id = ?"
            params.append(tenant_id)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(sql, params)

        rows = cursor.fetchall()
        conn.close()

        # Calculate similarities
        results = []
        for row in rows:
            memory_id, uri, level, ctx_type, vector_blob = row
            if vector_blob is None:
                continue

            vector = self._blob_to_vector(vector_blob)
            # Normalize
            norm = np.linalg.norm(vector)
            if norm > 0:
                vector = vector / norm

            # Cosine similarity
            score = float(np.dot(query_array, vector))

            # URI prefix filter
            if uri_prefix and not uri.startswith(uri_prefix.rstrip("/")):
                if not uri.startswith(uri_prefix.rstrip("/") + "/"):
                    continue

            results.append({
                "memory_id": memory_id,
                "uri": uri,
                "level": level or 2,
                "context_type": ctx_type,
                "score": max(0.0, score),
            })

        # Sort by score and limit
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def search_sync(
        self,
        query: str,
        top_k: int = 5,
        context_type: str | None = None,
        uri_prefix: str | None = None,
    ) -> list[dict]:
        """
        Synchronous semantic search using embedded query.

        This is a convenience method that encodes the query and searches
        in one call, compatible with AIE's VectorStore interface.
        """
        # Encode query
        query_embedding = self._encode([query])[0]

        # Run sync search
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self.search(
                query_vector=query_embedding.tolist(),
                context_type=context_type,
                uri_prefix=uri_prefix,
                limit=top_k,
            )
        )

    async def delete_by_memory_id(self, memory_id: str) -> None:
        """Delete vectors for a memory."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM memory_vectors WHERE memory_id = ?", (memory_id,))
        conn.commit()
        conn.close()

    async def delete_by_uri(self, uri: str) -> None:
        """Delete vectors for a memory URI (handles prefix for hierarchy)."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM memory_vectors WHERE uri = ? OR uri LIKE ? || '/%'",
            (uri, uri)
        )
        conn.commit()
        conn.close()

    async def count(self) -> int:
        """Count total vectors in the index."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM memory_vectors WHERE vector IS NOT NULL")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    async def get_by_memory_id(self, memory_id: str) -> list[dict]:
        """Get all vector entries for a memory ID."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM memory_vectors WHERE memory_id = ?", (memory_id,))
        rows = cursor.fetchall()
        conn.close()

        columns = ["memory_id", "uri", "level", "context_type", "tenant_id", "vector", "created_at"]
        return [dict(zip(columns, row)) for row in rows]
