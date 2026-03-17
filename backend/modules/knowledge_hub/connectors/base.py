"""接入器基类"""

from abc import ABC, abstractmethod
from typing import Any


class BaseConnector(ABC):
    """知识源接入器基类"""

    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get("enabled", True)

    @abstractmethod
    async def connect(self) -> bool:
        """连接知识源"""
        pass

    @abstractmethod
    async def fetch(self, query: str = None) -> list[dict]:
        """获取知识"""
        pass

    @abstractmethod
    async def sync(self) -> int:
        """同步知识"""
        pass
