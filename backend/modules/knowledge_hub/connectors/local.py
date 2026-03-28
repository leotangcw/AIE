"""本地文件接入器

支持多种分段策略：
- 固定长度分段
- 语义分段（按段落/标题）
- 父子分段（文档+段落两级）
- 递归分段
"""

import re
from pathlib import Path
from typing import Optional, Iterator
from loguru import logger
from dataclasses import dataclass

from .base import BaseConnector
from ..config import ChunkConfig, ChunkStrategy


@dataclass
class Chunk:
    """分段数据结构"""
    content: str
    metadata: dict
    parent_id: str | None = None
    chunk_id: str | None = None


class TextChunker:
    """文本分段器 - 支持多种分段策略"""

    def __init__(self, config: ChunkConfig):
        self.config = config

    def chunk(self, text: str, source: str = "") -> list[Chunk]:
        """根据配置的分段策略进行分段"""
        strategy = self.config.strategy

        if strategy == ChunkStrategy.FIXED:
            return self._chunk_fixed(text, source)
        elif strategy == ChunkStrategy.SEMANTIC:
            return self._chunk_semantic(text, source)
        elif strategy == ChunkStrategy.PARENT_CHILD:
            return self._chunk_parent_child(text, source)
        elif strategy == ChunkStrategy.RECURSIVE:
            return self._chunk_recursive(text, source)
        else:
            return self._chunk_fixed(text, source)

    def _chunk_fixed(self, text: str, source: str) -> list[Chunk]:
        """固定长度分段"""
        chunks = []
        chunk_size = self.config.chunk_size
        overlap = self.config.chunk_overlap

        start = 0
        chunk_idx = 0
        while start < len(text):
            end = start + chunk_size
            chunk_text = text[start:end]

            if chunk_text.strip():
                chunks.append(Chunk(
                    content=chunk_text,
                    metadata={
                        "source": source,
                        "chunk_index": chunk_idx,
                        "strategy": "fixed",
                        "start": start,
                        "end": min(end, len(text))
                    },
                    chunk_id=f"{source}#chunk-{chunk_idx}"
                ))

            chunk_idx += 1
            start = end - overlap if end < len(text) else end

        return chunks

    def _chunk_semantic(self, text: str, source: str) -> list[Chunk]:
        """语义分段 - 按段落和标题分割"""
        chunks = []
        separators = self.config.separators

        # 先按标题分割（Markdown 标题）
        sections = self._split_by_headers(text)

        chunk_idx = 0
        for section in sections:
            section_text = section["content"]
            section_header = section.get("header", "")

            # 如果段落太长，按分隔符进一步分割
            if len(section_text) > self.config.chunk_size:
                sub_chunks = self._split_by_separators(section_text, separators)
                for sub_text in sub_chunks:
                    if len(sub_text.strip()) > 50:  # 忽略太短的片段
                        chunks.append(Chunk(
                            content=sub_text,
                            metadata={
                                "source": source,
                                "chunk_index": chunk_idx,
                                "strategy": "semantic",
                                "section_header": section_header,
                            },
                            chunk_id=f"{source}#chunk-{chunk_idx}"
                        ))
                        chunk_idx += 1
            else:
                if len(section_text.strip()) > 50:
                    chunks.append(Chunk(
                        content=section_text,
                        metadata={
                            "source": source,
                            "chunk_index": chunk_idx,
                            "strategy": "semantic",
                            "section_header": section_header,
                        },
                        chunk_id=f"{source}#chunk-{chunk_idx}"
                    ))
                    chunk_idx += 1

        return chunks

    def _chunk_parent_child(self, text: str, source: str) -> list[Chunk]:
        """父子分段 - 文档级（父）+ 段落级（子）"""
        chunks = []

        # 创建父分段（整个文档的摘要或前N字符）
        parent_content = text[:self.config.parent_chunk_size]
        parent_id = f"{source}#parent"
        parent_chunk = Chunk(
            content=parent_content,
            metadata={
                "source": source,
                "level": "parent",
                "strategy": "parent_child",
            },
            chunk_id=parent_id
        )
        chunks.append(parent_chunk)

        # 创建子分段
        separators = self.config.separators
        sub_chunks = self._split_by_separators(text, separators)

        chunk_idx = 0
        for sub_text in sub_chunks:
            if len(sub_text.strip()) > 50:
                chunks.append(Chunk(
                    content=sub_text,
                    metadata={
                        "source": source,
                        "level": "child",
                        "chunk_index": chunk_idx,
                        "strategy": "parent_child",
                    },
                    parent_id=parent_id,
                    chunk_id=f"{source}#child-{chunk_idx}"
                ))
                chunk_idx += 1

        return chunks

    def _chunk_recursive(self, text: str, source: str) -> list[Chunk]:
        """递归分段 - 按分隔符层级递归分割"""
        chunks = []

        def split_recursive(txt: str, sep_idx: int = 0) -> list[str]:
            if sep_idx >= len(self.config.separators):
                # 最后使用固定长度分割
                return self._fixed_split(txt)

            sep = self.config.separators[sep_idx]
            parts = txt.split(sep)

            result = []
            current = ""
            for part in parts:
                if len(current) + len(part) <= self.config.chunk_size:
                    current += part + sep
                else:
                    if current.strip():
                        result.append(current)
                    if len(part) > self.config.chunk_size:
                        # 递归分割
                        result.extend(split_recursive(part, sep_idx + 1))
                    else:
                        current = part + sep

            if current.strip():
                result.append(current)

            return result

        parts = split_recursive(text)
        chunk_idx = 0
        for part in parts:
            if len(part.strip()) > 50:
                chunks.append(Chunk(
                    content=part,
                    metadata={
                        "source": source,
                        "chunk_index": chunk_idx,
                        "strategy": "recursive",
                    },
                    chunk_id=f"{source}#chunk-{chunk_idx}"
                ))
                chunk_idx += 1

        return chunks

    def _split_by_headers(self, text: str) -> list[dict]:
        """按 Markdown 标题分割"""
        sections = []
        current_section = {"header": "", "content": ""}

        lines = text.split("\n")
        for line in lines:
            header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if header_match:
                if current_section["content"].strip():
                    sections.append(current_section)
                current_section = {
                    "header": header_match.group(2).strip(),
                    "content": line + "\n"
                }
            else:
                current_section["content"] += line + "\n"

        if current_section["content"].strip():
            sections.append(current_section)

        return sections

    def _split_by_separators(self, text: str, separators: list[str]) -> list[str]:
        """按分隔符分割"""
        result = [text]
        for sep in separators:
            new_result = []
            for part in result:
                new_result.extend(part.split(sep))
            result = new_result
        return [p for p in result if p.strip()]

    def _fixed_split(self, text: str) -> list[str]:
        """固定长度分割"""
        result = []
        for i in range(0, len(text), self.config.chunk_size - self.config.chunk_overlap):
            result.append(text[i:i + self.config.chunk_size])
        return result


class LocalConnector(BaseConnector):
    """本地文件接入器"""

    def __init__(self, config: dict | ChunkConfig):
        super().__init__(config)
        # 支持传入 ChunkConfig 对象或字典
        if isinstance(config, ChunkConfig):
            self.chunk_config = config
            self.path = config.get("path", "") if isinstance(config, dict) else ""
            self.file_types = [".md", ".txt"]
            self.recursive = True
        else:
            self.path = config.get("path", "")
            self.file_types = config.get("file_types", [".md", ".txt"])
            self.recursive = config.get("recursive", True)
            # 创建分段配置
            self.chunk_config = ChunkConfig(
                strategy=ChunkStrategy(config.get("chunk_strategy", "fixed")),
                chunk_size=config.get("chunk_size", 1000),
                chunk_overlap=config.get("overlap", 100),
                parent_chunk_size=config.get("parent_chunk_size", 3000),
                separators=config.get("separators", ["\n\n", "\n", "。", "！", "？", "；"])
            )

        self._chunker = TextChunker(self.chunk_config)
        self._file_cache: dict[str, float] = {}  # 文件路径 -> 修改时间

    async def connect(self) -> bool:
        """验证路径是否存在"""
        p = Path(self.path)
        return p.exists() and p.is_dir()

    async def fetch(self, query: str = None) -> list[dict]:
        """获取所有文档"""
        if not await self.connect():
            return []

        documents = []
        path = Path(self.path)
        glob_method = path.rglob if self.recursive else path.glob

        for ext in self.file_types:
            for file in glob_method(f"*{ext}"):
                if file.name.startswith("."):
                    continue
                try:
                    doc = self._process_file(file, path)
                    if doc:
                        documents.append(doc)
                except Exception as e:
                    logger.warning(f"Failed to read {file}: {e}")

        return documents

    def _process_file(self, file: Path, base_path: Path) -> dict | None:
        """处理单个文件"""
        # 检查文件编码
        try:
            content = file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = file.read_text(encoding="gbk")
            except:
                logger.warning(f"Cannot decode file: {file}")
                return None

        relative_path = str(file.relative_to(base_path))

        # 使用分段器进行分段
        chunks = self._chunker.chunk(content, relative_path)

        # 转换为兼容格式
        chunk_contents = [c.content for c in chunks]
        chunk_metadata = [c.metadata for c in chunks]

        return {
            "source": relative_path,
            "content": chunk_contents,
            "chunks": [{"content": c.content, "metadata": c.metadata, "id": c.chunk_id} for c in chunks],
            "path": str(file),
            "metadata": {
                "file_size": file.stat().st_size,
                "modified_time": file.stat().st_mtime,
            }
        }

    async def sync(self) -> int:
        """同步文档"""
        docs = await self.fetch()
        total_chunks = sum(len(d.get("chunks", [])) for d in docs)
        logger.info(f"Synced {len(docs)} files, {total_chunks} chunks")
        return total_chunks

    async def fetch_incremental(self) -> list[dict]:
        """增量获取变更的文件"""
        if not await self.connect():
            return []

        changed_docs = []
        path = Path(self.path)
        glob_method = path.rglob if self.recursive else path.glob

        for ext in self.file_types:
            for file in glob_method(f"*{ext}"):
                if file.name.startswith("."):
                    continue

                mtime = file.stat().st_mtime
                file_key = str(file)

                # 检查是否变更
                if file_key in self._file_cache:
                    if self._file_cache[file_key] >= mtime:
                        continue

                # 处理变更的文件
                try:
                    doc = self._process_file(file, path)
                    if doc:
                        changed_docs.append(doc)
                        self._file_cache[file_key] = mtime
                except Exception as e:
                    logger.warning(f"Failed to process {file}: {e}")

        return changed_docs

    def get_file_count(self) -> int:
        """获取文件数量"""
        if not Path(self.path).exists():
            return 0
        count = 0
        path = Path(self.path)
        glob_method = path.rglob if self.recursive else path.glob
        for ext in self.file_types:
            for _ in glob_method(f"*{ext}"):
                if not _.name.startswith("."):
                    count += 1
        return count
