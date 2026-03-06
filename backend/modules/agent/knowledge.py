"""AIE Knowledge Base RAG System - Multi-mode Retrieval"""

import json
import os
import uuid
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Literal
from loguru import logger
from collections import Counter

from backend.utils.paths import MEMORY_DIR, WORKSPACE_DIR
from backend.modules.agent.vector_store import get_vector_store, VectorStore


class KnowledgeSource:
    """知识源"""

    def __init__(
        self,
        name: str,
        source_type: Literal["local", "api", "database", "wiki"],
        config: dict,
        enabled: bool = True,
        priority: int = 5,
        sync_interval: int = 60,
    ):
        self.id = str(uuid.uuid4())
        self.name = name
        self.source_type = source_type
        self.config = config
        self.enabled = enabled
        self.priority = priority  # 1-10, 优先级越高越先检索
        self.sync_interval = sync_interval  # 同步间隔(分钟)
        self.created_at = datetime.now().isoformat()
        self.last_sync = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "source_type": self.source_type,
            "config": self.config,
            "enabled": self.enabled,
            "priority": self.priority,
            "sync_interval": self.sync_interval,
            "created_at": self.created_at,
            "last_sync": self.last_sync,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeSource":
        """从字典创建"""
        source = cls(
            name=data["name"],
            source_type=data["source_type"],
            config=data.get("config", {}),
            enabled=data.get("enabled", True),
            priority=data.get("priority", 5),
            sync_interval=data.get("sync_interval", 60),
        )
        source.id = data.get("id", source.id)
        source.created_at = data.get("created_at", source.created_at)
        source.last_sync = data.get("last_sync")
        return source


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


class KnowledgeRef:
    """知识引用 - 用于记录检索到的知识"""

    def __init__(
        self,
        source_id: str,
        source_name: str,
        content: str,
        file_path: str = None,
        line_start: int = None,
        line_end: int = None,
        score: float = 0.0,
    ):
        self.source_id = source_id
        self.source_name = source_name
        self.content = content
        self.file_path = file_path
        self.line_start = line_start
        self.line_end = line_end
        self.score = score

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "content": self.content,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "score": self.score,
        }


class RAGSkillRetriever:
    """rag-skill 风格检索器 - 基于目录结构检索"""

    def __init__(self, knowledge_dir: Path):
        self.knowledge_dir = knowledge_dir

    def retrieve(self, query: str, top_k: int = 5) -> list[KnowledgeRef]:
        """检索知识"""
        results = []

        # 1. 查找 data_structure.md 了解目录结构
        data_structure = self.knowledge_dir / "data_structure.md"
        if data_structure.exists():
            structure_content = data_structure.read_text(encoding="utf-8")
            # 查找与问题相关的目录
            related_dirs = self._find_related_dirs(structure_content, query)
            for dir_path in related_dirs:
                # 递归检索目录下的文档
                dir_results = self._search_directory(dir_path, query, top_k // 2)
                results.extend(dir_results)

        # 2. 直接全文搜索
        if len(results) < top_k:
            direct_results = self._direct_search(query, top_k)
            results.extend(direct_results)

        # 去重并排序
        results = self._deduplicate(results)[:top_k]
        return results

    def _find_related_dirs(self, structure: str, query: str) -> list[Path]:
        """查找相关目录"""
        query_keywords = set(query.lower().split())
        related = []

        lines = structure.split("\n")
        for line in lines:
            # 查找目录或标题
            if "##" in line or "###" in line:
                dir_name = line.replace("#", "").strip()
                if query_keywords & set(dir_name.lower().split()):
                    # 尝试找到对应的目录
                    dir_path = self.knowledge_dir / dir_name
                    if dir_path.exists():
                        related.append(dir_path)

        return related[:3]

    def _search_directory(self, dir_path: Path, query: str, limit: int) -> list[KnowledgeRef]:
        """搜索目录"""
        results = []
        query_keywords = query.lower().split()

        # 搜索 Markdown 文件
        for md_file in dir_path.rglob("*.md"):
            if md_file.name == "data_structure.md":
                continue

            try:
                content = md_file.read_text(encoding="utf-8")
                # 简单关键词匹配
                if any(kw in content.lower() for kw in query_keywords):
                    # 查找匹配的行
                    lines = content.split("\n")
                    for i, line in enumerate(lines):
                        if any(kw in line.lower() for kw in query_keywords):
                            # 提取上下文
                            start = max(0, i - 3)
                            end = min(len(lines), i + 4)
                            context = "\n".join(lines[start:end])

                            results.append(KnowledgeRef(
                                source_id="local",
                                source_name=str(md_file.relative_to(self.knowledge_dir)),
                                content=context,
                                file_path=str(md_file),
                                line_start=i + 1,
                                line_end=i + 1,
                                score=1.0
                            ))

                            if len(results) >= limit:
                                return results
            except Exception as e:
                logger.warning(f"Failed to read {md_file}: {e}")

        return results

    def _direct_search(self, query: str, limit: int) -> list[KnowledgeRef]:
        """直接搜索"""
        results = []
        query_keywords = query.lower().split()

        for md_file in self.knowledge_dir.rglob("*.md"):
            if md_file.name == "data_structure.md":
                continue

            try:
                content = md_file.read_text(encoding="utf-8")
                if any(kw in content.lower() for kw in query_keywords):
                    # 简单返回文件的前几段
                            content = md_file.read_text(encoding="utf-8")
                            # 找到第一个匹配位置
                            idx = min(content.lower().find(kw) for kw in query_keywords if kw in content.lower())
                            # 提取附近内容
                            start = max(0, idx - 200)
                            end = min(len(content), idx + 500)
                            context = content[start:end]

                            results.append(KnowledgeRef(
                                source_id="local",
                                source_name=str(md_file.relative_to(self.knowledge_dir)),
                                content=context,
                                file_path=str(md_file),
                                score=0.8
                            ))

                            if len(results) >= limit:
                                return results
            except Exception:
                pass

        return results

    def _deduplicate(self, results: list[KnowledgeRef]) -> list[KnowledgeRef]:
        """去重"""
        seen = set()
        unique = []
        for r in results:
            key = r.file_path or r.content[:50]
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique


class BM25Retriever:
    """BM25 检索器"""

    def __init__(self):
        self.chunks: list[KnowledgeChunk] = []
        self.doc_lengths: list[int] = []
        self.avg_doc_length: float = 0
        self.k1 = 1.5
        self.b = 0.75

    def add_chunks(self, chunks: list[KnowledgeChunk]):
        """添加知识块"""
        self.chunks = chunks
        self.doc_lengths = [len(c.content) for c in chunks]
        self.avg_doc_length = sum(self.doc_lengths) / len(self.doc_lengths) if self.doc_lengths else 1

    def _tokenize(self, text: str) -> list[str]:
        """分词"""
        return re.findall(r'\w+', text.lower())

    def _calculate_idf(self, term: str) -> float:
        """计算 IDF"""
        containing_docs = sum(1 for chunk in self.chunks if term in chunk.content.lower())
        if containing_docs == 0:
            return 0
        return math.log((len(self.chunks) - containing_docs + 0.5) / (containing_docs + 0.5) + 1)

    def retrieve(self, query: str, top_k: int = 5) -> list[KnowledgeRef]:
        """BM25 检索"""
        if not self.chunks:
            return []

        query_terms = self._tokenize(query)
        scores = []

        for i, chunk in enumerate(self.chunks):
            doc_terms = self._tokenize(chunk.content)
            doc_tf = Counter(doc_terms)

            score = 0.0
            for term in query_terms:
                if term in doc_tf:
                    tf = doc_tf[term]
                    idf = self._calculate_idf(term)
                    # BM25 公式
                    numerator = tf * (self.k1 + 1)
                    denominator = tf + self.k1 * (1 - self.b + self.b * len(doc_terms) / self.avg_doc_length)
                    score += idf * numerator / denominator

            if score > 0:
                scores.append((score, chunk))

        scores.sort(key=lambda x: x[0], reverse=True)

        return [
            KnowledgeRef(
                source_id=chunk.source_id,
                source_name=chunk.metadata.get("source_name", chunk.source_id),
                content=chunk.content,
                score=score
            )
            for score, chunk in scores[:top_k]
        ]


class VectorRetriever:
    """简化版向量检索器"""

    def __init__(self):
        self.chunks: list[KnowledgeChunk] = []

    def add_chunks(self, chunks: list[KnowledgeChunk]):
        """添加知识块"""
        self.chunks = chunks

    def _simple_embed(self, text: str) -> list[float]:
        """简化版 embedding - 使用词频向量"""
        words = re.findall(r'\w+', text.lower())
        word_freq = Counter(words)
        # 取最常见的 100 个词作为维度
        vocab = [w for w, _ in word_freq.most_common(100)]
        vec = [word_freq.get(w, 0) for w in vocab]
        # 归一化
        total = sum(v * v for v in vec) ** 0.5
        return [v / total if total > 0 else 0 for v in vec]

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """余弦相似度"""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0
        return dot / (norm_a * norm_b)

    def retrieve(self, query: str, top_k: int = 5) -> list[KnowledgeRef]:
        """向量检索"""
        if not self.chunks:
            return []

        query_vec = self._simple_embed(query)
        scores = []

        for chunk in self.chunks:
            # 简化：每次重新计算（生产环境应该缓存）
            chunk_vec = self._simple_embed(chunk.content)
            score = self._cosine_similarity(query_vec, chunk_vec)
            if score > 0.01:  # 阈值过滤
                scores.append((score, chunk))

        scores.sort(key=lambda x: x[0], reverse=True)

        return [
            KnowledgeRef(
                source_id=chunk.source_id,
                source_name=chunk.metadata.get("source_name", chunk.source_id),
                content=chunk.content,
                score=score
            )
            for score, chunk in scores[:top_k]
        ]


class KnowledgeRAG:
    """Knowledge Base RAG System - Multi-mode Retrieval"""

    def __init__(self, storage_dir: Path = None, workspace_dir: Path = None):
        self.storage_dir = storage_dir or MEMORY_DIR / "knowledge"
        self.workspace_dir = workspace_dir or WORKSPACE_DIR
        self.sources_dir = self.storage_dir / "sources"
        self.chunks_dir = self.storage_dir / "chunks"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        self.chunks_dir.mkdir(parents=True, exist_ok=True)

        # Initialize retrievers
        self.rag_skill_retriever = RAGSkillRetriever(self.workspace_dir / "knowledge")
        self.bm25_retriever = BM25Retriever()
        self.vector_retriever = VectorRetriever()

        # Initialize vector store (SQLite + bge-small-zh)
        self.vector_store: VectorStore = get_vector_store()

        self._sources: dict[str, KnowledgeSource] = {}
        self._chunks: list[KnowledgeChunk] = []
        self._load_data()

    def _load_data(self):
        """加载数据"""
        # 加载知识源
        for file in self.sources_dir.glob("*.json"):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                source = KnowledgeSource.from_dict(data)
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
                    self._chunks.append(chunk)
            except Exception as e:
                logger.warning(f"Failed to load chunks: {e}")

        # 初始化 BM25 和向量检索器
        self.bm25_retriever.add_chunks(self._chunks)
        self.vector_retriever.add_chunks(self._chunks)

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
        # 更新检索器
        self.bm25_retriever.add_chunks(self._chunks)
        self.vector_retriever.add_chunks(self._chunks)

    # ========== 知识源管理 ==========

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

    def update_source(self, source_id: str, **kwargs) -> bool:
        """更新知识源"""
        source = self._sources.get(source_id)
        if not source:
            return False

        for key, value in kwargs.items():
            if hasattr(source, key):
                setattr(source, key, value)

        self._save_sources()
        return True

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

    def sync_source(self, source_id: str) -> bool:
        """同步知识源"""
        source = self._sources.get(source_id)
        if not source:
            return False

        if source.source_type == "local":
            # 同步本地目录
            self._sync_local_source(source)

        source.last_sync = datetime.now().isoformat()
        self._save_sources()
        return True

    def _sync_local_source(self, source: KnowledgeSource):
        """同步本地知识目录"""
        local_path = source.config.get("path")
        if not local_path:
            return

        path = Path(local_path)
        if not path.exists():
            logger.warning(f"Knowledge path not found: {local_path}")
            return

        # 扫描 Markdown 文件
        for md_file in path.rglob("*.md"):
            if md_file.name.startswith("."):
                continue

            try:
                content = md_file.read_text(encoding="utf-8")
                metadata = {
                    "source_name": str(md_file.relative_to(path)),
                    "file_path": str(md_file),
                }
                self.add_document(source.id, content, metadata)
            except Exception as e:
                logger.warning(f"Failed to sync {md_file}: {e}")

    # ========== Document Management ==========

    def add_document(self, source_id: str, content: str, metadata: dict = None):
        """Add document to knowledge base"""
        chunk_size = 1000
        overlap = 100

        chunks = []
        entries_for_vector_store = []

        for i in range(0, len(content), chunk_size - overlap):
            chunk_content = content[i:i + chunk_size]
            if chunk_content.strip():
                chunk = KnowledgeChunk(
                    source_id=source_id,
                    content=chunk_content,
                    metadata=metadata or {},
                )
                chunks.append(chunk)

                # Prepare for vector store
                entries_for_vector_store.append({
                    "content": chunk_content,
                    "metadata": {**(metadata or {}), "chunk_index": i},
                })

        self._chunks.extend(chunks)
        self._save_chunks()

        # Also add to vector store for semantic search
        if entries_for_vector_store:
            try:
                self.vector_store.add_batch(
                    entries=entries_for_vector_store,
                    source_type="knowledge",
                    source_id=source_id,
                )
            except Exception as e:
                logger.warning(f"Failed to add to vector store: {e}")

        logger.info(f"Added {len(chunks)} chunks from document")

        return len(chunks)

    # ========== Multi-mode Retrieval ==========

    def retrieve(
        self,
        query: str,
        method: Literal["auto", "rag-skill", "bm25", "vector", "embed"] = "auto",
        top_k: int = 5,
        source_ids: list[str] = None
    ) -> list[KnowledgeRef]:
        """
        Retrieve knowledge

        Args:
            query: Query text
            method: Retrieval method (auto/bm25/rag-skill/vector/embed)
            top_k: Number of results to return
            source_ids: Filter by source IDs
        """
        # Auto select best method
        if method == "auto":
            method = self._select_best_method(query)

        results = []

        if method == "rag-skill":
            # rag-skill style retrieval
            results = self.rag_skill_retriever.retrieve(query, top_k)
        elif method == "bm25":
            # BM25 retrieval
            results = self.bm25_retriever.retrieve(query, top_k)
        elif method == "vector":
            # Legacy vector retrieval
            results = self.vector_retriever.retrieve(query, top_k)
        elif method == "embed":
            # SQLite + bge-small-zh vector retrieval
            results = self._retrieve_from_vector_store(query, top_k, source_ids)

        # Source filtering
        if source_ids:
            results = [r for r in results if r.source_id in source_ids]

        return results

    def _retrieve_from_vector_store(
        self,
        query: str,
        top_k: int = 5,
        source_ids: list[str] = None
    ) -> list[KnowledgeRef]:
        """Retrieve from vector store (SQLite + bge-small-zh)"""
        # Use hybrid search for better results
        results = self.vector_store.search_hybrid(
            query=query,
            top_k=top_k,
            source_type="knowledge",
            source_id=source_ids[0] if source_ids and len(source_ids) == 1 else None,
        )

        # Convert to KnowledgeRef
        return [
            KnowledgeRef(
                source_id=r.get("source_id", "embed"),
                source_name=r["metadata"].get("source_name", r["source_type"]),
                content=r["content"],
                file_path=r["metadata"].get("file_path"),
                score=r["final_score"] if "final_score" in r else r["score"],
            )
            for r in results
        ]

    def _select_best_method(self, query: str) -> str:
        """Auto select best retrieval method"""
        # Check if vector store has data
        if self.vector_store.count(source_type="knowledge") > 0:
            # Use embed (SQLite + bge-small-zh) for better semantic understanding
            return "embed"

        # Check if knowledge directory exists
        knowledge_dir = self.workspace_dir / "knowledge"
        if knowledge_dir.exists() and (knowledge_dir / "data_structure.md").exists():
            # Use rag-skill if directory structure exists
            return "rag-skill"

        # Otherwise use BM25
        return "bm25"

    def retrieve_all_methods(
        self,
        query: str,
        top_k: int = 5
    ) -> dict[str, list[KnowledgeRef]]:
        """使用所有方式检索并合并结果"""
        results = {
            "rag-skill": self.retrieve(query, "rag-skill", top_k),
            "bm25": self.retrieve(query, "bm25", top_k),
            "vector": self.retrieve(query, "vector", top_k),
        }
        return results

    def augment_context(
        self,
        query: str,
        context: dict,
        method: str = "auto",
        top_k: int = 3
    ) -> dict:
        """增强上下文"""
        chunks = self.retrieve(query, method, top_k)

        if not chunks:
            return context

        # 构建知识上下文
        knowledge_context = "\n\n".join([
            f"[知识 {i+1} ({r.source_name})]: {r.content}"
            for i, r in enumerate(chunks)
        ])

        # 构建增强后的上下文
        augmented = {
            **context,
            "knowledge_context": knowledge_context,
            "knowledge_sources": [r.source_name for r in chunks],
            "knowledge_count": len(chunks),
            "knowledge_method": method if method != "auto" else self._select_best_method(query),
        }

        return augmented


# 全局实例
_rag: Optional[KnowledgeRAG] = None


def get_knowledge_rag() -> KnowledgeRAG:
    global _rag
    if _rag is None:
        _rag = KnowledgeRAG()
    return _rag


def reinit_knowledge_rag():
    """重新初始化知识库"""
    global _rag
    _rag = KnowledgeRAG()
    return _rag
