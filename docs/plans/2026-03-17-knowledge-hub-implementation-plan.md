# KnowledgeHub 模块实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** 创建企业知识中枢(KnowledgeHub)可插拔独立模块，支持多种知识接入、智能处理模式、LLM加工增强功能

**Architecture:** 采用分层架构(5层)，模块独立化设计，支持直接检索/LLM加工/混合三种处理模式

**Tech Stack:** Python 3.11+, FastAPI, SQLite向量存储, Pydantic

---

## 阶段一：模块骨架与配置模型

### Task 1: 创建模块目录结构

**Files:**
- Create: `backend/modules/knowledge_hub/__init__.py`
- Create: `backend/modules/knowledge_hub/config.py`
- Create: `backend/modules/knowledge_hub/hub.py`

**Step 1: 创建目录结构**

```bash
mkdir -p backend/modules/knowledge_hub/processors
mkdir -p backend/modules/knowledge_hub/connectors
mkdir -p backend/modules/knowledge_hub/storage
mkdir -p backend/modules/knowledge_hub/skills
```

**Step 2: 创建 config.py**

```python
"""KnowledgeHub 配置模型"""

from typing import Optional, Literal
from pydantic import BaseModel
from pathlib import Path


class LLMConfig(BaseModel):
    """LLM处理配置"""
    enabled: bool = False
    model: str = "gpt-3.5-turbo"
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.7
    max_tokens: int = 2000
    prompt_style: str = "compress"
    custom_prompts: dict = {}

    PROMPT_STYLES = {
        "compress": {
            "name": "信息压缩",
            "description": "极致压缩，只提取关键重点",
            "template": "请从以下知识中提取最核心的关键信息..."
        },
        "restate": {
            "name": "关键复述",
            "description": "关键语义原文复述",
            "template": "请根据以下知识回答用户问题，尽量保持原文语义..."
        },
        "rework": {
            "name": "加工改写",
            "description": "知识加工增加模型自我理解",
            "template": "请根据以下知识回答用户问题，在理解知识的基础上进行加工整合..."
        }
    }


class CacheConfig(BaseModel):
    """缓存配置"""
    enabled: bool = True
    ttl: int = 3600
    max_memory_items: int = 100


class SourceConfig(BaseModel):
    """知识源配置"""
    id: str
    name: str
    source_type: Literal["local", "database", "web", "feishu", "wecom"]
    enabled: bool = True
    priority: int = 5
    config: dict = {}


class KnowledgeHubConfig(BaseModel):
    """模块配置"""
    enabled: bool = True
    default_mode: Literal["direct", "llm", "hybrid"] = "direct"
    llm: LLMConfig = LLMConfig()
    cache: CacheConfig = CacheConfig()
    sources: list[SourceConfig] = []

    storage_dir: str = "memory/knowledge_hub"

    @classmethod
    def load(cls, path: str) -> "KnowledgeHubConfig":
        """从文件加载配置"""
        p = Path(path)
        if p.exists():
            import json
            return cls(**json.loads(p.read_text()))
        return cls()

    def save(self, path: str):
        """保存配置到文件"""
        import json
        Path(path).write_text(json.dumps(self.model_dump(), ensure_ascii=False, indent=2))
```

**Step 3: 创建 hub.py 主类框架**

```python
"""KnowledgeHub 核心类"""

from typing import Optional, Any
from loguru import logger

from .config import KnowledgeHubConfig, LLMConfig, CacheConfig, SourceConfig


class KnowledgeHub:
    """企业知识中枢 - 可插拔独立模块"""

    def __init__(self, config: KnowledgeHubConfig = None):
        self.config = config or KnowledgeHubConfig()
        self._initialized = False

    async def initialize(self):
        """初始化模块"""
        if self._initialized:
            return
        logger.info("Initializing KnowledgeHub...")
        self._initialized = True

    async def retrieve(self, query: str, **options) -> dict:
        """检索知识"""
        raise NotImplementedError

    async def query_database(self, question: str) -> dict:
        """智能数据库查询"""
        raise NotImplementedError
```

**Step 4: 创建 __init__.py**

```python
"""KnowledgeHub - 企业知识中枢模块"""

from .hub import KnowledgeHub
from .config import KnowledgeHubConfig, LLMConfig, CacheConfig, SourceConfig

__all__ = ["KnowledgeHub", "KnowledgeHubConfig", "LLMConfig", "CacheConfig", "SourceConfig"]
```

---

### Task 2: 创建处理器基类

**Files:**
- Create: `backend/modules/knowledge_hub/processors/__init__.py`
- Create: `backend/modules/knowledge_hub/processors/base.py`

**Step 1: 创建 processors/__init__.py**

```python
"""处理器模块"""

from .base import BaseProcessor
from .direct import DirectProcessor
from .llm import LLMProcessor
from .hybrid import HybridProcessor

__all__ = ["BaseProcessor", "DirectProcessor", "LLMProcessor", "HybridProcessor"]
```

**Step 2: 创建 base.py**

```python
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
```

---

### Task 3: 创建存储层（简单缓存）

**Files:**
- Create: `backend/modules/knowledge_hub/storage/__init__.py`
- Create: `backend/modules/knowledge_hub/storage/cache.py`

**Step 1: 创建 storage/__init__.py**

```python
"""存储层"""

from .cache import SimpleCache

__all__ = ["SimpleCache"]
```

**Step 2: 创建 cache.py**

```python
"""简单缓存 - 内存+本地文件"""

import json
import time
from typing import Optional
from pathlib import Path
from loguru import logger


class SimpleCache:
    """简单缓存实现"""

    def __init__(self, cache_dir: str = None, config = None):
        self.cache_dir = Path(cache_dir) if cache_dir else Path("memory/knowledge_hub/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.config = config
        self.ttl = config.ttl if config else 3600
        self.max_items = config.max_memory_items if config else 100

        self._memory = {}
        self._access_time = {}

    def get(self, key: str) -> Optional[str]:
        """获取缓存"""
        # 1. 先查内存
        if key in self._memory:
            if time.time() - self._access_time[key] < self.ttl:
                return self._memory[key]
            else:
                del self._memory[key]
                del self._access_time[key]

        # 2. 再查文件
        cache_file = self.cache_dir / f"{hash(key)}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                if time.time() - data.get("timestamp", 0) < self.ttl:
                    self._memory[key] = data["content"]
                    self._access_time[key] = data["timestamp"]
                    return data["content"]
            except Exception:
                pass

        return None

    def set(self, key: str, value: str, ttl: int = None):
        """设置缓存"""
        self._memory[key] = value
        self._access_time[key] = time.time()

        # 简单内存淘汰
        if len(self._memory) > self.max_items:
            oldest_key = min(self._access_time, key=self._access_time.get)
            del self._memory[oldest_key]
            del self._access_time[oldest_key]

    def clear(self, pattern: str = None):
        """清空缓存"""
        self._memory.clear()
        self._access_time.clear()
        if pattern:
            for f in self.cache_dir.glob(f"{pattern}*.json"):
                f.unlink()
        else:
            for f in self.cache_dir.glob("*.json"):
                f.unlink()

    def invalidate(self, key: str):
        """失效指定缓存"""
        if key in self._memory:
            del self._memory[key]
            del self._access_time[key]
```

---

## 阶段二：直接检索模式

### Task 4: 实现直接检索处理器

**Files:**
- Create: `backend/modules/knowledge_hub/processors/direct.py`
- Modify: `backend/modules/knowledge_hub/hub.py`

**Step 1: 创建 direct.py**

```python
"""直接检索处理器"""

import time
from typing import Optional
from loguru import logger

from .base import BaseProcessor, KnowledgeResult


class DirectProcessor(BaseProcessor):
    """直接检索模式 - 快速返回原始结果"""

    def __init__(self, config, retrievers=None):
        super().__init__(config)
        self.retrievers = retrievers or {}

    async def process(self, query: str, chunks: list = None) -> KnowledgeResult:
        """直接检索处理"""
        start_time = time.time()

        # 如果没有传入chunks，需要从检索器获取
        if chunks is None:
            chunks = await self._retrieve_chunks(query)

        # 格式化输出
        content = self._format_chunks(chunks)

        processing_time = time.time() - start_time

        return KnowledgeResult(
            content=content,
            sources=[{"content": c.get("content", ""), "source": c.get("source", "")} for c in chunks],
            mode="direct",
            processing_time=processing_time,
            llm_used=False
        )

    async def _retrieve_chunks(self, query: str) -> list:
        """检索知识块"""
        results = []
        for name, retriever in self.retrievers.items():
            try:
                if hasattr(retriever, 'retrieve'):
                    chunks = await retriever.retrieve(query)
                    results.extend(chunks)
            except Exception as e:
                logger.warning(f"Retriever {name} failed: {e}")
        return results[:self.config.get("top_k", 10)]

    def _format_chunks(self, chunks: list) -> str:
        """格式化知识块"""
        if not chunks:
            return ""

        formatted = []
        for i, chunk in enumerate(chunks, 1):
            content = chunk.get("content", "")
            source = chunk.get("source", "unknown")
            formatted.append(f"【知识 {i} 来源: {source}】\n{content}")

        return "\n\n".join(formatted)
```

**Step 2: 更新 hub.py 添加直接检索**

```python
# 在 hub.py 中添加
from .processors import DirectProcessor

class KnowledgeHub:
    # ... existing code ...

    def _init_processors(self):
        """初始化处理器"""
        self.processors = {
            "direct": DirectProcessor({"top_k": 10}),
            # "llm": LLMProcessor(self.config.llm),
            # "hybrid": HybridProcessor(self.config),
        }

    async def retrieve(self, query: str, mode: str = None, **options) -> KnowledgeResult:
        """检索知识"""
        await self.initialize()

        mode = mode or self.config.default_mode
        processor = self.processors.get(mode) or self.processors["direct"]

        return await processor.process(query, **options)
```

---

### Task 5: 创建知识接入器基类和本地文件接入

**Files:**
- Create: `backend/modules/knowledge_hub/connectors/__init__.py`
- Create: `backend/modules/knowledge_hub/connectors/base.py`
- Create: `backend/modules/knowledge_hub/connectors/local.py`

**Step 1: 创建 connectors/__init__.py**

```python
"""知识接入器"""

from .base import BaseConnector
from .local import LocalConnector

__all__ = ["BaseConnector", "LocalConnector"]
```

**Step 2: 创建 base.py**

```python
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
```

**Step 3: 创建 local.py**

```python
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
```

---

### Task 6: 集成现有KnowledgeRAG能力

**Files:**
- Modify: `backend/modules/knowledge_hub/hub.py`
- Create: `backend/modules/knowledge_hub/storage/vector.py`

**Step 1: 创建 vector.py (封装现有向量存储)**

```python
"""向量存储封装"""

from typing import Optional, Literal
from loguru import logger

from backend.modules.agent.vector_store import get_vector_store, VectorStore


class VectorStoreWrapper:
    """向量存储封装"""

    def __init__(self, storage_dir: str = None):
        self.storage_dir = storage_dir or "memory/knowledge_hub/vectors"
        self._store: Optional[VectorStore] = None

    def get_store(self) -> VectorStore:
        """获取向量存储实例"""
        if self._store is None:
            # 使用已有的向量存储
            self._store = get_vector_store()
        return self._store

    async def add_documents(self, documents: list[dict], source_type: str = "knowledge"):
        """添加文档到向量库"""
        store = self.get_store()

        for doc in documents:
            chunks = doc.get("content", [])
            if isinstance(chunks, list):
                entries = [{"content": c, "metadata": doc} for c in chunks]
            else:
                entries = [{"content": chunks, "metadata": doc}]

            try:
                store.add_batch(entries=entries, source_type=source_type, source_id=doc.get("id"))
            except Exception as e:
                logger.warning(f"Failed to add to vector store: {e}")

    async def search(self, query: str, top_k: int = 5, source_type: str = "knowledge") -> list[dict]:
        """检索"""
        store = self.get_store()

        results = store.search_hybrid(
            query=query,
            top_k=top_k,
            source_type=source_type
        )

        return results

    async def count(self, source_type: str = "knowledge") -> int:
        """统计数量"""
        store = self.get_store()
        return store.count(source_type=source_type)
```

**Step 2: 更新 hub.py 集成现有能力**

```python
# 在 hub.py 中添加
from .connectors import LocalConnector
from .storage.cache import SimpleCache
from .storage.vector import VectorStoreWrapper


class KnowledgeHub:
    def __init__(self, config: KnowledgeHubConfig = None):
        self.config = config or KnowledgeHubConfig()
        self._initialized = False

        # 存储层
        self.cache = SimpleCache(config=self.config.cache)
        self.vector_store = VectorStoreWrapper(self.config.storage_dir)

        # 接入器
        self.connectors = {}

        # 处理器
        self.processors = {}

    async def initialize(self):
        """初始化模块"""
        if self._initialized:
            return

        logger.info("Initializing KnowledgeHub...")

        # 初始化接入器
        for source in self.config.sources:
            if source.enabled and source.source_type == "local":
                self.connectors[source.id] = LocalConnector(source.config)

        # 初始化处理器
        from .processors import DirectProcessor
        self.processors["direct"] = DirectProcessor({"top_k": 10})

        self._initialized = True
```

---

## 阶段三：LLM加工模式

### Task 7: 实现LLM加工处理器

**Files:**
- Create: `backend/modules/knowledge_hub/processors/llm.py`

**Step 1: 创建 llm.py**

```python
"""LLM加工处理器"""

import time
import json
from loguru import logger

from .base import BaseProcessor, KnowledgeResult


class LLMProcessor(BaseProcessor):
    """LLM加工模式 - 智能处理"""

    def __init__(self, config):
        super().__init__(config)
        self.config = config
        self.client = None

    async def process(self, query: str, chunks: list = None) -> KnowledgeResult:
        """LLM加工处理"""
        start_time = time.time()

        # 1. 检索原始知识
        if chunks is None:
            chunks = await self._retrieve_chunks(query)

        if not chunks:
            return KnowledgeResult(
                content="未找到相关知识",
                sources=[],
                mode="llm",
                processing_time=time.time() - start_time,
                llm_used=False
            )

        # 2. 调用LLM处理
        context = self._format_context(chunks)
        prompt = self._build_prompt(query, context)

        try:
            result = await self._call_llm(prompt)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            # 降级到直接返回
            result = context

        processing_time = time.time() - start_time

        return KnowledgeResult(
            content=result,
            sources=[{"content": c.get("content", ""), "source": c.get("source", "")} for c in chunks],
            mode="llm",
            processing_time=processing_time,
            llm_used=True
        )

    async def _retrieve_chunks(self, query: str) -> list:
        """检索知识"""
        # TODO: 集成向量检索
        return []

    def _format_context(self, chunks: list) -> str:
        """格式化上下文"""
        formatted = []
        for i, chunk in enumerate(chunks, 1):
            content = chunk.get("content", "")
            formatted.append(f"【知识 {i}】\n{content}")
        return "\n\n".join(formatted)

    def _build_prompt(self, query: str, context: str) -> str:
        """构建提示词"""
        style = self.config.prompt_style
        template = self.config.PROMPT_STYLES.get(style, self.config.PROMPT_STYLES["compress"])

        prompt = template["template"].format(query=query, context=context)
        return prompt

    async def _call_llm(self, prompt: str) -> str:
        """调用LLM"""
        # TODO: 集成LiteLLM
        # 临时实现：简单返回
        try:
            from litellm import acompletion
            response = await acompletion(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            return response.choices[0].message.content
        except ImportError:
            return "LLM未配置，请先配置API Key"
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            raise
```

---

## 阶段四：API路由与集成

### Task 8: 创建API路由

**Files:**
- Create: `backend/modules/knowledge_hub/api.py`

**Step 1: 创建 api.py**

```python
"""KnowledgeHub API路由"""

from typing import Optional, Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger


router = APIRouter(prefix="/api/knowledge_hub", tags=["knowledge_hub"])


class RetrieveRequest(BaseModel):
    """检索请求"""
    query: str
    mode: Literal["direct", "llm", "hybrid"] = "direct"
    top_k: int = 5
    source_ids: list[str] = []


class QueryDBRequest(BaseModel):
    """数据库查询请求"""
    question: str


class ConfigUpdateRequest(BaseModel):
    """配置更新请求"""
    enabled: Optional[bool] = None
    default_mode: Optional[str] = None
    llm: Optional[dict] = None
    cache: Optional[dict] = None


# 全局实例
_hub = None


def get_hub():
    """获取Hub实例"""
    global _hub
    if _hub is None:
        from . import KnowledgeHub, KnowledgeHubConfig
        _hub = KnowledgeHub()
    return _hub


@router.post("/retrieve")
async def retrieve(request: RetrieveRequest):
    """知识检索"""
    hub = get_hub()

    try:
        result = await hub.retrieve(
            query=request.query,
            mode=request.mode,
            top_k=request.top_k,
            source_ids=request.source_ids
        )

        return {
            "code": 0,
            "data": {
                "content": result.content,
                "sources": result.sources,
                "mode": result.mode,
                "processing_time": result.processing_time,
                "llm_used": result.llm_used
            }
        }
    except Exception as e:
        logger.error(f"Retrieve failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query-db")
async def query_db(request: QueryDBRequest):
    """智能数据库查询"""
    hub = get_hub()

    try:
        result = await hub.query_database(request.question)
        return {"code": 0, "data": result}
    except Exception as e:
        logger.error(f"Query DB failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_config():
    """获取配置"""
    hub = get_hub()
    return {
        "code": 0,
        "data": hub.config.model_dump()
    }


@router.put("/config")
async def update_config(request: ConfigUpdateRequest):
    """更新配置"""
    hub = get_hub()

    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(hub.config, key):
            setattr(hub.config, key, value)

    return {"code": 0, "message": "Config updated"}


@router.post("/cache/refresh")
async def refresh_cache(cache_type: str = None):
    """刷新缓存"""
    hub = get_hub()

    if hasattr(hub, 'cache') and hub.cache:
        hub.cache.clear(cache_type)

    return {"code": 0, "message": "Cache cleared"}
```

---

### Task 9: 注册API路由到主应用

**Files:**
- Modify: `backend/app.py`

**Step 1: 添加路由注册**

```python
# 在 backend/app.py 中添加
from backend.modules.knowledge_hub.api import router as knowledge_hub_router

# 注册路由
app.include_router(knowledge_hub_router)
```

---

## 阶段五：前端配置界面

### Task 10: 创建前端API客户端

**Files:**
- Create: `frontend/src/api/knowledgeHub.ts`

**Step 1: 创建 knowledgeHub.ts**

```typescript
/* eslint-disable */
/* KnowledgeHub API Client */

import apiClient from './client'

export interface LLMConfig {
  enabled: boolean
  model: string
  api_key: string
  base_url: string
  temperature: number
  max_tokens: number
  prompt_style: string
}

export interface CacheConfig {
  enabled: boolean
  ttl: number
  max_memory_items: number
}

export interface KnowledgeHubConfig {
  enabled: boolean
  default_mode: 'direct' | 'llm' | 'hybrid'
  llm: LLMConfig
  cache: CacheConfig
  sources: any[]
}

export interface RetrieveRequest {
  query: string
  mode?: 'direct' | 'llm' | 'hybrid'
  top_k?: number
  source_ids?: string[]
}

export interface RetrieveResult {
  content: string
  sources: any[]
  mode: string
  processing_time: number
  llm_used: boolean
}

export const knowledgeHubApi = {
  // 知识检索
  retrieve: async (request: RetrieveRequest): Promise<RetrieveResult> => {
    const response = await apiClient.post('/api/knowledge_hub/retrieve', request)
    return response.data
  },

  // 智能数据库查询
  queryDb: async (question: string): Promise<any> => {
    const response = await apiClient.post('/api/knowledge_hub/query-db', { question })
    return response.data
  },

  // 获取配置
  getConfig: async (): Promise<KnowledgeHubConfig> => {
    const response = await apiClient.get('/api/knowledge_hub/config')
    return response.data
  },

  // 更新配置
  updateConfig: async (config: Partial<KnowledgeHubConfig>): Promise<void> => {
    await apiClient.put('/api/knowledge_hub/config', config)
  },

  // 刷新缓存
  refreshCache: async (cacheType?: string): Promise<void> => {
    await apiClient.post('/api/knowledge_hub/cache/refresh', null, { params: { cache_type: cacheType } })
  },
}

export default knowledgeHubApi
```

---

### Task 11: 创建配置界面组件

**Files:**
- Create: `frontend/src/modules/knowledge/KnowledgeHubConfig.vue`

**Step 1: 创建 KnowledgeHubConfig.vue**

```vue
<template>
  <div class="knowledge-hub-config">
    <div class="section-header">
      <h3>{{ $t('knowledgeHub.title') }}</h3>
      <p>{{ $t('knowledgeHub.description') }}</p>
    </div>

    <!-- 处理模式 -->
    <div class="config-section">
      <h4>{{ $t('knowledgeHub.processingMode') }}</h4>
      <div class="mode-selector">
        <label v-for="mode in modes" :key="mode.value" class="mode-option">
          <input
            type="radio"
            v-model="config.default_mode"
            :value="mode.value"
            @change="updateConfig"
          />
          <span class="mode-label">{{ mode.label }}</span>
        </label>
      </div>
    </div>

    <!-- LLM配置 -->
    <div class="config-section" v-if="config.default_mode !== 'direct'">
      <h4>{{ $t('knowledgeHub.llmConfig') }}</h4>

      <div class="form-group">
        <label class="toggle-label">
          <span>{{ $t('knowledgeHub.enableLLM') }}</span>
          <label class="toggle-switch">
            <input type="checkbox" v-model="config.llm.enabled" @change="updateConfig" />
            <span class="toggle-slider"></span>
          </label>
        </label>
      </div>

      <div v-if="config.llm.enabled" class="llm-options">
        <div class="form-group">
          <label>{{ $t('knowledgeHub.promptStyle') }}</label>
          <select v-model="config.llm.prompt_style" @change="updateConfig">
            <option value="compress">{{ $t('knowledgeHub.styleCompress') }}</option>
            <option value="restate">{{ $t('knowledgeHub.styleRestate') }}</option>
            <option value="rework">{{ $t('knowledgeHub.styleRework') }}</option>
          </select>
        </div>

        <div class="form-group">
          <label>{{ $t('knowledgeHub.model') }}</label>
          <input v-model="config.llm.model" type="text" @change="updateConfig" />
        </div>

        <div class="form-group">
          <label>{{ $t('knowledgeHub.temperature') }}: {{ config.llm.temperature }}</label>
          <input
            type="range"
            v-model.number="config.llm.temperature"
            min="0"
            max="1"
            step="0.1"
            @change="updateConfig"
          />
        </div>

        <div class="form-group">
          <label>{{ $t('knowledgeHub.maxTokens') }}</label>
          <input v-model.number="config.llm.max_tokens" type="number" @change="updateConfig" />
        </div>
      </div>
    </div>

    <!-- 缓存配置 -->
    <div class="config-section">
      <h4>{{ $t('knowledgeHub.cache') }}</h4>
      <div class="form-group">
        <label class="toggle-label">
          <span>{{ $t('knowledgeHub.enableCache') }}</span>
          <label class="toggle-switch">
            <input type="checkbox" v-model="config.cache.enabled" @change="updateConfig" />
            <span class="toggle-slider"></span>
          </label>
        </label>
      </div>
      <div class="form-group">
        <label>{{ $t('knowledgeHub.cacheTTL') }} (秒)</label>
        <input v-model.number="config.cache.ttl" type="number" @change="updateConfig" />
      </div>
      <button class="btn secondary" @click="refreshCache">
        {{ $t('knowledgeHub.refreshCache') }}
      </button>
    </div>

    <!-- 测试检索 -->
    <div class="config-section">
      <h4>{{ $t('knowledgeHub.testRetrieve') }}</h4>
      <div class="test-form">
        <input v-model="testQuery" type="text" :placeholder="$t('knowledgeHub.queryPlaceholder')" />
        <button class="btn primary" @click="testRetrieve" :disabled="testing">
          {{ testing ? $t('knowledgeHub.searching') : $t('knowledgeHub.search') }}
        </button>
      </div>
      <div v-if="testResult" class="test-result">
        <pre>{{ testResult }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import knowledgeHubApi, { type KnowledgeHubConfig } from '@/api/knowledgeHub'

const { t } = useI18n()

const config = ref<KnowledgeHubConfig>({
  enabled: true,
  default_mode: 'direct',
  llm: {
    enabled: false,
    model: 'gpt-3.5-turbo',
    api_key: '',
    base_url: '',
    temperature: 0.7,
    max_tokens: 2000,
    prompt_style: 'compress'
  },
  cache: {
    enabled: true,
    ttl: 3600,
    max_memory_items: 100
  },
  sources: []
})

const modes = [
  { value: 'direct', label: '直接检索' },
  { value: 'llm', label: 'LLM加工' },
  { value: 'hybrid', label: '混合模式' }
]

const testQuery = ref('')
const testing = ref(false)
const testResult = ref('')

const loadConfig = async () => {
  try {
    config.value = await knowledgeHubApi.getConfig()
  } catch (error) {
    console.error('Failed to load config:', error)
  }
}

const updateConfig = async () => {
  try {
    await knowledgeHubApi.updateConfig(config.value)
  } catch (error) {
    console.error('Failed to update config:', error)
  }
}

const refreshCache = async () => {
  try {
    await knowledgeHubApi.refreshCache()
    alert(t('knowledgeHub.cacheRefreshed'))
  } catch (error) {
    console.error('Failed to refresh cache:', error)
  }
}

const testRetrieve = async () => {
  if (!testQuery.value.trim()) return

  testing.value = true
  testResult.value = ''

  try {
    const result = await knowledgeHubApi.retrieve({
      query: testQuery.value,
      mode: config.value.default_mode,
      top_k: 5
    })
    testResult.value = JSON.stringify(result, null, 2)
  } catch (error) {
    console.error('Failed to retrieve:', error)
    testResult.value = 'Error: ' + error
  } finally {
    testing.value = false
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.knowledge-hub-config {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 16px;
}

.config-section {
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border-primary);
  border-radius: 8px;
  padding: 16px;
}

.config-section h4 {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 600;
}

.mode-selector {
  display: flex;
  gap: 16px;
}

.mode-option {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-size: 14px;
}

.form-group input[type="text"],
.form-group input[type="number"],
.form-group select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--color-border-primary);
  border-radius: 6px;
}

.toggle-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.toggle-switch {
  position: relative;
  width: 44px;
  height: 24px;
}

.toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-slider {
  position: absolute;
  cursor: pointer;
  inset: 0;
  background-color: var(--color-border-secondary);
  border-radius: 24px;
  transition: 0.3s;
}

.toggle-slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  border-radius: 50%;
  transition: 0.3s;
}

.toggle-switch input:checked + .toggle-slider {
  background-color: var(--color-success);
}

.toggle-switch input:checked + .toggle-slider:before {
  transform: translateX(20px);
}

.btn {
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.btn.primary {
  background: var(--color-primary);
  color: white;
  border: none;
}

.btn.secondary {
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border-primary);
}

.test-result {
  margin-top: 16px;
  padding: 12px;
  background: var(--color-bg-secondary);
  border-radius: 6px;
  max-height: 300px;
  overflow: auto;
}

.test-result pre {
  margin: 0;
  font-size: 12px;
  white-space: pre-wrap;
}
</style>
```

---

## 阶段六：数据库自动SQL（可选P1）

### Task 12: 实现数据库自动SQL接入器

**Files:**
- Create: `backend/modules/knowledge_hub/connectors/database.py`

**Step 1: 创建 database.py**

```python
"""数据库接入器 - 自动SQL生成"""

import re
from typing import Optional
from loguru import logger

from .base import BaseConnector


class DatabaseConnector(BaseConnector):
    """数据库自动SQL接入器"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.connection_string = config.get("connection_string", "")
        self.tables = config.get("tables", [])
        self.llm_config = config.get("llm", {})

    async def connect(self) -> bool:
        """连接数据库"""
        # TODO: 实现数据库连接
        return bool(self.connection_string)

    async def fetch(self, query: str = None) -> list[dict]:
        """获取数据（需要通过LLM生成SQL）"""
        return []

    async def sync(self) -> int:
        """同步表结构"""
        return len(self.tables)

    async def execute_query(self, question: str) -> dict:
        """智能执行查询"""

        # 1. 获取表结构
        schema = await self.get_schema()

        # 2. LLM生成SQL
        sql = await self.generate_sql(question, schema)

        # 3. 验证SQL
        if not self.validate_sql(sql):
            return {"error": "SQL验证失败", "sql": sql}

        # 4. 执行SQL
        result = await self.run_sql(sql)

        return {
            "sql": sql,
            "result": result,
            "schema": schema
        }

    async def get_schema(self) -> dict:
        """获取数据库表结构"""
        # TODO: 实现表结构获取
        return {"tables": self.tables}

    async def generate_sql(self, question: str, schema: dict) -> str:
        """LLM生成SQL"""
        # TODO: 集成LLM生成SQL
        return "SELECT * FROM table LIMIT 10"

    def validate_sql(self, sql: str) -> bool:
        """验证SQL安全性"""
        dangerous = ["DROP", "DELETE", "TRUNCATE", "ALTER", "INSERT", "UPDATE"]
        upper_sql = sql.upper()
        return not any(d in upper_sql for d in dangerous)

    async def run_sql(self, sql: str) -> list:
        """执行SQL"""
        # TODO: 实现SQL执行
        return []
```

---

## 总结

本计划包含以下主要任务：

| 阶段 | 任务数 | 说明 |
|------|--------|------|
| 1 | 3 | 模块骨架、配置模型、处理器基类、缓存 |
| 2 | 3 | 直接检索、本地文件接入、向量存储集成 |
| 3 | 1 | LLM加工处理器 |
| 4 | 2 | API路由、注册到主应用 |
| 5 | 2 | 前端API、配置界面 |
| 6 | 1 | 数据库自动SQL (P1) |

**Plan complete and saved to `docs/plans/2026-03-17-knowledge-hub-design.md`**.

---

## 执行选择

**Two execution options:**

1. **Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

2. **Parallel Session (separate)** - Open new session with executing_plans, batch execution with checkpoints

Which approach?
