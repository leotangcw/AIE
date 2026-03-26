"""GraphRAG 模块集成

提供与 AIE 其他模块的集成接口。
"""

from .user_profile import UserProfileManager
from .session_kg import SessionKnowledgeGraph
from .knowledge_hub import GraphEnhancedProcessor

__all__ = [
    "UserProfileManager",
    "SessionKnowledgeGraph",
    "GraphEnhancedProcessor",
]
