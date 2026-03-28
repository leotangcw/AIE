# LightRAG 集成到 AIE 的设计方案

## 1. LightRAG 核心能力分析

### 1.1 架构概述

LightRAG 是一个基于知识图谱的高效 RAG 框架，核心特性包括：

```
┌─────────────────────────────────────────────────────────────┐
│                      LightRAG Core                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Entity      │  │ Relation    │  │ Knowledge Graph     │  │
│  │ Extraction  │──│ Building    │──│ (NetworkX/Neo4j)    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│         │                │                    │              │
│         ▼                ▼                    ▼              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              Multi-Modal Query Engine                    ││
│  │  ┌───────┐ ┌───────┐ ┌────────┐ ┌───────┐ ┌───────┐    ││
│  │  │ local │ │global │ │hybrid  │ │ naive │ │  mix  │    ││
│  │  └───────┘ └───────┘ └────────┘ └───────┘ └───────┘    ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### 1.2 核心组件

| 组件 | 功能 | 作用 |
|------|------|------|
| `LightRAG` | 主类 | 协调文档索引、查询、存储管理 |
| `operate.py` | 核心操作 | 实体抽取、关系构建、多模式查询 |
| `BaseGraphStorage` | 图存储抽象 | 知识图谱存储接口 |
| `BaseVectorStorage` | 向量存储抽象 | 实体/关系/文档块嵌入 |
| `BaseKVStorage` | KV存储抽象 | 文本块、LLM缓存 |
| `QueryParam` | 查询参数 | 配置检索模式、Token限制等 |

### 1.3 查询模式

| 模式 | 描述 | 适用场景 |
|------|------|----------|
| `local` | 基于实体的局部检索 | 具体事实查询 |
| `global` | 基于社区的全局检索 | 概括性问题 |
| `hybrid` | 混合local+global | 平衡型查询 |
| `naive` | 纯向量检索 | 简单相似度搜索 |
| `mix` | KG+向量+重排序 | 最高质量检索 |

### 1.4 存储后端

- **图存储**: NetworkX(默认), Neo4j, PostgreSQL, Memgraph
- **向量存储**: NanoVectorDB(默认), Milvus, Qdrant, Faiss
- **KV存储**: JSON文件, Redis, PostgreSQL, MongoDB

## 2. AIE 集成架构设计

### 2.1 模块定位

将 LightRAG 封装为 AIE 的**独立公共模块**，提供统一的知识图谱检索能力：

```
AIE/backend/modules/
├── graph_rag/                    # 新增：知识图谱RAG模块
│   ├── __init__.py
│   ├── core.py                   # LightRAG 核心封装
│   ├── config.py                 # 配置模型
│   ├── storage/                  # 存储适配层
│   │   ├── __init__.py
│   │   ├── graph.py              # 图存储适配
│   │   ├── vector.py             # 向量存储适配
│   │   └── kv.py                 # KV存储适配
│   ├── operators/                # 操作封装
│   │   ├── __init__.py
│   │   ├── indexer.py            # 文档索引
│   │   └── retriever.py          # 知识检索
│   ├── api.py                    # REST API
│   └── skill.py                  # Agent技能封装
```

### 2.2 与现有模块的关系

```
┌──────────────────────────────────────────────────────────────┐
│                        AIE System                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐    ┌─────────────────┐                  │
│  │   Agent Core    │    │  Skills System  │                  │
│  │  (主控制器)      │    │  (技能调用)      │                  │
│  └────────┬────────┘    └────────┬────────┘                  │
│           │                      │                           │
│           ▼                      ▼                           │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                    graph_rag 模块                        │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │ │
│  │  │   Indexer   │  │  Retriever  │  │  GraphManager   │  │ │
│  │  │  (文档索引)  │  │  (知识检索)  │  │  (图谱管理)      │  │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘  │ │
│  └─────────────────────────────────────────────────────────┘ │
│           │                      │                           │
│           ▼                      ▼                           │
│  ┌─────────────────┐    ┌─────────────────┐                  │
│  │ knowledge_hub   │    │    memory       │                  │
│  │  (知识源管理)    │    │  (用户记忆)      │                  │
│  └─────────────────┘    └─────────────────┘                  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## 3. 调用场景分析

### 3.1 场景一：知识检索模块增强

**当前问题**：
- `knowledge_hub` 的向量检索仅支持简单的相似度匹配
- 缺少实体关系抽取和知识图谱构建
- 无法进行多跳推理

**集成方案**：
```python
# backend/modules/knowledge_hub/processors/graph_processor.py

from backend.modules.graph_rag import GraphRAGClient

class GraphEnhancedProcessor:
    """基于知识图谱的增强检索处理器"""

    def __init__(self, config: dict, hub):
        self.graph_rag = GraphRAGClient(namespace="knowledge_hub")
        self.hub = hub

    async def process(self, query: str, **options) -> KnowledgeResult:
        # 1. 从知识图谱检索相关实体和关系
        kg_result = await self.graph_rag.query(
            query,
            mode="mix",  # 混合模式，最高质量
            top_k=options.get("top_k", 10)
        )

        # 2. 补充原始文档上下文
        sources = []
        for chunk in kg_result.get("chunks", []):
            sources.append({
                "content": chunk["content"],
                "source": chunk.get("source", "knowledge_graph"),
                "score": chunk.get("score", 0.0),
                "entities": chunk.get("entities", []),
                "relations": chunk.get("relations", [])
            })

        return KnowledgeResult(
            content=kg_result.get("answer", ""),
            sources=sources,
            mode="graph",
            processing_time=kg_result.get("processing_time", 0.0)
        )
```

### 3.2 场景二：用户长期记忆/画像

**需求**：
- 从用户对话中抽取关键信息
- 构建用户偏好、习惯、兴趣的知识图谱
- 支持用户画像查询

**集成方案**：
```python
# backend/modules/memory/user_profile.py

from backend.modules.graph_rag import GraphRAGClient

class UserProfileManager:
    """用户画像管理器 - 基于 LightRAG"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        # 每个用户独立的命名空间
        self.graph_rag = GraphRAGClient(
            namespace=f"user_profile_{user_id}",
            workspace="user_profiles"
        )

    async def extract_and_store(self, conversation: str):
        """从对话中抽取用户画像信息并存储"""
        # LightRAG 会自动抽取实体和关系
        # 实体类型：偏好、习惯、兴趣、职业、家庭等
        await self.graph_rag.insert(
            conversation,
            entity_types=["偏好", "习惯", "兴趣", "职业", "家庭成员", "目标"]
        )

    async def query_profile(self, query: str) -> dict:
        """查询用户画像"""
        result = await self.graph_rag.query(
            query,
            mode="hybrid",
            only_need_context=True
        )
        return result

    async def get_user_interests(self) -> list[str]:
        """获取用户兴趣列表"""
        result = await self.graph_rag.query(
            "用户的兴趣爱好有哪些？",
            mode="local"
        )
        return self._parse_interests(result)

    async def get_user_preferences(self) -> dict:
        """获取用户偏好设置"""
        result = await self.graph_rag.query(
            "用户在工作、生活、学习方面有什么偏好？",
            mode="global"
        )
        return self._parse_preferences(result)
```

### 3.3 场景三：Agent Skill 工具

**需求**：
- 作为 Agent 可调用的标准工具
- 支持文档索引和知识查询
- 支持多个知识库命名空间

**集成方案**：
```python
# backend/modules/graph_rag/skill.py

from backend.modules.tools.base import Tool

class GraphRAGIndexTool(Tool):
    """知识图谱索引工具"""

    name = "graph_rag_index"
    description = "将文档内容索引到知识图谱，支持后续智能检索"
    parameters = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "要索引的文档内容"
            },
            "namespace": {
                "type": "string",
                "description": "知识库命名空间，用于隔离不同知识库",
                "default": "default"
            },
            "doc_type": {
                "type": "string",
                "description": "文档类型：document/conversation/code",
                "default": "document"
            }
        },
        "required": ["content"]
    }

    async def execute(self, content: str, namespace: str = "default",
                      doc_type: str = "document") -> dict:
        client = GraphRAGClient(namespace=namespace)
        await client.insert(content, doc_type=doc_type)
        return {"status": "indexed", "namespace": namespace}


class GraphRAGQueryTool(Tool):
    """知识图谱查询工具"""

    name = "graph_rag_query"
    description = "从知识图谱中检索相关信息，支持多种查询模式"
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "查询问题"
            },
            "namespace": {
                "type": "string",
                "description": "知识库命名空间",
                "default": "default"
            },
            "mode": {
                "type": "string",
                "enum": ["local", "global", "hybrid", "naive", "mix"],
                "description": "查询模式",
                "default": "hybrid"
            },
            "top_k": {
                "type": "integer",
                "description": "返回结果数量",
                "default": 10
            }
        },
        "required": ["query"]
    }

    async def execute(self, query: str, namespace: str = "default",
                      mode: str = "hybrid", top_k: int = 10) -> dict:
        client = GraphRAGClient(namespace=namespace)
        result = await client.query(query, mode=mode, top_k=top_k)
        return result
```

### 3.4 场景四：会话记忆增强

**需求**：
- 从历史对话中抽取关键实体和关系
- 构建会话知识图谱
- 支持上下文感知的对话

**集成方案**：
```python
# backend/modules/session/session_kg.py

from backend.modules.graph_rag import GraphRAGClient

class SessionKnowledgeGraph:
    """会话级知识图谱"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.graph_rag = GraphRAGClient(
            namespace=f"session_{session_id}",
            workspace="sessions"
        )

    async def add_exchange(self, user_msg: str, assistant_msg: str):
        """添加对话交换到知识图谱"""
        content = f"用户: {user_msg}\n助手: {assistant_msg}"
        await self.graph_rag.insert(content)

    async def get_context_for_query(self, query: str) -> str:
        """获取与当前查询相关的历史上下文"""
        result = await self.graph_rag.query(
            query,
            mode="local",
            only_need_context=True
        )
        return result.get("context", "")

    async def get_related_entities(self, entity_name: str) -> list:
        """获取与指定实体相关的所有实体"""
        # 利用知识图谱的关系查询能力
        result = await self.graph_rag.query(
            f"与 {entity_name} 相关的内容",
            mode="local",
            only_need_context=True
        )
        return result.get("entities", [])
```

## 4. 详细实现设计

### 4.1 核心封装类

```python
# backend/modules/graph_rag/core.py

from dataclasses import dataclass, field
from typing import Optional, Literal, Any
from pathlib import Path
import asyncio

from loguru import logger

# 条件导入 LightRAG
try:
    from lightrag import LightRAG as _LightRAG
    from lightrag.base import QueryParam
    from lightrag.llm.openai import gpt_4o_mini_complete, openai_embed
    LIGHTERAG_AVAILABLE = True
except ImportError:
    LIGHTERAG_AVAILABLE = False
    _LightRAG = None

from backend.utils.paths import MEMORY_DIR


@dataclass
class GraphRAGConfig:
    """GraphRAG 配置"""
    enabled: bool = True
    working_dir: str = str(MEMORY_DIR / "graph_rag")

    # 存储配置
    kv_storage: str = "JsonKVStorage"
    vector_storage: str = "NanoVectorDBStorage"
    graph_storage: str = "NetworkXStorage"

    # 查询配置
    default_mode: Literal["local", "global", "hybrid", "naive", "mix"] = "hybrid"
    top_k: int = 10
    chunk_top_k: int = 5

    # LLM 配置
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536


class GraphRAGClient:
    """LightRAG 客户端封装

    提供统一的接口用于：
    - 文档索引
    - 知识查询
    - 图谱管理
    """

    _instances: dict[str, "GraphRAGClient"] = {}

    def __init__(
        self,
        namespace: str = "default",
        workspace: str = "default",
        config: GraphRAGConfig | None = None
    ):
        self.namespace = namespace
        self.workspace = workspace
        self.config = config or GraphRAGConfig()

        self._rag: Optional[_LightRAG] = None
        self._initialized = False

    @classmethod
    def get_instance(cls, namespace: str, workspace: str = "default") -> "GraphRAGClient":
        """获取单例实例"""
        key = f"{workspace}:{namespace}"
        if key not in cls._instances:
            cls._instances[key] = cls(namespace=namespace, workspace=workspace)
        return cls._instances[key]

    async def initialize(self):
        """初始化 LightRAG"""
        if not LIGHTERAG_AVAILABLE:
            logger.warning("LightRAG not installed, GraphRAG features disabled")
            return False

        if self._initialized:
            return True

        try:
            import os
            working_dir = Path(self.config.working_dir) / self.workspace / self.namespace
            working_dir.mkdir(parents=True, exist_ok=True)

            self._rag = _LightRAG(
                working_dir=str(working_dir),
                kv_storage=self.config.kv_storage,
                vector_storage=self.config.vector_storage,
                graph_storage=self.config.graph_storage,
                llm_model_func=gpt_4o_mini_complete,
                embedding_func=openai_embed,
            )

            await self._rag.initialize_storages()
            self._initialized = True
            logger.info(f"GraphRAG initialized: {self.workspace}/{self.namespace}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize GraphRAG: {e}")
            return False

    async def insert(
        self,
        content: str | list[str],
        doc_type: str = "document",
        file_paths: list[str] | None = None
    ) -> bool:
        """插入文档到知识图谱

        Args:
            content: 文档内容或内容列表
            doc_type: 文档类型
            file_paths: 文件路径（用于引用）

        Returns:
            是否成功
        """
        if not self._initialized:
            await self.initialize()

        if not self._rag:
            return False

        try:
            if isinstance(content, str):
                content = [content]

            await self._rag.ainsert(content, file_paths=file_paths)
            logger.info(f"Inserted {len(content)} documents to GraphRAG")
            return True

        except Exception as e:
            logger.error(f"Failed to insert to GraphRAG: {e}")
            return False

    async def query(
        self,
        query: str,
        mode: str | None = None,
        top_k: int | None = None,
        only_need_context: bool = False,
        stream: bool = False
    ) -> dict[str, Any]:
        """查询知识图谱

        Args:
            query: 查询问题
            mode: 查询模式 (local/global/hybrid/naive/mix)
            top_k: 返回结果数量
            only_need_context: 仅返回上下文，不生成回答
            stream: 是否流式返回

        Returns:
            查询结果
        """
        if not self._initialized:
            await self.initialize()

        if not self._rag:
            return {"error": "GraphRAG not initialized", "content": ""}

        try:
            param = QueryParam(
                mode=mode or self.config.default_mode,
                top_k=top_k or self.config.top_k,
                chunk_top_k=self.config.chunk_top_k,
                only_need_context=only_need_context,
                stream=stream
            )

            result = await self._rag.aquery(query, param=param)

            if hasattr(result, '__aiter__'):
                # 流式结果
                return {"stream": result, "mode": mode}
            else:
                # 非流式结果
                return {
                    "content": result if isinstance(result, str) else getattr(result, "content", str(result)),
                    "mode": mode or self.config.default_mode,
                }

        except Exception as e:
            logger.error(f"GraphRAG query failed: {e}")
            return {"error": str(e), "content": ""}

    async def get_graph_stats(self) -> dict:
        """获取图谱统计信息"""
        if not self._initialized:
            await self.initialize()

        if not self._rag:
            return {"available": False}

        try:
            # 获取节点和边数量
            stats = {
                "available": True,
                "namespace": self.namespace,
                "workspace": self.workspace,
            }
            return stats

        except Exception as e:
            return {"available": False, "error": str(e)}

    async def clear(self) -> bool:
        """清空当前命名空间的知识图谱"""
        if not self._initialized:
            return True

        if not self._rag:
            return False

        try:
            await self._rag.adelete_by_ids(["*"])
            logger.info(f"Cleared GraphRAG: {self.namespace}")
            return True

        except Exception as e:
            logger.error(f"Failed to clear GraphRAG: {e}")
            return False

    async def finalize(self):
        """清理资源"""
        if self._rag:
            try:
                await self._rag.finalize_storages()
            except Exception:
                pass
        self._initialized = False
```

### 4.2 配置模型

```python
# backend/modules/graph_rag/config.py

from pydantic import BaseModel, Field
from typing import Literal, Optional


class GraphRAGSettings(BaseModel):
    """GraphRAG 模块配置"""

    enabled: bool = Field(default=True, description="是否启用 GraphRAG")

    # 存储配置
    storage_type: Literal["file", "postgres", "neo4j"] = Field(
        default="file",
        description="存储类型"
    )
    working_dir: str = Field(
        default="memory/graph_rag",
        description="工作目录（文件存储模式）"
    )

    # 查询配置
    default_mode: Literal["local", "global", "hybrid", "naive", "mix"] = Field(
        default="hybrid",
        description="默认查询模式"
    )
    top_k: int = Field(default=10, ge=1, le=100, description="默认返回结果数")
    chunk_top_k: int = Field(default=5, ge=1, le=50, description="文档块返回数")

    # Token 限制
    max_entity_tokens: int = Field(default=6000, description="实体上下文最大 Token")
    max_relation_tokens: int = Field(default=8000, description="关系上下文最大 Token")
    max_total_tokens: int = Field(default=30000, description="总上下文最大 Token")

    # 实体抽取配置
    entity_types: list[str] = Field(
        default=["人物", "组织", "地点", "事件", "概念", "产品"],
        description="实体类型列表"
    )
    max_gleaning: int = Field(default=1, description="最大抽取轮数")


class GraphRAGNamespaceConfig(BaseModel):
    """命名空间配置"""

    namespace: str = Field(description="命名空间名称")
    workspace: str = Field(default="default", description="工作空间")
    description: str = Field(default="", description="描述")
    entity_types: Optional[list[str]] = Field(default=None, description="自定义实体类型")
    enabled: bool = Field(default=True, description="是否启用")
```

### 4.3 API 端点设计

```python
# backend/modules/graph_rag/api.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal

router = APIRouter(prefix="/api/graph_rag", tags=["graph_rag"])


class InsertRequest(BaseModel):
    content: str | list[str]
    namespace: str = "default"
    workspace: str = "default"
    file_paths: Optional[list[str]] = None


class QueryRequest(BaseModel):
    query: str
    namespace: str = "default"
    workspace: str = "default"
    mode: Literal["local", "global", "hybrid", "naive", "mix"] = "hybrid"
    top_k: int = 10
    only_need_context: bool = False


@router.post("/insert")
async def insert_document(request: InsertRequest):
    """索引文档到知识图谱"""
    from .core import GraphRAGClient

    client = GraphRAGClient(
        namespace=request.namespace,
        workspace=request.workspace
    )

    success = await client.insert(
        content=request.content,
        file_paths=request.file_paths
    )

    if success:
        return {"code": 0, "message": "Document indexed successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to index document")


@router.post("/query")
async def query_knowledge(request: QueryRequest):
    """查询知识图谱"""
    from .core import GraphRAGClient

    client = GraphRAGClient(
        namespace=request.namespace,
        workspace=request.workspace
    )

    result = await client.query(
        query=request.query,
        mode=request.mode,
        top_k=request.top_k,
        only_need_context=request.only_need_context
    )

    return {"code": 0, "data": result}


@router.get("/namespaces")
async def list_namespaces():
    """列出所有命名空间"""
    # TODO: 实现命名空间列表
    return {"code": 0, "data": []}


@router.get("/stats/{namespace}")
async def get_stats(namespace: str, workspace: str = "default"):
    """获取命名空间统计信息"""
    from .core import GraphRAGClient

    client = GraphRAGClient(namespace=namespace, workspace=workspace)
    stats = await client.get_graph_stats()

    return {"code": 0, "data": stats}


@router.delete("/namespace/{namespace}")
async def clear_namespace(namespace: str, workspace: str = "default"):
    """清空命名空间"""
    from .core import GraphRAGClient

    client = GraphRAGClient(namespace=namespace, workspace=workspace)
    success = await client.clear()

    if success:
        return {"code": 0, "message": "Namespace cleared"}
    else:
        raise HTTPException(status_code=500, detail="Failed to clear namespace")
```

## 5. 依赖和安装

### 5.1 requirements.txt 新增

```txt
# GraphRAG (LightRAG)
lightrag-hku>=1.0.0
networkx>=3.0
tiktoken>=0.5.0
```

### 5.2 可选依赖

```txt
# 高级存储后端 (可选)
neo4j>=5.0.0          # Neo4j 图存储
pymilvus>=2.3.0       # Milvus 向量存储
qdrant-client>=1.6.0  # Qdrant 向量存储
redis>=5.0.0          # Redis KV 存储
psycopg[binary]>=3.1  # PostgreSQL 存储
```

## 6. 实施计划

### Phase 1: 基础集成 (1-2天)

1. 创建 `graph_rag` 模块目录结构
2. 实现 `core.py` 核心封装类
3. 实现 `config.py` 配置模型
4. 添加依赖到 requirements.txt

### Phase 2: API 和工具 (1天)

1. 实现 `api.py` REST API 端点
2. 实现 `skill.py` Agent 工具封装
3. 注册工具到 ToolRegistry

### Phase 3: 模块集成 (2天)

1. 集成到 `knowledge_hub` 处理器
2. 实现用户画像管理器
3. 实现会话知识图谱

### Phase 4: 前端支持 (1天)

1. 添加 GraphRAG 配置页面
2. 添加知识图谱可视化组件
3. 集成到知识检索界面

### Phase 5: 测试和优化 (1天)

1. 编写单元测试
2. 性能测试和优化
3. 文档完善

## 7. 使用示例

### 7.1 基础使用

```python
from backend.modules.graph_rag import GraphRAGClient

# 创建客户端
client = GraphRAGClient(namespace="company_docs")

# 初始化
await client.initialize()

# 索引文档
await client.insert("""
AIE 是一个企业级 AI 办公助手项目。
主要功能包括智能对话、记忆系统、定时任务等。
技术栈使用 Python FastAPI 后端和 Vue3 前端。
""")

# 查询
result = await client.query("AIE 项目的主要功能是什么？")
print(result["content"])
```

### 7.2 作为 Agent 工具

```python
# 在 Agent 配置中启用工具
tools = [
    "graph_rag_index",
    "graph_rag_query",
]

# Agent 自动调用
# 用户: "请帮我索引这份文档到知识库"
# Agent: [调用 graph_rag_index 工具]

# 用户: "根据知识库，AIE 项目的架构是什么？"
# Agent: [调用 graph_rag_query 工具]
```

### 7.3 用户画像

```python
from backend.modules.graph_rag.integrations import UserProfileManager

profile = UserProfileManager(user_id="user_123")

# 从对话中抽取信息
await profile.extract_and_store("""
用户：我喜欢用 Python 写代码，偏好简洁的代码风格。
我每天早上 7 点起床，晚上 11 点睡觉。
我的工作主要是后端开发，对 AI 技术很感兴趣。
""")

# 查询用户画像
interests = await profile.get_user_interests()
# 返回: ["Python编程", "AI技术", "后端开发"]
```

## 8. 注意事项

### 8.1 LLM 模型要求

- 实体抽取建议使用 32B+ 参数的模型
- 查询阶段可以使用较小的模型
- 推荐模型：GPT-4o-mini, Claude 3.5 Sonnet, Qwen-Plus

### 8.2 嵌入模型要求

- 必须保持一致性（索引和查询使用相同模型）
- 推荐：text-embedding-3-small, BAAI/bge-m3
- 更换嵌入模型需要重建索引

### 8.3 资源消耗

- 内存：每个命名空间约 100MB-1GB（取决于文档量）
- 磁盘：文档量的 2-3 倍
- CPU：索引时较高，查询时较低

## 9. 总结

LightRAG 的集成将显著提升 AIE 的知识处理能力：

1. **知识检索增强**：从简单的向量匹配升级为知识图谱推理
2. **用户画像**：自动从对话中构建和维护用户画像
3. **Agent 能力**：提供标准化的知识管理工具
4. **会话记忆**：结构化的会话知识存储和检索

该模块设计为独立、可插拔的组件，不影响现有功能，可根据需要启用或禁用。
