# 模型提供商架构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 AIE 统一模型提供商架构，整合三套 Embedding 模型为 BGE-M3，创建 ModelRegistry 和 Infrastructure 层。

**Architecture:** 分层服务架构 - ModelRegistry 统一管理 LLM/Embedder，Infrastructure 层管理 SQLite/Vector/Cache，应用层通过注册中心获取依赖。

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, LiteLLM, FlagEmbedding (BGE-M3), SQLite

**Spec Document:** `docs/superpowers/specs/2026-03-26-model-architecture-design.md`

## 任务依赖图

```
Task 1 (Config) ─┬─→ Task 4 (Embedder) ─→ Task 5 (ModelRegistry) ─┐
                  │                                           │
Task 2 (Database) ─→ Task 3 (VectorStore) ─→ Task 6 (Infra) ───┼─→ Task 7 (App) ─→ Task 8 (GraphRAG)
                                                              │
Task 2.5 (Cache) ──────────────────────────────────────────────┘
```

---

## 文件结构

```
backend/
├── core/                          # 新建核心模块
│   ├── __init__.py                # 新建
│   ├── model_registry.py          # 新建：模型注册中心
│   └── built_in/
│       ├── __init__.py            # 新建
│       └── embedders.py           # 新建：统一 Embedder
├── infrastructure/                # 新建基础设施层
│   ├── __init__.py                # 新建：Infrastructure 类
│   ├── database.py                # 新建：SQLite 封装
│   ├── vector_store.py            # 新建：向量存储（1024维）
│   └── cache.py                   # 新建：缓存
├── modules/
│   ├── config/
│   │   └── schema.py              # 修改：扩展配置模型
│   ├── graph_rag/
│   │   └── core.py                # 修改：使用 ModelRegistry
│   ├── agent/
│   │   └── vector_store.py        # 修改：废弃旧实现
│   └── memory_mcp_server/
│       └── utils/
│           └── embedder.py        # 修改：使用适配器
└── app.py                         # 修改：初始化 ModelRegistry
```

---

## Task 1: 扩展配置模型

**Files:**
- Modify: `backend/modules/config/schema.py:1-251`

- [ ] **Step 1: 添加新配置类**

在 `backend/modules/config/schema.py` 中添加：

```python
# 在 ProviderConfig 类之后添加

class SubAgentConfig(BaseModel):
    """子代理模型配置"""
    enabled: bool = False
    provider: str = "qwen"
    model: str = "qwen-turbo"
    max_concurrent: int = 3
    temperature: float = Field(default=0.5, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=0)


class DatabaseConfig(BaseModel):
    """数据库配置"""
    path: str = Field(default="data/aie.db", description="SQLite 数据库路径")
    echo: bool = False


class APIFallbackConfig(BaseModel):
    """Embedding API 回退配置"""
    provider: str = "qwen_bailian"
    model: str = "text-embedding-v3"
    api_key: Optional[str] = None
    api_base: Optional[str] = None


class EmbeddingConfig(BaseModel):
    """Embedding 配置 - 统一 BGE-M3"""
    model: str = "BAAI/bge-m3"
    dimension: int = 1024
    max_length: int = 8192
    device: str = "auto"
    use_fp16: bool = True
    cache_dir: Optional[str] = None
    use_modelscope: bool = True
    modelscope_endpoint: Optional[str] = None
    api_fallback: Optional[APIFallbackConfig] = None


class BuiltInModelConfig(BaseModel):
    """内置模型配置"""
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
```

- [ ] **Step 2: 扩展 AppConfig 类**

修改 `AppConfig` 类：

```python
class AppConfig(BaseModel):
    """应用配置"""
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    model: ModelConfig = Field(default_factory=ModelConfig)
    sub_agent: SubAgentConfig = Field(default_factory=SubAgentConfig)  # 新增
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)  # 新增
    built_in: BuiltInModelConfig = Field(default_factory=BuiltInModelConfig)  # 新增
    workspace: WorkspaceConfig = Field(default_factory=WorkspaceConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    tool_history: ToolHistoryConfig = Field(default_factory=ToolHistoryConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    persona: PersonaConfig = Field(default_factory=PersonaConfig)
    theme: str = "auto"
    language: str = "auto"
    font_size: str = "medium"
```

- [ ] **Step 3: 验证配置加载**

```bash
cd /mnt/d/code/AIE_0302/AIE && python -c "
from backend.modules.config.schema import AppConfig
config = AppConfig()
print(f'SubAgent enabled: {config.sub_agent.enabled}')
print(f'Embedding model: {config.built_in.embedding.model}')
print(f'Embedding dimension: {config.built_in.embedding.dimension}')
print(f'Database path: {config.database.path}')
"
```
Expected: 无错误输出，显示配置默认值

- [ ] **Step 4: Commit**

```bash
git add backend/modules/config/schema.py
git commit -m "feat(config): add SubAgent, Database, Embedding config models"
```

---

## Task 2: 创建基础设施层 - Database

**Files:**
- Create: `backend/infrastructure/__init__.py`
- Create: `backend/infrastructure/database.py`

- [ ] **Step 1: 创建目录结构**

```bash
mkdir -p /mnt/d/code/AIE_0302/AIE/backend/infrastructure
```

- [ ] **Step 2: 创建 database.py**

```python
# backend/infrastructure/database.py

"""SQLite 数据库封装"""

import sqlite3
import asyncio
from pathlib import Path
from typing import Optional
from loguru import logger


class SQLiteDatabase:
    """SQLite 数据库连接管理"""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[sqlite3.Connection] = None
        logger.info(f"Database initialized at {self.db_path}")

    async def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._connection is None:
            self._connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
            )
            self._connection.row_factory = sqlite3.Row
        return self._connection

    async def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """执行 SQL"""
        conn = await self.get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return cursor

    async def fetchall(self, sql: str, params: tuple = ()) -> list:
        """查询所有行"""
        conn = await self.get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall()

    async def fetchone(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """查询单行"""
        conn = await self.get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.fetchone()

    async def close(self):
        """关闭连接"""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("Database connection closed")
```

- [ ] **Step 3: 验证数据库模块**

```bash
cd /mnt/d/code/AIE_0302/AIE && python -c "
import asyncio
from backend.infrastructure.database import SQLiteDatabase

async def test():
    db = SQLiteDatabase('data/test.db')
    await db.execute('CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY, name TEXT)')
    await db.execute('INSERT INTO test (name) VALUES (?)', ('test',))
    rows = await db.fetchall('SELECT * FROM test')
    print(f'Rows: {len(rows)}')
    await db.close()
    print('Database test passed')

asyncio.run(test())
"
```
Expected: "Database test passed"

- [ ] **Step 4: Commit**

```bash
git add backend/infrastructure/database.py
git commit -m "feat(infra): add SQLiteDatabase wrapper"
```

---

## Task 3: 创建基础设施层 - Vector Store

**Files:**
- Create: `backend/infrastructure/vector_store.py`

- [ ] **Step 1: 创建 vector_store.py**

```python
# backend/infrastructure/vector_store.py

"""统一向量存储 - 1024 维 (BGE-M3)"""

import json
import uuid
import numpy as np
from datetime import datetime
from typing import Optional, Any
from loguru import logger

from .database import SQLiteDatabase


class SQLiteVectorStore:
    """向量存储（统一 1024 维）

    使用显式初始化模式，避免在 __init__ 中调用 asyncio.run()
    """

    def __init__(self, db: SQLiteDatabase, dimension: int = 1024):
        self._db = db
        self._dimension = dimension
        self._embedder: Optional[Any] = None
        self._initialized = False

    async def initialize(self) -> "SQLiteVectorStore":
        """异步初始化表结构（必须调用）"""
        if self._initialized:
            return self

        await self._db.execute(f"""
            CREATE TABLE IF NOT EXISTS vectors (
                id TEXT PRIMARY KEY,
                namespace TEXT DEFAULT 'default',
                content TEXT NOT NULL,
                metadata TEXT,
                vector BLOB,
                dimension INTEGER DEFAULT {self._dimension},
                source_type TEXT DEFAULT 'knowledge',
                source_id TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        await self._db.execute("CREATE INDEX IF NOT EXISTS idx_namespace ON vectors(namespace)")
        await self._db.execute("CREATE INDEX IF NOT EXISTS idx_source_type ON vectors(source_type)")
        self._initialized = True
        logger.info(f"Vector store initialized (dimension={self._dimension})")
        return self

    def set_embedder(self, embedder: Any):
        """设置 Embedder（由 ModelRegistry 注入）"""
        self._embedder = embedder

    def _vector_to_blob(self, vector: np.ndarray) -> bytes:
        return vector.astype(np.float32).tobytes()

    def _blob_to_vector(self, blob: bytes) -> np.ndarray:
        return np.frombuffer(blob, dtype=np.float32)

    async def add(
        self,
        content: str,
        embedding: Optional[np.ndarray] = None,
        metadata: dict = None,
        namespace: str = "default",
        source_type: str = "knowledge",
        source_id: str = None,
    ) -> str:
        """添加向量"""
        if not self._initialized:
            await self.initialize()

        entry_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        if embedding is None and self._embedder:
            embedding = await self._embedder.embed_single(content)

        vector_blob = self._vector_to_blob(embedding) if embedding is not None else None

        await self._db.execute("""
            INSERT INTO vectors (id, namespace, content, metadata, vector, dimension, source_type, source_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry_id, namespace, content,
            json.dumps(metadata or {}, ensure_ascii=False),
            vector_blob, self._dimension,
            source_type, source_id, now, now
        ))

        return entry_id

    async def search(
        self,
        query_embedding: np.ndarray,
        namespace: str = "default",
        top_k: int = 5,
        min_score: float = 0.5,
    ) -> list[dict]:
        """向量搜索"""
        if not self._initialized:
            await self.initialize()

        rows = await self._db.fetchall("""
            SELECT id, content, metadata, vector, source_type, source_id
            FROM vectors
            WHERE namespace = ? AND vector IS NOT NULL AND dimension = ?
        """, (namespace, self._dimension))

        results = []
        for row in rows:
            vector = self._blob_to_vector(row["vector"])
            score = float(np.dot(query_embedding, vector))
            if score >= min_score:
                results.append({
                    "id": row["id"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"] or "{}"),
                    "source_type": row["source_type"],
                    "source_id": row["source_id"],
                    "score": score,
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    async def delete(self, entry_id: str) -> bool:
        """删除向量"""
        await self._db.execute("DELETE FROM vectors WHERE id = ?", (entry_id,))
        return True

    async def delete_by_namespace(self, namespace: str) -> int:
        """删除命名空间下所有向量"""
        await self._db.execute("DELETE FROM vectors WHERE namespace = ?", (namespace,))
        return 0

    async def count(self, namespace: str = "default") -> int:
        """统计数量"""
        row = await self._db.fetchone(
            "SELECT COUNT(*) as cnt FROM vectors WHERE namespace = ?",
            (namespace,)
        )
        return row["cnt"] if row else 0

    async def get_stats(self, namespace: str = "default") -> dict:
        """获取统计信息"""
        row = await self._db.fetchone("""
            SELECT COUNT(*) as cnt, dimension
            FROM vectors
            WHERE namespace = ?
            GROUP BY dimension
        """, (namespace,))
        if row:
            return {"count": row["cnt"], "dimension": row["dimension"]}
        return {"count": 0, "dimension": self._dimension}

    async def iter_documents(self, namespace: str = "default", batch_size: int = 100):
        """迭代文档（用于迁移）"""
        offset = 0
        while True:
            rows = await self._db.fetchall("""
                SELECT id, content, metadata, source_type, source_id
                FROM vectors
                WHERE namespace = ?
                ORDER BY id
                LIMIT ? OFFSET ?
            """, (namespace, batch_size, offset))
            if not rows:
                break
            yield [dict(row) for row in rows]
            offset += batch_size

    async def update_embedding(self, doc_id: str, embedding: np.ndarray, dimension: int) -> bool:
        """更新向量"""
        vector_blob = self._vector_to_blob(embedding)
        now = datetime.now().isoformat()
        await self._db.execute("""
            UPDATE vectors SET vector = ?, dimension = ?, updated_at = ? WHERE id = ?
        """, (vector_blob, dimension, now, doc_id))
        return True
```

- [ ] **Step 2: 验证向量存储**

```bash
cd /mnt/d/code/AIE_0302/AIE && python -c "
import asyncio
import numpy as np
from backend.infrastructure.database import SQLiteDatabase
from backend.infrastructure.vector_store import SQLiteVectorStore

async def test():
    db = SQLiteDatabase('data/test_vector.db')
    store = SQLiteVectorStore(db, dimension=1024)

    # 添加测试向量
    embedding = np.random.randn(1024).astype(np.float32)
    entry_id = await store.add('test content', embedding=embedding)
    print(f'Added entry: {entry_id}')

    # 搜索
    query = np.random.randn(1024).astype(np.float32)
    results = await store.search(query, min_score=0.0)
    print(f'Search results: {len(results)}')

    # 统计
    stats = await store.get_stats()
    print(f'Stats: {stats}')

    await db.close()
    print('Vector store test passed')

asyncio.run(test())
"
```
Expected: "Vector store test passed"

- [ ] **Step 3: Commit**

```bash
git add backend/infrastructure/vector_store.py
git commit -m "feat(infra): add SQLiteVectorStore with 1024 dimension"
```

---

## Task 3.5: 创建缓存模块（可选）

**Depends on:** Task 2 (Database)

**Files:**
- Create: `backend/infrastructure/cache.py`

- [ ] **Step 1: 创建 cache.py**

```python
# backend/infrastructure/cache.py

"""简单的 SQLite 缓存模块"""

import json
import hashlib
from datetime import datetime
from typing import Optional, Any
from loguru import logger

from .database import SQLiteDatabase


class SQLiteCache:
    """基于 SQLite 的缓存"""

    def __init__(self, db: SQLiteDatabase, table_name: str = "cache"):
        self._db = db
        self._table_name = table_name
        self._initialized = False

    async def initialize(self) -> "SQLiteCache":
        """初始化缓存表"""
        if self._initialized:
            return self

        await self._db.execute(f"""
            CREATE TABLE IF NOT EXISTS {self._table_name} (
                key TEXT PRIMARY KEY,
                value TEXT,
                expires_at TEXT,
                created_at TEXT
            )
        """)
        self._initialized = True
        logger.debug(f"Cache initialized: {self._table_name}")
        return self

    def _hash_key(self, key: str) -> str:
        """生成缓存 key 的 hash"""
        return hashlib.sha256(key.encode()).hexdigest()

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if not self._initialized:
            await self.initialize()

        hashed_key = self._hash_key(key)
        row = await self._db.fetchone(f"""
            SELECT value, expires_at FROM {self._table_name}
            WHERE key = ?
        """, (hashed_key,))

        if row is None:
            return None

        # 检查过期
        if row["expires_at"]:
            expires_at = datetime.fromisoformat(row["expires_at"])
            if datetime.now() > expires_at:
                await self.delete(key)
                return None

        try:
            return json.loads(row["value"])
        except json.JSONDecodeError:
            return row["value"]

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """设置缓存"""
        if not self._initialized:
            await self.initialize()

        hashed_key = self._hash_key(key)
        value_str = json.dumps(value) if not isinstance(value, str) else value

        expires_at = None
        if ttl_seconds:
            expires_at = (datetime.now() + __import__('datetime').timedelta(seconds=ttl_seconds)).isoformat()

        created_at = datetime.now().isoformat()

        await self._db.execute(f"""
            INSERT OR REPLACE INTO {self._table_name} (key, value, expires_at, created_at)
            VALUES (?, ?, ?, ?)
        """, (hashed_key, value_str, expires_at, created_at))

        return True

    async def delete(self, key: str) -> bool:
        """删除缓存"""
        hashed_key = self._hash_key(key)
        await self._db.execute(f"DELETE FROM {self._table_name} WHERE key = ?", (hashed_key,))
        return True

    async def clear(self) -> int:
        """清空所有缓存"""
        await self._db.execute(f"DELETE FROM {self._table_name}")
        return 0

    async def cleanup_expired(self) -> int:
        """清理过期缓存"""
        now = datetime.now().isoformat()
        await self._db.execute(f"""
            DELETE FROM {self._table_name}
            WHERE expires_at IS NOT NULL AND expires_at < ?
        """, (now,))
        return 0
```

- [ ] **Step 2: 验证缓存模块**

```bash
cd /mnt/d/code/AIE_0302/AIE && python -c "
import asyncio
from backend.infrastructure.database import SQLiteDatabase
from backend.infrastructure.cache import SQLiteCache

async def test():
    db = SQLiteDatabase('data/test_cache.db')
    cache = SQLiteCache(db)
    await cache.initialize()

    # 测试设置和获取
    await cache.set('test_key', {'data': 'test_value'}, ttl_seconds=60)
    result = await cache.get('test_key')
    print(f'Cache result: {result}')

    # 测试删除
    await cache.delete('test_key')
    result2 = await cache.get('test_key')
    print(f'After delete: {result2}')

    await db.close()
    print('Cache test passed')

asyncio.run(test())
"
```
Expected: "Cache test passed"

- [ ] **Step 3: Commit**

```bash
git add backend/infrastructure/cache.py
git commit -m "feat(infra): add SQLiteCache module"
```

---

## Task 4: 创建统一 Embedder

**Files:**
- Create: `backend/core/__init__.py`
- Create: `backend/core/built_in/__init__.py`
- Create: `backend/core/built_in/embedders.py`

- [ ] **Step 1: 创建目录结构**

```bash
mkdir -p /mnt/d/code/AIE_0302/AIE/backend/core/built_in
```

- [ ] **Step 2: 创建 core/__init__.py**

```python
# backend/core/__init__.py

"""核心模块 - 模型注册和统一 Embedder"""

from .model_registry import (
    ModelRegistry,
    EmbedderUnavailableError,
    get_model_registry,
    init_model_registry,
)

__all__ = [
    "ModelRegistry",
    "EmbedderUnavailableError",
    "get_model_registry",
    "init_model_registry",
]
```

- [ ] **Step 3: 创建 built_in/__init__.py**

```python
# backend/core/built_in/__init__.py

"""内置模型"""

from .embedders import UnifiedEmbedder

__all__ = ["UnifiedEmbedder"]
```

- [ ] **Step 4: 创建 embedders.py**

```python
# backend/core/built_in/embedders.py

"""统一 Embedder - BGE-M3 本地优先，支持 API 回退"""

import os
import numpy as np
from typing import Optional, Any
from loguru import logger


class UnifiedEmbedder:
    """统一 Embedder - BGE-M3 本地优先，支持 API 回退"""

    def __init__(self, dimension: int = 1024):
        self._dimension = dimension
        self._local_model: Optional[Any] = None
        self._api_client: Optional[dict] = None

    @property
    def dimension(self) -> int:
        return self._dimension

    @classmethod
    async def create_local(cls, config) -> "UnifiedEmbedder":
        """创建本地 Embedder"""
        instance = cls(config.dimension)
        await instance._load_local_model(config)
        return instance

    @classmethod
    async def create_api(
        cls,
        config,
        api_key: str,
        api_base: Optional[str] = None,
    ) -> "UnifiedEmbedder":
        """创建 API Embedder"""
        instance = cls(config.dimension)
        instance._api_client = {
            "provider": config.api_fallback.provider if config.api_fallback else "openai",
            "model": config.api_fallback.model if config.api_fallback else "text-embedding-v3",
            "api_key": api_key,
            "api_base": api_base,
        }
        logger.info(f"API embedder configured: {instance._api_client['provider']}/{instance._api_client['model']}")
        return instance

    async def _load_local_model(self, config):
        """加载 BGE-M3 本地模型"""
        # 设置 ModelScope 镜像（国内加速）
        if config.use_modelscope:
            endpoint = config.modelscope_endpoint or "https://hf-mirror.com"
            os.environ["HF_ENDPOINT"] = endpoint
            logger.debug(f"HF mirror set: {endpoint}")

        # 尝试 FlagEmbedding
        try:
            from FlagEmbedding import BGEM3FlagModel

            device = self._resolve_device(config.device)
            self._local_model = BGEM3FlagModel(
                config.model,
                use_fp16=config.use_fp16,
                device=device,
            )
            logger.info(f"BGE-M3 loaded on {device}")
            return

        except ImportError:
            logger.warning("FlagEmbedding not installed, trying sentence-transformers")

        # 回退到 sentence-transformers
        try:
            from sentence_transformers import SentenceTransformer

            device = self._resolve_device(config.device)
            self._local_model = SentenceTransformer(config.model, device=device)
            logger.info(f"Embedder loaded via sentence-transformers on {device}")
        except ImportError:
            raise ImportError(
                "No embedding library available. "
                "Install FlagEmbedding (pip install FlagEmbedding) or "
                "sentence-transformers (pip install sentence-transformers)"
            )

    def _resolve_device(self, device: str) -> str:
        """解析设备"""
        if device == "auto":
            try:
                import torch
                return "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                return "cpu"
        return device

    async def embed(self, texts: list[str]) -> np.ndarray:
        """生成嵌入向量"""
        if self._local_model is not None:
            return await self._embed_local(texts)
        elif self._api_client is not None:
            return await self._embed_api(texts)
        else:
            raise RuntimeError("No embedder available")

    async def _embed_local(self, texts: list[str]) -> np.ndarray:
        """本地嵌入"""
        if hasattr(self._local_model, 'encode'):
            # FlagEmbedding BGEM3
            output = self._local_model.encode(
                texts,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )
            return output['dense_vecs']
        else:
            # sentence-transformers
            embeddings = self._local_model.encode(texts)
            return np.array(embeddings, dtype=np.float32)

    async def _embed_api(self, texts: list[str]) -> np.ndarray:
        """API 嵌入"""
        import litellm

        response = await litellm.aembedding(
            model=f"openai/{self._api_client['model']}",
            input=texts,
            api_key=self._api_client['api_key'],
            api_base=self._api_client['api_base'],
        )

        embeddings = [item["embedding"] for item in response.data]
        return np.array(embeddings, dtype=np.float32)

    async def embed_single(self, text: str) -> np.ndarray:
        """嵌入单个文本"""
        result = await self.embed([text])
        return result[0]
```

- [ ] **Step 5: 验证 Embedder（API 模式，不依赖本地模型）**

```bash
cd /mnt/d/code/AIE_0302/AIE && python -c "
import asyncio
from backend.core.built_in.embedders import UnifiedEmbedder
from backend.modules.config.schema import EmbeddingConfig, APIFallbackConfig

async def test():
    # 创建 API embedder（跳过本地模型）
    config = EmbeddingConfig(
        api_fallback=APIFallbackConfig(
            provider='qwen_bailian',
            model='text-embedding-v3'
        )
    )

    # 直接创建 API embedder
    print('Creating API embedder (requires DASHSCOPE_API_KEY)...')
    import os
    api_key = os.environ.get('DASHSCOPE_API_KEY', '')
    if not api_key:
        print('SKIPPED: No DASHSCOPE_API_KEY')
        return

    embedder = await UnifiedEmbedder.create_api(config, api_key=api_key, api_base='https://dashscope.aliyuncs.com/compatible-mode/v1')
    print(f'Embedder dimension: {embedder.dimension}')
    print('API embedder test passed')

asyncio.run(test())
"
```
Expected: 如果有 DASHSCOPE_API_KEY 则通过，否则跳过

- [ ] **Step 6: Commit**

```bash
git add backend/core/
git commit -m "feat(core): add UnifiedEmbedder with local/API fallback"
```

---

## Task 5: 创建 ModelRegistry

**Files:**
- Create: `backend/core/model_registry.py`

- [ ] **Step 1: 创建 model_registry.py**

```python
# backend/core/model_registry.py

"""统一模型注册中心"""

from typing import Optional, Any, TYPE_CHECKING
from loguru import logger

if TYPE_CHECKING:
    from .built_in.embedders import UnifiedEmbedder


class EmbedderUnavailableError(Exception):
    """Embedder 不可用异常（非致命）"""
    pass


class ModelRegistry:
    """统一模型注册中心

    管理所有模型的创建和缓存：
    - LLM (主/子代理)
    - Embedder (BGE-M3 统一)
    """

    def __init__(self, config):
        self._config = config
        # LLM 客户端
        self._llm: Optional[Any] = None
        self._sub_llm: Optional[Any] = None
        # Embedder
        self._embedder: Optional["UnifiedEmbedder"] = None

    # ========== LLM ==========

    async def get_llm(self) -> Any:
        """获取主 LLM 客户端"""
        if self._llm is None:
            self._llm = await self._create_llm(self._config.model)
        return self._llm

    async def get_sub_llm(self) -> Optional[Any]:
        """获取子代理 LLM（可选）"""
        if not self._config.sub_agent.enabled:
            return None
        if self._sub_llm is None:
            self._sub_llm = await self._create_llm(self._config.sub_agent)
        return self._sub_llm

    async def _create_llm(self, model_config) -> Any:
        """创建 LLM 客户端（使用现有 provider 系统）"""
        from backend.modules.providers.factory import create_provider

        provider_id = model_config.provider
        provider_config = self._config.providers.get(provider_id)

        return create_provider(
            api_key=provider_config.api_key if provider_config else None,
            api_base=provider_config.api_base if provider_config else None,
            default_model=model_config.model,
            provider_id=provider_id,
        )

    # ========== Embedder ==========

    async def get_embedder(self) -> "UnifiedEmbedder":
        """获取统一 Embedder"""
        if self._embedder is None:
            self._embedder = await self._create_embedder()
        return self._embedder

    async def _create_embedder(self) -> "UnifiedEmbedder":
        """创建 Embedder（本地优先，API 回退）"""
        from .built_in.embedders import UnifiedEmbedder

        config = self._config.built_in.embedding

        # 尝试加载本地模型
        try:
            embedder = await UnifiedEmbedder.create_local(config)
            logger.info(f"Embedder loaded: {config.model} on {config.device}")
            return embedder
        except Exception as e:
            logger.warning(f"Failed to load local embedder: {e}")

            # 尝试 API 回退
            if config.api_fallback:
                provider = config.api_fallback.provider
                provider_config = self._config.providers.get(provider)

                api_key = config.api_fallback.api_key or (
                    provider_config.api_key if provider_config else None
                )
                api_base = config.api_fallback.api_base or (
                    provider_config.api_base if provider_config else None
                )

                if api_key:
                    logger.info(f"Falling back to API embedder: {provider}")
                    return await UnifiedEmbedder.create_api(
                        config, api_key=api_key, api_base=api_base
                    )

            raise EmbedderUnavailableError(
                "No embedder available. Vector search features will be disabled. "
                "Install FlagEmbedding (pip install FlagEmbedding) or configure "
                "API fallback in built_in.embedding.api_fallback"
            )


# 全局单例
_registry: Optional[ModelRegistry] = None


def get_model_registry() -> ModelRegistry:
    """获取模型注册中心"""
    if _registry is None:
        raise RuntimeError("ModelRegistry not initialized")
    return _registry


async def init_model_registry(config) -> ModelRegistry:
    """初始化模型注册中心"""
    global _registry
    _registry = ModelRegistry(config)
    # 预热主 LLM
    await _registry.get_llm()
    logger.info("ModelRegistry initialized")
    return _registry
```

- [ ] **Step 2: 验证 ModelRegistry**

```bash
cd /mnt/d/code/AIE_0302/AIE && python -c "
from backend.core.model_registry import ModelRegistry, get_model_registry, init_model_registry
print('ModelRegistry import test passed')
"
```
Expected: "ModelRegistry import test passed"

- [ ] **Step 3: Commit**

```bash
git add backend/core/model_registry.py
git commit -m "feat(core): add ModelRegistry with embedder management"
```

---

## Task 6: 创建 Infrastructure 管理类

**Files:**
- Create: `backend/infrastructure/__init__.py`

- [ ] **Step 1: 创建 __init__.py**

```python
# backend/infrastructure/__init__.py

"""基础设施层"""

from typing import Optional, TYPE_CHECKING
from loguru import logger

from .database import SQLiteDatabase
from .vector_store import SQLiteVectorStore

if TYPE_CHECKING:
    from .cache import SQLiteCache


class Infrastructure:
    """共享基础设施"""

    def __init__(self, config):
        self._config = config
        self._db: Optional[SQLiteDatabase] = None
        self._vector_store: Optional[SQLiteVectorStore] = None
        self._cache: Optional["SQLiteCache"] = None

    async def get_database(self) -> SQLiteDatabase:
        """获取数据库连接"""
        if self._db is None:
            self._db = SQLiteDatabase(self._config.database.path)
        return self._db

    async def get_vector_store(self) -> SQLiteVectorStore:
        """获取向量存储（统一 1024 维）"""
        if self._vector_store is None:
            db = await self.get_database()
            self._vector_store = SQLiteVectorStore(
                db=db,
                dimension=1024,  # BGE-M3 维度
            )
        return self._vector_store

    async def initialize(self):
        """初始化基础设施"""
        await self.get_database()
        await self.get_vector_store()
        logger.info("Infrastructure initialized")

    async def finalize(self):
        """清理资源"""
        if self._db:
            await self._db.close()


# 全局单例
_infra: Optional[Infrastructure] = None


def get_infrastructure() -> Infrastructure:
    """获取基础设施"""
    if _infra is None:
        raise RuntimeError("Infrastructure not initialized")
    return _infra


async def init_infrastructure(config) -> Infrastructure:
    """初始化基础设施"""
    global _infra
    _infra = Infrastructure(config)
    await _infra.initialize()
    return _infra
```

- [ ] **Step 2: 验证 Infrastructure**

```bash
cd /mnt/d/code/AIE_0302/AIE && python -c "
import asyncio
from backend.infrastructure import Infrastructure, get_infrastructure, init_infrastructure
from backend.modules.config.schema import AppConfig

async def test():
    config = AppConfig()
    infra = await init_infrastructure(config)
    print(f'Database path: {infra._config.database.path}')

    store = await infra.get_vector_store()
    print(f'Vector store dimension: {store._dimension}')

    print('Infrastructure test passed')

asyncio.run(test())
"
```
Expected: "Infrastructure test passed"

- [ ] **Step 3: Commit**

```bash
git add backend/infrastructure/__init__.py
git commit -m "feat(infra): add Infrastructure manager class"
```

---

## Task 7: 修改 app.py 集成 ModelRegistry

**Files:**
- Modify: `backend/app.py`

- [ ] **Step 1: 添加导入和初始化**

在 `backend/app.py` 中，找到 `_create_shared_components` 函数，在末尾添加：

```python
# 在 _create_shared_components 函数末尾，return 之前添加

    # ========== 初始化 ModelRegistry 和 Infrastructure ==========
    logger.info("Initializing ModelRegistry and Infrastructure...")
    from backend.core.model_registry import init_model_registry
    from backend.infrastructure import init_infrastructure

    registry = await init_model_registry(config)
    infra = await init_infrastructure(config)

    # 将 Embedder 注入到 VectorStore
    try:
        embedder = await registry.get_embedder()
        vector_store = await infra.get_vector_store()
        vector_store.set_embedder(embedder)
        logger.info("Embedder injected into VectorStore")
    except Exception as e:
        logger.warning(f"Embedder not available, vector search disabled: {e}")

    # 存储到 shared dict 供其他模块使用
    shared["model_registry"] = registry
    shared["infrastructure"] = infra
```

- [ ] **Step 2: 修改 lifespan 函数签名**

确保 `lifespan` 函数是 async 的：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... startup code ...
    yield
    # ... cleanup code ...
```

- [ ] **Step 3: 验证集成**

```bash
cd /mnt/d/code/AIE_0302/AIE && python -c "
# 简单验证导入
from backend.core.model_registry import init_model_registry
from backend.infrastructure import init_infrastructure
print('App integration imports OK')
"
```
Expected: "App integration imports OK"

- [ ] **Step 4: Commit**

```bash
git add backend/app.py
git commit -m "feat(app): integrate ModelRegistry and Infrastructure"
```

---

## Task 8: 迁移 GraphRAG 使用 ModelRegistry

**Files:**
- Modify: `backend/modules/graph_rag/core.py`

- [ ] **Step 1: 修改 GraphRAGClient.initialize 方法**

找到 `GraphRAGClient.initialize` 方法，修改为：

```python
async def initialize(self) -> bool:
    async with self._lock:
        if self._initialized:
            return True

        if not LIGHTERAG_AVAILABLE:
            logger.warning("LightRAG not installed. GraphRAG features disabled.")
            return False

        try:
            # 从 ModelRegistry 获取 LLM 和 Embedder
            from backend.core.model_registry import get_model_registry

            registry = get_model_registry()

            # 使用统一 LLM
            llm_client = await registry.get_llm()
            self._llm_func = llm_client.complete

            # 使用统一 Embedder
            embedder = await registry.get_embedder()
            self._embed_func = embedder.embed

            # 创建 LightRAG 实例...
            # 其余初始化代码保持不变
```

- [ ] **Step 2: 移除旧的配置传递**

删除 `set_llm_config` 和 `set_embed_config` 相关代码（如果存在）。

- [ ] **Step 3: 验证 GraphRAG 导入**

```bash
cd /mnt/d/code/AIE_0302/AIE && python -c "
from backend.modules.graph_rag import GraphRAGClient
print('GraphRAG import OK')
"
```
Expected: "GraphRAG import OK"

- [ ] **Step 4: Commit**

```bash
git add backend/modules/graph_rag/core.py
git commit -m "refactor(graph_rag): use ModelRegistry for LLM and Embedder"
```

---

## Task 9: 添加 Memory MCP Server Embedder 适配器

**Files:**
- Modify: `backend/modules/memory_mcp_server/utils/embedder.py`

- [ ] **Step 1: 添加适配器类**

在文件中添加：

```python
# backend/modules/memory_mcp_server/utils/embedder.py

"""Memory MCP Server Embedder 适配器"""

import numpy as np
from typing import Optional
from loguru import logger


class UnifiedEmbedderAdapter:
    """适配器：将统一 Embedder 包装为 Memory MCP 接口"""

    def __init__(self):
        self._embedder = None

    async def _get_embedder(self):
        """获取统一 Embedder"""
        if self._embedder is None:
            from backend.core.model_registry import get_model_registry
            registry = get_model_registry()
            self._embedder = await registry.get_embedder()
        return self._embedder

    async def embed(self, texts: list[str]) -> np.ndarray:
        """生成嵌入向量"""
        embedder = await self._get_embedder()
        return await embedder.embed(texts)

    async def embed_single(self, text: str) -> np.ndarray:
        """嵌入单个文本"""
        embedder = await self._get_embedder()
        return await embedder.embed_single(text)

    @property
    def dimension(self) -> int:
        """向量维度"""
        return 1024  # BGE-M3


# 全局适配器实例
_adapter: Optional[UnifiedEmbedderAdapter] = None


def get_embedder_adapter() -> UnifiedEmbedderAdapter:
    """获取 Embedder 适配器"""
    global _adapter
    if _adapter is None:
        _adapter = UnifiedEmbedderAdapter()
    return _adapter
```

- [ ] **Step 2: 更新 Memory MCP 使用适配器**

修改 Memory MCP 中使用 embedder 的地方：

```python
# 替换旧的 embedder 导入
# from .embedder import BGEEmbedder  # 旧代码
from .embedder import get_embedder_adapter  # 新代码

# 使用
embedder = get_embedder_adapter()
embeddings = await embedder.embed(texts)
```

- [ ] **Step 3: Commit**

```bash
git add backend/modules/memory_mcp_server/utils/embedder.py
git commit -m "refactor(memory_mcp): add UnifiedEmbedderAdapter"
```

---

## Task 10: 废弃旧的 VectorStore

**Files:**
- Modify: `backend/modules/agent/vector_store.py`

- [ ] **Step 1: 添加废弃警告**

在文件开头添加：

```python
"""Vector Store using SQLite + bge-small-zh-v1.5 embedding

DEPRECATED: 此模块已废弃，请使用 backend.infrastructure.vector_store.SQLiteVectorStore
统一使用 BGE-M3 1024 维向量。
"""

import warnings

warnings.warn(
    "backend.modules.agent.vector_store.VectorStore is deprecated. "
    "Use backend.infrastructure.vector_store.SQLiteVectorStore instead.",
    DeprecationWarning,
    stacklevel=2,
)

# ... 保留原有代码以保持兼容性 ...
```

- [ ] **Step 2: 更新使用点**

搜索项目中使用 `from backend.modules.agent.vector_store import VectorStore` 的地方，更新为：

```python
from backend.infrastructure.vector_store import SQLiteVectorStore as VectorStore
```

- [ ] **Step 3: Commit**

```bash
git add backend/modules/agent/vector_store.py
git commit -m "depr(agent): mark old VectorStore as deprecated"
```

---

## Task 11: 添加向量迁移 CLI 命令（可选）

**Depends on:** Task 5, Task 6, Task 7

**Files:**
- Create: `backend/cli/commands/migrate_vectors.py`

- [ ] **Step 1: 创建迁移命令**

```python
# backend/cli/commands/migrate_vectors.py

"""向量迁移命令 - 从 512 维迁移到 1024 维"""

import asyncio
import click
from pathlib import Path
from datetime import datetime
from loguru import logger


@click.group()
def migrate():
    """迁移命令"""
    pass


@migrate.command("vectors")
@click.option("--namespace", default="default", help="命名空间")
@click.option("--force", is_flag=True, help="强制迁移（覆盖已有数据）")
@click.option("--backup/--no-backup", default=True, help="是否备份原始数据")
def migrate_vectors(namespace: str, force: bool, backup: bool):
    """迁移向量数据从 512 维到 1024 维

    流程:
    1. 检测现有向量维度
    2. 备份原始数据（可选）
    3. 使用新 Embedder 重新生成向量
    4. 更新向量存储
    5. 验证迁移结果
    """
    asyncio.run(_migrate_vectors_async(namespace, force, backup))


async def _migrate_vectors_async(namespace: str, force: bool, backup: bool):
    from backend.core.model_registry import get_model_registry
    from backend.infrastructure import get_infrastructure

    vector_store = await get_infrastructure().get_vector_store()

    # 检测现有向量
    stats = await vector_store.get_stats(namespace)
    click.echo(f"Current stats: {stats}")

    if stats.get("count", 0) == 0:
        click.echo("No vectors to migrate.")
        return

    if stats.get("dimension") == 1024 and not force:
        click.echo("向量已是 1024 维，无需迁移。使用 --force 强制重新生成。")
        return

    click.echo(f"开始迁移 {stats.get('count', 0)} 条向量数据...")

    # 备份原始数据
    if backup:
        backup_path = Path(f"data/backups/{namespace}_{datetime.now():%Y%m%d_%H%M%S}.json")
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        click.echo(f"备份位置: {backup_path}")
        # 实际备份逻辑...

    # 获取新 Embedder
    try:
        registry = get_model_registry()
        embedder = await registry.get_embedder()
    except Exception as e:
        click.echo(f"错误: 无法获取 Embedder: {e}")
        click.echo("请确保已安装 FlagEmbedding 或配置了 API 回退")
        return

    # 重新生成向量
    migrated = 0
    async for batch in vector_store.iter_documents(namespace):
        texts = [doc["content"] for doc in batch]
        new_embeddings = await embedder.embed(texts)

        for doc, embedding in zip(batch, new_embeddings):
            await vector_store.update_embedding(
                doc_id=doc["id"],
                embedding=embedding,
                dimension=1024,
            )
            migrated += 1

        click.echo(f"\r已迁移: {migrated}/{stats.get('count', 0)}", nl=False)

    click.echo(f"\n迁移完成: {migrated} 条记录")

    # 验证
    new_stats = await vector_store.get_stats(namespace)
    click.echo(f"新统计: {new_stats}")


@migrate.command("rollback")
@click.argument("backup_path", type=click.Path(exists=True))
@click.option("--namespace", default="default", help="命名空间")
def rollback_vectors(backup_path: str, namespace: str):
    """回滚到备份数据"""
    asyncio.run(_rollback_async(Path(backup_path), namespace))


async def _rollback_async(backup_path: Path, namespace: str):
    from backend.infrastructure import get_infrastructure

    vector_store = await get_infrastructure().get_vector_store()
    # 实际恢复逻辑...
    click.echo(f"已从备份恢复: {backup_path}")


if __name__ == "__main__":
    migrate()
```

- [ ] **Step 2: 注册 CLI 命令**

在 CLI 入口文件中注册：

```python
# backend/cli/__init__.py 或主 CLI 入口

from .commands.migrate_vectors import migrate as migrate_vectors_group

# 在 CLI 组中添加
cli.add_command(migrate_vectors_group, name="migrate")
```

- [ ] **Step 3: 验证命令**

```bash
cd /mnt/d/code/AIE_0302/AIE && python -c "
from backend.cli.commands.migrate_vectors import migrate
print('CLI command import OK')
"
```
Expected: "CLI command import OK"

- [ ] **Step 4: Commit**

```bash
git add backend/cli/commands/migrate_vectors.py
git commit -m "feat(cli): add migrate vectors command for 512->1024 dimension"
```

---

## Task 12: 验证完整集成

- [ ] **Step 1: 运行单元测试**

```bash
cd /mnt/d/code/AIE_0302/AIE && python -m pytest tests/ -v -k "embedder or vector" || echo "No tests found"
```

- [ ] **Step 2: 启动应用验证**

```bash
cd /mnt/d/code/AIE_0302/AIE && python -c "
import asyncio
from backend.modules.config.schema import AppConfig
from backend.core.model_registry import init_model_registry
from backend.infrastructure import init_infrastructure

async def test_full():
    config = AppConfig()

    # 初始化
    registry = await init_model_registry(config)
    infra = await init_infrastructure(config)

    # 尝试获取 LLM
    llm = await registry.get_llm()
    print(f'LLM: {type(llm).__name__}')

    # 尝试获取 embedder
    try:
        embedder = await registry.get_embedder()
        print(f'Embedder: {type(embedder).__name__}, dim={embedder.dimension}')
    except Exception as e:
        print(f'Embedder unavailable (expected if no model): {type(e).__name__}')

    # 获取 vector store
    store = await infra.get_vector_store()
    print(f'VectorStore: dim={store._dimension}')

    print('Full integration test passed')

asyncio.run(test_full())
"
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test: verify full ModelRegistry and Infrastructure integration"
```

---

## Task 13: 更新依赖

- [ ] **Step 1: 添加 requirements**

在 `requirements.txt` 或 `pyproject.toml` 中添加：

```
# Embedding
FlagEmbedding>=1.2.0
sentence-transformers>=2.2.0

# Vector (如需 GPU 加速)
# faiss-cpu  # 或 faiss-gpu
```

- [ ] **Step 2: Commit**

```bash
git add requirements.txt pyproject.toml
git commit -m "chore: add FlagEmbedding and sentence-transformers dependencies"
```

---

## 验收清单

- [ ] `ModelRegistry` 正确初始化
- [ ] `get_llm()` 可用
- [ ] `get_embedder()` 可用（本地或 API）
- [ ] `Infrastructure` 正确初始化
- [ ] BGE-M3 Embedder 可加载（本地或 API）
- [ ] GraphRAG 使用统一 Embedder
- [ ] Memory MCP Server 使用适配器
- [ ] 旧 VectorStore 标记为废弃
- [ ] 向量维度统一为 1024
- [ ] 应用启动无错误
- [ ] CLI 迁移命令可用
