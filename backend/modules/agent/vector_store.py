"""Vector Store using SQLite + bge-small-zh-v1.5 embedding"""

import json
import sqlite3
import uuid
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Optional, Literal
from loguru import logger

from backend.utils.paths import MEMORY_DIR, WORKSPACE_DIR

# Vector dimension for bge-small-zh-v1.5
VECTOR_DIMENSION = 512


class VectorStore:
    """Vector store using SQLite for persistence and bge-small-zh for embedding"""

    def __init__(
        self,
        db_path: Path = None,
        embedding_model: str = "BAAI/bge-small-zh-v1.5",
    ):
        self.db_path = db_path or MEMORY_DIR / "vector_store.db"
        self.embedding_model_name = embedding_model
        self.embedding_model = None
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Create vector table
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

        # Create index on source_type for filtering
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_source_type ON vectors(source_type)
        """)

        # Create index on source_id for grouping
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_source_id ON vectors(source_id)
        """)

        conn.commit()
        conn.close()

        logger.info(f"Vector store initialized at {self.db_path}")

    def _get_embedding_model(self):
        """Lazy load embedding model"""
        if self.embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info(f"Loading embedding model: {self.embedding_model_name}")
                # Use CPU explicitly
                self.embedding_model = SentenceTransformer(
                    self.embedding_model_name,
                    device="cpu"
                )
                logger.info(f"Embedding model loaded successfully")
            except ImportError:
                logger.error("sentence-transformers not installed. Install with: pip install sentence-transformers")
                raise

        return self.embedding_model

    def _encode(self, texts: list[str]) -> np.ndarray:
        """Encode texts to vectors"""
        model = self._get_embedding_model()
        embeddings = model.encode(texts, normalize_embeddings=True)
        return embeddings

    def _vector_to_blob(self, vector: np.ndarray) -> bytes:
        """Convert numpy array to blob"""
        return vector.astype(np.float32).tobytes()

    def _blob_to_vector(self, blob: bytes) -> np.ndarray:
        """Convert blob to numpy array"""
        return np.frombuffer(blob, dtype=np.float32)

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity"""
        return float(np.dot(a, b))

    # ========== CRUD Operations ==========

    def add(
        self,
        content: str,
        metadata: dict = None,
        source_type: str = "knowledge",
        source_id: str = None,
        generate_embedding: bool = True,
    ) -> str:
        """Add a new vector entry"""
        entry_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        # Generate embedding if requested
        vector = None
        if generate_embedding:
            embeddings = self._encode([content])
            vector = self._vector_to_blob(embeddings[0])

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO vectors (id, content, metadata, vector, source_type, source_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry_id,
            content,
            json.dumps(metadata or {}, ensure_ascii=False),
            vector,
            source_type,
            source_id,
            now,
            now,
        ))

        conn.commit()
        conn.close()

        logger.debug(f"Added vector entry: {entry_id}")
        return entry_id

    def add_batch(
        self,
        entries: list[dict],
        source_type: str = "knowledge",
        source_id: str = None,
    ) -> list[str]:
        """Add multiple entries at once (more efficient)"""
        if not entries:
            return []

        # Extract contents for batch encoding
        contents = [e["content"] for e in entries]

        # Generate embeddings in batch
        logger.info(f"Encoding {len(contents)} entries...")
        embeddings = self._encode(contents)

        # Insert all entries
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        entry_ids = []
        now = datetime.now().isoformat()

        for i, entry in enumerate(entries):
            entry_id = str(uuid.uuid4())
            entry_ids.append(entry_id)

            vector = self._vector_to_blob(embeddings[i])

            cursor.execute("""
                INSERT INTO vectors (id, content, metadata, vector, source_type, source_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry_id,
                entry["content"],
                json.dumps(entry.get("metadata", {}), ensure_ascii=False),
                vector,
                source_type,
                source_id or entry.get("source_id"),
                now,
                now,
            ))

        conn.commit()
        conn.close()

        logger.info(f"Added {len(entry_ids)} vector entries")
        return entry_ids

    def get(self, entry_id: str) -> Optional[dict]:
        """Get entry by ID"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM vectors WHERE id = ?", (entry_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return self._row_to_dict(row)

    def update(
        self,
        entry_id: str,
        content: str = None,
        metadata: dict = None,
        generate_embedding: bool = True,
    ) -> bool:
        """Update an entry"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Check if exists
        cursor.execute("SELECT content, metadata FROM vectors WHERE id = ?", (entry_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False

        old_content, old_metadata = row
        update_content = content if content is not None else old_content
        update_metadata = json.dumps(metadata if metadata is not None else json.loads(old_metadata or "{}"), ensure_ascii=False)

        # Generate new embedding if content changed
        vector = None
        if generate_embedding and content is not None:
            embeddings = self._encode([content])
            vector = self._vector_to_blob(embeddings[0])

        now = datetime.now().isoformat()

        if vector:
            cursor.execute("""
                UPDATE vectors
                SET content = ?, metadata = ?, vector = ?, updated_at = ?
                WHERE id = ?
            """, (update_content, update_metadata, vector, now, entry_id))
        else:
            cursor.execute("""
                UPDATE vectors
                SET content = ?, metadata = ?, updated_at = ?
                WHERE id = ?
            """, (update_content, update_metadata, now, entry_id))

        conn.commit()
        conn.close()

        logger.debug(f"Updated vector entry: {entry_id}")
        return True

    def delete(self, entry_id: str) -> bool:
        """Delete an entry"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("DELETE FROM vectors WHERE id = ?", (entry_id,))
        deleted = cursor.rowcount > 0

        conn.commit()
        conn.close()

        if deleted:
            logger.debug(f"Deleted vector entry: {entry_id}")
        return deleted

    def delete_by_source(self, source_type: str = None, source_id: str = None) -> int:
        """Delete entries by source type or source_id"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        if source_type and source_id:
            cursor.execute(
                "DELETE FROM vectors WHERE source_type = ? AND source_id = ?",
                (source_type, source_id)
            )
        elif source_type:
            cursor.execute(
                "DELETE FROM vectors WHERE source_type = ?",
                (source_type,)
            )

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        logger.info(f"Deleted {deleted} vector entries")
        return deleted

    # ========== Search Operations ==========

    def search(
        self,
        query: str,
        top_k: int = 5,
        source_type: str = None,
        source_id: str = None,
        min_score: float = 0.5,
    ) -> list[dict]:
        """Search by semantic similarity"""
        # Encode query
        query_embedding = self._encode([query])[0]

        # Build SQL query
        sql = """
            SELECT id, content, metadata, source_type, source_id, vector
            FROM vectors
            WHERE vector IS NOT NULL
        """
        params = []

        if source_type:
            sql += " AND source_type = ?"
            params.append(source_type)

        if source_id:
            sql += " AND source_id = ?"
            params.append(source_id)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(sql, params)

        rows = cursor.fetchall()
        conn.close()

        # Calculate similarities
        results = []
        for row in rows:
            entry_id, content, metadata, src_type, src_id, vector_blob = row
            if vector_blob:
                vector = self._blob_to_vector(vector_blob)
                score = self._cosine_similarity(query_embedding, vector)

                if score >= min_score:
                    results.append({
                        "id": entry_id,
                        "content": content,
                        "metadata": json.loads(metadata or "{}"),
                        "source_type": src_type,
                        "source_id": src_id,
                        "score": score,
                    })

        # Sort by score and limit
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def search_hybrid(
        self,
        query: str,
        top_k: int = 5,
        source_type: str = None,
        source_id: str = None,
        keyword_weight: float = 0.3,
        vector_weight: float = 0.7,
    ) -> list[dict]:
        """Hybrid search combining keyword and vector similarity"""
        # Vector search
        vector_results = self.search(query, top_k * 2, source_type, source_id, min_score=0.0)

        # Keyword search (simple substring match)
        keyword_results = self._keyword_search(query, top_k * 2, source_type, source_id)

        # Merge results
        merged = {}
        query_lower = query.lower()

        # Add vector results
        for r in vector_results:
            merged[r["id"]] = {
                **r,
                "vector_score": r["score"],
                "keyword_score": 0.0,
                "final_score": r["score"] * vector_weight,
            }

        # Add keyword results
        for r in keyword_results:
            if r["id"] in merged:
                merged[r["id"]]["keyword_score"] = r["score"]
                merged[r["id"]]["final_score"] = (
                    merged[r["id"]]["vector_score"] * vector_weight +
                    r["score"] * keyword_weight
                )
            else:
                merged[r["id"]] = {
                    **r,
                    "vector_score": 0.0,
                    "keyword_score": r["score"],
                    "final_score": r["score"] * keyword_weight,
                }

        # Sort by final score
        results = list(merged.values())
        results.sort(key=lambda x: x["final_score"], reverse=True)

        return results[:top_k]

    def _keyword_search(
        self,
        query: str,
        top_k: int = 5,
        source_type: str = None,
        source_id: str = None,
    ) -> list[dict]:
        """Simple keyword search"""
        keywords = query.lower().split()

        sql = "SELECT id, content, metadata, source_type, source_id FROM vectors WHERE 1=1"
        params = []

        if source_type:
            sql += " AND source_type = ?"
            params.append(source_type)

        if source_id:
            sql += " AND source_id = ?"
            params.append(source_id)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(sql, params)

        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            entry_id, content, metadata, src_type, src_id = row
            content_lower = content.lower()

            # Count keyword matches
            matches = sum(1 for kw in keywords if kw in content_lower)
            if matches > 0:
                score = matches / len(keywords)
                results.append({
                    "id": entry_id,
                    "content": content,
                    "metadata": json.loads(metadata or "{}"),
                    "source_type": src_type,
                    "source_id": src_id,
                    "score": score,
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    # ========== Utility Methods ==========

    def count(self, source_type: str = None) -> int:
        """Count entries"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        if source_type:
            cursor.execute("SELECT COUNT(*) FROM vectors WHERE source_type = ?", (source_type,))
        else:
            cursor.execute("SELECT COUNT(*) FROM vectors")

        count = cursor.fetchone()[0]
        conn.close()

        return count

    def get_all_source_ids(self, source_type: str = None) -> list[str]:
        """Get all unique source IDs"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        if source_type:
            cursor.execute(
                "SELECT DISTINCT source_id FROM vectors WHERE source_type = ? AND source_id IS NOT NULL",
                (source_type,)
            )
        else:
            cursor.execute(
                "SELECT DISTINCT source_id FROM vectors WHERE source_id IS NOT NULL"
            )

        rows = cursor.fetchall()
        conn.close()

        return [row[0] for row in rows if row[0]]

    def _row_to_dict(self, row: tuple) -> dict:
        """Convert database row to dictionary"""
        columns = ["id", "content", "metadata", "vector", "source_type", "source_id", "created_at", "updated_at"]
        result = dict(zip(columns, row))

        if result["metadata"]:
            result["metadata"] = json.loads(result["metadata"])

        if result["vector"]:
            result["vector"] = self._blob_to_vector(result["vector"]).tolist()

        return result


# Global instance
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get global vector store instance"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


def reinit_vector_store():
    """Reinitialize vector store"""
    global _vector_store
    _vector_store = VectorStore()
    return _vector_store
