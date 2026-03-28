"""向量存储封装"""

from typing import Optional, Literal
from loguru import logger


class VectorStoreWrapper:
    """向量存储封装"""

    def __init__(self, storage_dir: str = None):
        self.storage_dir = storage_dir or "memory/knowledge_hub/vectors"
        self._store: Optional[object] = None

    def get_store(self):
        """获取向量存储实例"""
        if self._store is None:
            try:
                from backend.modules.agent.vector_store import VectorStore
                import os
                db_path = os.path.join(self.storage_dir, "vectors.db")
                self._store = VectorStore(db_path=db_path)
            except ImportError as e:
                logger.warning(f"Vector store not available: {e}")
                return None
            except Exception as e:
                logger.warning(f"Vector store init failed: {e}")
                return None
        return self._store

    def add(
        self,
        content: str,
        metadata: dict = None,
        source_type: str = "knowledge",
        source_id: str = None,
    ) -> str:
        """添加单个文档到向量库"""
        store = self.get_store()
        if store is None:
            return ""

        try:
            return store.add(
                content=content,
                metadata=metadata or {},
                source_type=source_type,
                source_id=source_id,
            )
        except Exception as e:
            logger.warning(f"Failed to add to vector store: {e}")
            return ""

    def search(self, query: str, top_k: int = 5, source_type: str = None) -> list[dict]:
        """检索"""
        store = self.get_store()
        if store is None:
            return []

        try:
            results = store.search(
                query=query,
                top_k=top_k,
                source_type=source_type,
            )
            return results
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return []

    async def add_documents(self, documents: list[dict], source_type: str = "knowledge"):
        """添加文档到向量库"""
        store = self.get_store()
        if store is None:
            return

        for doc in documents:
            chunks = doc.get("content", [])
            if isinstance(chunks, list):
                entries = [{"content": c, "metadata": doc} for c in chunks]
            else:
                entries = [{"content": chunks, "metadata": doc}]

            try:
                for entry in entries:
                    store.add(
                        content=entry["content"],
                        metadata=entry.get("metadata", {}),
                        source_type=source_type,
                        source_id=doc.get("id"),
                    )
            except Exception as e:
                logger.warning(f"Failed to add to vector store: {e}")

    async def search_async(self, query: str, top_k: int = 5, source_type: str = "knowledge") -> list[dict]:
        """异步检索"""
        return self.search(query, top_k, source_type)

    def count(self, source_type: str = "knowledge") -> int:
        """统计数量"""
        store = self.get_store()
        if store is None:
            return 0
        try:
            return store.count(source_type=source_type)
        except Exception:
            return 0

    def get_stats(self) -> dict:
        """获取统计信息"""
        store = self.get_store()
        if store is None:
            return {"available": False}

        try:
            return {
                "available": True,
                "count": self.count(),
            }
        except Exception as e:
            return {"available": False, "error": str(e)}
