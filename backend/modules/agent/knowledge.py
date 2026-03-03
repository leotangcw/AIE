"""AIE 知识库 RAG 系统"""

import json
import os
import uuid
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from loguru import logger

from backend.utils.paths import MEMORY_DIR


class KnowledgeSource:
    """知识源"""

    def __init__(
        self,
        name: str,
        source_type: str,  # local, wiki, database, api
        config: dict,
        enabled: bool = True,
    ):
        self.id = str(uuid.uuid4())
        self.name = name
        self.source_type = source_type
        self.config = config
        self.enabled = enabled
        self.created_at = datetime.now().isoformat()
        self.last_sync = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "source_type": self.source_type,
            "config": self.config,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "last_sync": self.last_sync,
        }


class KnowledgeChunk:
    """知识块"""

    def __init__(
        self,
        source_id: str,
        content: str,
        metadata: dict = None,
        embedding: list[float] = None,
    ):
        self.id = str(uuid.uuid4())
        self.source_id = source_id
        self.content = content
        self.metadata = metadata or {}
        self.embedding = embedding
        self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


class KnowledgeRAG:
    """知识库 RAG 系统"""

    def __init__(self, storage_dir: Path = None):
        self.storage_dir = storage_dir or MEMORY_DIR / "knowledge"
        self.sources_dir = self.storage_dir / "sources"
        self.chunks_dir = self.storage_dir / "chunks"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        self.chunks_dir.mkdir(parents=True, exist_ok=True)

        self._sources: dict[str, KnowledgeSource] = {}
        self._chunks: list[KnowledgeChunk] = []
        self._load_data()

    def _load_data(self):
        """加载数据"""
        # 加载知识源
        for file in self.sources_dir.glob("*.json"):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                source = KnowledgeSource(
                    name=data["name"],
                    source_type=data["source_type"],
                    config=data.get("config", {}),
                    enabled=data.get("enabled", True),
                )
                source.id = data.get("id", source.id)
                source.created_at = data.get("created_at", source.created_at)
                source.last_sync = data.get("last_sync")
                self._sources[source.id] = source
            except Exception as e:
                logger.warning(f"Failed to load source from {file}: {e}")

        # 加载知识块
        chunks_file = self.chunks_dir / "index.json"
        if chunks_file.exists():
            try:
                data = json.loads(chunks_file.read_text(encoding="utf-8"))
                for item in data:
                    chunk = KnowledgeChunk(
                        source_id=item["source_id"],
                        content=item["content"],
                        metadata=item.get("metadata", {}),
                    )
                    chunk.id = item.get("id", chunk.id)
                    chunk.created_at = item.get("created_at", chunk.created_at)
                    self._chunks.append(chunk)
            except Exception as e:
                logger.warning(f"Failed to load chunks: {e}")

        logger.info(f"Loaded {len(self._sources)} sources and {len(self._chunks)} chunks")

    def _save_sources(self):
        """保存知识源"""
        for source in self._sources.values():
            file = self.sources_dir / f"{source.id}.json"
            file.write_text(
                json.dumps(source.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

    def _save_chunks(self):
        """保存知识块"""
        chunks_file = self.chunks_dir / "index.json"
        chunks_file.write_text(
            json.dumps([c.to_dict() for c in self._chunks], ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def add_source(self, source: KnowledgeSource):
        """添加知识源"""
        self._sources[source.id] = source
        self._save_sources()
        logger.info(f"Added knowledge source: {source.name}")

    def get_source(self, source_id: str) -> Optional[KnowledgeSource]:
        """获取知识源"""
        return self._sources.get(source_id)

    def get_all_sources(self) -> list[KnowledgeSource]:
        """获取所有知识源"""
        return list(self._sources.values())

    def delete_source(self, source_id: str) -> bool:
        """删除知识源"""
        if source_id in self._sources:
            del self._sources[source_id]
            # 删除关联的 chunks
            self._chunks = [c for c in self._chunks if c.source_id != source_id]
            self._save_sources()
            self._save_chunks()
            return True
        return False

    def add_document(self, source_id: str, content: str, metadata: dict = None):
        """添加文档到知识库"""
        # 简单的文本分块
        chunk_size = 1000
        overlap = 100

        chunks = []
        for i in range(0, len(content), chunk_size - overlap):
            chunk_content = content[i:i + chunk_size]
            if chunk_content.strip():
                chunk = KnowledgeChunk(
                    source_id=source_id,
                    content=chunk_content,
                    metadata=metadata or {},
                )
                chunks.append(chunk)

        self._chunks.extend(chunks)
        self._save_chunks()
        logger.info(f"Added {len(chunks)} chunks from document")

        # 更新同步时间
        source = self._sources.get(source_id)
        if source:
            source.last_sync = datetime.now().isoformat()
            self._save_sources()

        return len(chunks)

    def retrieve(self, query: str, top_k: int = 5, source_ids: list[str] = None) -> list[KnowledgeChunk]:
        """检索相关知识 - 简化版基于关键词匹配"""
        # 简化实现: 基于关键词匹配
        # 生产环境应使用向量相似度

        query_keywords = set(query.lower().split())
        scored_chunks = []

        for chunk in self._chunks:
            # 过滤来源
            if source_ids and chunk.source_id not in source_ids:
                continue

            # 计算关键词重叠
            content_keywords = set(chunk.content.lower().split())
            overlap = query_keywords & content_keywords
            if overlap:
                scored_chunks.append((len(overlap), chunk))

        # 按得分排序
        scored_chunks.sort(key=lambda x: x[0], reverse=True)

        # 返回 top_k
        return [chunk for _, chunk in scored_chunks[:top_k]]

    def augment_context(self, query: str, context: dict, top_k: int = 3) -> dict:
        """增强上下文"""
        # 检索相关知识
        chunks = self.retrieve(query, top_k=top_k)

        if not chunks:
            return context

        # 添加检索到的知识到上下文
        knowledge_context = "\n\n".join([
            f"[知识 {i+1}]: {chunk.content}"
            for i, chunk in enumerate(chunks)
        ])

        # 构建增强后的上下文
        augmented = {
            **context,
            "knowledge_context": knowledge_context,
            "knowledge_sources": [c.source_id for c in chunks],
            "knowledge_count": len(chunks),
        }

        return augmented


class KnowledgeAPI:
    """知识库 API"""

    def __init__(self, rag: KnowledgeRAG):
        self.rag = rag

    async def load_document(self, source_id: str, file_path: Path, metadata: dict = None) -> int:
        """加载文档"""
        try:
            content = file_path.read_text(encoding="utf-8")
            return self.rag.add_document(source_id, content, metadata)
        except Exception as e:
            logger.error(f"Failed to load document: {e}")
            return 0


# 全局实例
_rag: Optional[KnowledgeRAG] = None


def get_knowledge_rag() -> KnowledgeRAG:
    global _rag
    if _rag is None:
        _rag = KnowledgeRAG()
    return _rag
