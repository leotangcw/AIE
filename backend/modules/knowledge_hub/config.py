"""KnowledgeHub 配置模型

支持多种知识源类型和检索策略的配置。
"""

from typing import Optional, Literal, ClassVar, Any
from pydantic import BaseModel, Field
from pathlib import Path
from enum import Enum


# ==============================================================================
# 分段策略配置
# ==============================================================================

class ChunkStrategy(str, Enum):
    """分段策略类型"""
    FIXED = "fixed"               # 固定长度分段
    SEMANTIC = "semantic"          # 语义分段（按段落/标题）
    PARENT_CHILD = "parent_child"  # 父子分段（文档+段落两级）
    RECURSIVE = "recursive"        # 递归分段


class ChunkConfig(BaseModel):
    """分段配置"""
    strategy: ChunkStrategy = ChunkStrategy.FIXED
    chunk_size: int = 1000           # 分段大小（字符数）
    chunk_overlap: int = 100         # 分段重叠
    parent_chunk_size: int = 3000    # 父分段大小（父子分段模式）
    separators: list[str] = ["\n\n", "\n", "。", "！", "？", "；"]  # 分隔符


# ==============================================================================
# 检索策略配置
# ==============================================================================

class RetrievalMode(str, Enum):
    """检索模式"""
    DIRECT = "direct"       # 直接检索（关键词/BM25）
    VECTOR = "vector"       # 向量检索
    HYBRID = "hybrid"       # 混合检索（向量+关键词）
    LLM = "llm"             # LLM 处理后返回
    GRAPH = "graph"         # 知识图谱检索（GraphRAG）


class RerankConfig(BaseModel):
    """重排序配置"""
    enabled: bool = True
    # 各维度权重
    semantic_weight: float = 0.5    # 语义相似度权重
    recency_weight: float = 0.2     # 时间新近度权重
    hotness_weight: float = 0.2     # 热度权重
    source_weight: float = 0.1      # 来源权重


class RetrievalConfig(BaseModel):
    """检索配置"""
    mode: RetrievalMode = RetrievalMode.DIRECT
    top_k: int = 10                 # 返回结果数量
    min_score: float = 0.3          # 最小相关分数
    rerank: RerankConfig = RerankConfig()
    # 混合检索权重（仅 hybrid 模式）
    vector_weight: float = 0.7
    keyword_weight: float = 0.3


# ==============================================================================
# 知识源配置
# ==============================================================================

class LocalSourceConfig(BaseModel):
    """本地文件知识源配置"""
    path: str                       # 目录路径
    file_types: list[str] = [".md", ".txt", ".pdf", ".docx", ".xlsx"]
    recursive: bool = True          # 递归扫描子目录
    chunk: ChunkConfig = ChunkConfig()
    watch_changes: bool = False     # 监听文件变化


class DatabaseSourceConfig(BaseModel):
    """数据库知识源配置"""
    db_type: Literal["sqlite", "mysql", "postgresql", "mssql", "oracle"] = "sqlite"
    connection_string: str = ""     # 数据库连接字符串
    # 或使用分离参数
    host: str = ""
    port: int = 0
    database: str = ""
    username: str = ""
    password: str = ""
    # 查询配置
    tables: list[str] = []          # 要索引的表
    text_columns: list[str] = []    # 文本列
    id_column: str = "id"           # ID列
    # 安全配置
    read_only: bool = True          # 只读模式
    allowed_operations: list[str] = ["SELECT"]  # 允许的操作


class WebSearchSourceConfig(BaseModel):
    """网络搜索知识源配置"""
    provider: Literal["brave", "google", "bing", "custom"] = "brave"
    api_key: str = ""
    base_url: str = ""              # 自定义 API 地址
    max_results: int = 5            # 最大返回结果数
    timeout: int = 10               # 超时时间（秒）
    # 自定义请求配置
    custom_headers: dict = {}
    custom_params: dict = {}


class SourceConfig(BaseModel):
    """知识源配置"""
    id: str
    name: str
    source_type: Literal["local", "database", "web_search"]
    enabled: bool = True
    priority: int = 5               # 优先级（1-10，数字越大优先级越高）
    # 类型特定配置
    config: dict = {}               # 通用配置字典
    local: LocalSourceConfig | None = None
    database: DatabaseSourceConfig | None = None
    web_search: WebSearchSourceConfig | None = None
    # 检索配置
    retrieval: RetrievalConfig = RetrievalConfig()
    # 元数据
    description: str = ""
    tags: list[str] = []


# ==============================================================================
# LLM 配置
# ==============================================================================

# 提示词风格预定义 - 类级别常量
PROMPT_STYLES = {
    "compress": {
        "name": "信息压缩",
        "description": "极致压缩，只提取关键重点",
        "template": """请从以下知识中提取最核心的关键信息，以最简洁的方式呈现。

要求：
- 只保留核心要点
- 删除冗余描述
- 用最少的文字表达完整含义

知识内容：
{context}

用户问题：{query}

请输出压缩后的关键信息："""
    },
    "restate": {
        "name": "关键复述",
        "description": "关键语义原文复述",
        "template": """请根据以下知识回答用户问题，尽量保持原文语义，仅在必要时进行合理复述。

要求：
- 保持原文核心语义
- 可调整表达方式但不改原意
- 保留关键专业术语

知识内容：
{context}

用户问题：{query}

请输出回答："""
    },
    "rework": {
        "name": "加工改写",
        "description": "知识加工增加模型自我理解",
        "template": """请根据以下知识回答用户问题，在理解知识的基础上进行加工整合。

要求：
- 深入理解知识内涵
- 用自己的语言重新组织
- 可以补充相关背景说明
- 逻辑清晰便于理解

知识内容：
{context}

用户问题：{query}

请输出加工后的回答："""
    },
}


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


# ==============================================================================
# 缓存配置
# ==============================================================================

class CacheConfig(BaseModel):
    """缓存配置"""
    enabled: bool = True
    ttl: int = 3600                 # 缓存过期时间（秒）
    max_memory_items: int = 100     # 最大内存缓存条数
    persist: bool = True            # 是否持久化到磁盘
    cache_queries: bool = True      # 是否缓存查询结果


# ==============================================================================
# 向量存储配置
# ==============================================================================

class VectorStoreConfig(BaseModel):
    """向量存储配置"""
    enabled: bool = True
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    dimension: int = 512
    # 索引配置
    index_type: Literal["flat", "ivf", "hnsw"] = "flat"
    # 持久化
    persist_dir: str = "memory/knowledge_hub/vectors"


# ==============================================================================
# 主配置
# ==============================================================================

class KnowledgeHubConfig(BaseModel):
    """模块配置"""
    enabled: bool = True
    default_mode: RetrievalMode = RetrievalMode.DIRECT
    llm: LLMConfig = LLMConfig()
    cache: CacheConfig = CacheConfig()
    vector_store: VectorStoreConfig = VectorStoreConfig()
    sources: list[SourceConfig] = []

    storage_dir: str = "memory/knowledge_hub"
    default_retrieval: RetrievalConfig = RetrievalConfig()

    @classmethod
    def load(cls, path: str) -> "KnowledgeHubConfig":
        """从文件加载配置"""
        p = Path(path)
        if p.exists():
            import json
            data = json.loads(p.read_text())
            return cls(**data)
        return cls()

    def save(self, path: str):
        """保存配置到文件"""
        import json
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.model_dump(), ensure_ascii=False, indent=2))

    def get_source(self, source_id: str) -> SourceConfig | None:
        """获取指定知识源配置"""
        for source in self.sources:
            if source.id == source_id:
                return source
        return None

    def get_enabled_sources(self) -> list[SourceConfig]:
        """获取所有启用的知识源"""
        return [s for s in self.sources if s.enabled]
