"""GraphRAG 模块

基于 LightRAG 的知识图谱检索模块，提供：
- 文档索引与实体关系抽取
- 多模式知识检索（local/global/hybrid/mix）
- 用户画像管理
- 会话知识图谱
- 知识检索增强

使用示例：
```python
from backend.modules.graph_rag import GraphRAGClient, get_graph_rag

# 获取客户端
client = await get_graph_rag(namespace="my_docs")

# 索引文档
result = await client.insert("AIE 是一个企业级 AI 办公助手...")
print(f"成功: {result.success}")

# 查询
result = await client.query("AIE 的主要功能是什么？")
print(result.content)
```

用户画像：
```python
from backend.modules.graph_rag.integrations import UserProfileManager

profile = UserProfileManager(user_id="user_123")
await profile.extract_from_conversation("我喜欢用 Python 写代码...")
interests = await profile.get_interests()
```

会话知识图谱：
```python
from backend.modules.graph_rag.integrations import SessionKnowledgeGraph

session_kg = SessionKnowledgeGraph(session_id="session_abc")
await session_kg.add_exchange(user_msg="...", assistant_msg="...")
context = await session_kg.get_context_for_query("项目开发")
```

Agent 工具：
```python
from backend.modules.graph_rag import register_graph_rag_tools

# 注册工具到 ToolRegistry
register_graph_rag_tools(tool_registry)
```
"""

# 核心组件
from .core import (
    GraphRAGClient,
    get_graph_rag,
    index_documents,
    query_knowledge,
    LIGHTERAG_AVAILABLE,
)

# 配置
from .config import (
    GraphRAGSettings,
    NamespaceConfig,
    GraphRAGStats,
    QueryResult,
    InsertResult,
    DEFAULT_WORKING_DIR,
    DEFAULT_MODE,
    DEFAULT_TOP_K,
    DEFAULT_CHUNK_TOP_K,
)

# 集成
from .integrations import (
    UserProfileManager,
    SessionKnowledgeGraph,
    GraphEnhancedProcessor,
)

# API 路由
from .api import router as api_router

# Agent 工具
from .skill import (
    GraphRAGIndexTool,
    GraphRAGQueryTool,
    GraphRAGStatsTool,
    GraphRAGClearTool,
    register_graph_rag_tools,
)

__all__ = [
    # 核心
    "GraphRAGClient",
    "get_graph_rag",
    "index_documents",
    "query_knowledge",
    "LIGHTERAG_AVAILABLE",
    # 配置
    "GraphRAGSettings",
    "NamespaceConfig",
    "GraphRAGStats",
    "QueryResult",
    "InsertResult",
    "DEFAULT_WORKING_DIR",
    "DEFAULT_MODE",
    "DEFAULT_TOP_K",
    "DEFAULT_CHUNK_TOP_K",
    # 集成
    "UserProfileManager",
    "SessionKnowledgeGraph",
    "GraphEnhancedProcessor",
    # API
    "api_router",
    # Agent 工具
    "GraphRAGIndexTool",
    "GraphRAGQueryTool",
    "GraphRAGStatsTool",
    "GraphRAGClearTool",
    "register_graph_rag_tools",
]

__version__ = "1.0.0"
