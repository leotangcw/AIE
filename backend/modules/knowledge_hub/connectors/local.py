"""本地文件接入器"""

import re
from pathlib import Path
from typing import Optional
from loguru import logger

from .base import BaseConnector


class LocalConnector(BaseConnector):
    """本地文件接入器"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.path = config.get("path", "")
        self.file_types = config.get("file_types", [".md", ".txt"])
        self.chunk_size = config.get("chunk_size", 1000)
        self.overlap = config.get("overlap", 100)

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

        for ext in self.file_types:
            for file in path.rglob(f"*{ext}"):
                if file.name.startswith("."):
                    continue
                try:
                    content = file.read_text(encoding="utf-8")
                    # 简单分块
                    chunks = self._chunk_text(content)
                    documents.append({
                        "source": str(file.relative_to(path)),
                        "content": chunks,
                        "path": str(file)
                    })
                except Exception as e:
                    logger.warning(f"Failed to read {file}: {e}")

        return documents

    async def sync(self) -> int:
        """同步文档"""
        docs = await self.fetch()
        total_chunks = sum(len(d.get("content", [])) for d in docs)
        logger.info(f"Synced {len(docs)} files, {total_chunks} chunks")
        return total_chunks

    def _chunk_text(self, text: str) -> list[str]:
        """分块"""
        chunks = []
        for i in range(0, len(text), self.chunk_size - self.overlap):
            chunk = text[i:i + self.chunk_size]
            if chunk.strip():
                chunks.append(chunk)
        return chunks
