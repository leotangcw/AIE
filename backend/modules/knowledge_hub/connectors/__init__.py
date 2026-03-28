"""知识接入器"""

from .base import BaseConnector
from .local import LocalConnector
from .database import DatabaseConnector
from .web_search import WebSearchConnector

__all__ = [
    "BaseConnector",
    "LocalConnector",
    "DatabaseConnector",
    "WebSearchConnector",
]
