"""处理器基类"""

from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass


@dataclass
class KnowledgeResult:
    """知识检索结果"""
    content: str
    sources: list[dict]
    mode: str
    processing_time: float = 0.0
    llm_used: bool = False


class BaseProcessor(ABC):
    """处理器基类"""

    def __init__(self, config):
        self.config = config

    @abstractmethod
    async def process(self, query: str, chunks: list = None) -> KnowledgeResult:
        """处理知识"""
        pass
