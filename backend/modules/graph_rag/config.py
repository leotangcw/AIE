"""GraphRAG 配置模型

基于 LightRAG 的知识图谱检索配置。
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field
from pathlib import Path

from backend.utils.paths import MEMORY_DIR


# 默认值
DEFAULT_WORKING_DIR = str(MEMORY_DIR / "graph_rag")
DEFAULT_KV_STORAGE = "JsonKVStorage"
DEFAULT_VECTOR_STORAGE = "NanoVectorDBStorage"
DEFAULT_GRAPH_STORAGE = "NetworkXStorage"
DEFAULT_MODE = "hybrid"
DEFAULT_TOP_K = 10
DEFAULT_CHUNK_TOP_K = 5
DEFAULT_ENTITY_TYPES = ["人物", "组织", "地点", "事件", "概念", "产品", "时间"]

# 别名（保持兼容性）
CHUNK_TOP_K = DEFAULT_CHUNK_TOP_K


class GraphRAGSettings(BaseModel):
    """GraphRAG 模块配置"""

    enabled: bool = Field(default=True, description="是否启用 GraphRAG")

    # 存储配置
    storage_type: Literal["file", "postgres", "neo4j"] = Field(
        default="file",
        description="存储类型"
    )
    working_dir: str = Field(
        default=DEFAULT_WORKING_DIR,
        description="工作目录（文件存储模式）"
    )

    # 存储后端选择
    kv_storage: str = Field(
        default=DEFAULT_KV_STORAGE,
        description="KV 存储后端"
    )
    vector_storage: str = Field(
        default=DEFAULT_VECTOR_STORAGE,
        description="向量存储后端"
    )
    graph_storage: str = Field(
        default=DEFAULT_GRAPH_STORAGE,
        description="图存储后端"
    )

    # 查询配置
    default_mode: Literal["local", "global", "hybrid", "naive", "mix"] = Field(
        default=DEFAULT_MODE,
        description="默认查询模式"
    )
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=100, description="默认返回结果数")
    chunk_top_k: int = Field(default=DEFAULT_CHUNK_TOP_K, ge=1, le=50, description="文档块返回数")

    # Token 限制
    max_entity_tokens: int = Field(default=6000, description="实体上下文最大 Token")
    max_relation_tokens: int = Field(default=8000, description="关系上下文最大 Token")
    max_total_tokens: int = Field(default=30000, description="总上下文最大 Token")

    # 文本分块配置
    chunk_token_size: int = Field(default=1200, description="分块 Token 大小")
    chunk_overlap_token_size: int = Field(default=100, description="分块重叠 Token 大小")

    # 实体抽取配置
    entity_types: list[str] = Field(
        default_factory=lambda: DEFAULT_ENTITY_TYPES.copy(),
        description="实体类型列表"
    )
    max_gleaning: int = Field(default=1, description="最大抽取轮数")

    # LLM 配置
    llm_model: str = Field(default="gpt-4o-mini", description="LLM 模型名称")
    embedding_model: str = Field(default="text-embedding-3-small", description="嵌入模型名称")
    embedding_dim: int = Field(default=1536, description="嵌入向量维度")

    # 超时配置
    llm_timeout: int = Field(default=300, description="LLM 超时时间（秒）")
    embedding_timeout: int = Field(default=180, description="嵌入超时时间（秒）")

    # 并发配置
    max_async: int = Field(default=16, description="最大并发数")
    max_parallel_insert: int = Field(default=2, description="最大并行插入数")


class NamespaceConfig(BaseModel):
    """命名空间配置"""

    namespace: str = Field(description="命名空间名称")
    workspace: str = Field(default="default", description="工作空间")
    description: str = Field(default="", description="描述")
    entity_types: Optional[list[str]] = Field(default=None, description="自定义实体类型")
    enabled: bool = Field(default=True, description="是否启用")

    # 继承的全局配置覆盖
    default_mode: Optional[Literal["local", "global", "hybrid", "naive", "mix"]] = None
    top_k: Optional[int] = None


class GraphRAGStats(BaseModel):
    """GraphRAG 统计信息"""

    available: bool = Field(default=False, description="是否可用")
    namespace: str = Field(default="", description="命名空间")
    workspace: str = Field(default="", description="工作空间")

    # 图谱统计
    node_count: int = Field(default=0, description="节点数量")
    edge_count: int = Field(default=0, description="边数量")

    # 文档统计
    document_count: int = Field(default=0, description="文档数量")
    chunk_count: int = Field(default=0, description="分块数量")

    # 存储统计
    vector_count: int = Field(default=0, description="向量数量")

    # 错误信息
    error: Optional[str] = None

    class Config:
        from_attributes = True


class QueryResult(BaseModel):
    """查询结果"""

    content: str = Field(default="", description="回答内容")
    mode: str = Field(default="", description="查询模式")
    context: Optional[str] = Field(default=None, description="检索上下文")

    # 相关实体和关系
    entities: list[dict] = Field(default_factory=list, description="相关实体")
    relations: list[dict] = Field(default_factory=list, description="相关关系")
    chunks: list[dict] = Field(default_factory=list, description="相关文档块")

    # 元数据
    processing_time: float = Field(default=0.0, description="处理时间（秒）")
    total_tokens: int = Field(default=0, description="总 Token 数")

    # 错误
    error: Optional[str] = None

    class Config:
        from_attributes = True


class InsertResult(BaseModel):
    """插入结果"""

    success: bool = Field(default=False, description="是否成功")
    namespace: str = Field(default="", description="命名空间")
    document_count: int = Field(default=0, description="文档数量")
    chunk_count: int = Field(default=0, description="生成的分块数量")
    entity_count: int = Field(default=0, description="抽取的实体数量")
    relation_count: int = Field(default=0, description="抽取的关系数量")
    processing_time: float = Field(default=0.0, description="处理时间（秒）")
    error: Optional[str] = None
