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
                from backend.modules.agent.vector_store import get_vector_store
                self._store = get_vector_store()
            except ImportError as e:
                logger.warning(f"Vector store not available: {e}")
                return None
        return self._store

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
                store.add_batch(entries=entries, source_type=source_type, source_id=doc.get("id"))
            except Exception as e:
                logger.warning(f"Failed to add to vector store: {e}")

    async def search(self, query: str, top_k: int = 5, source_type: str = "knowledge") -> list[dict]:
        """检索"""
        store = self.get_store()
        if store is None:
            return []

        try:
            results = store.search_hybrid(
                query=query,
                top_k=top_k,
                source_type=source_type
            )
            return results
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return []

    async def count(self, source_type: str = "knowledge") -> int:
        """统计数量"""
        store = self.get_store()
        if store is None:
            return 0
        try:
            return store.count(source_type=source_type)
        except Exception:
            return 0
