"""KnowledgeHub API路由

提供知识检索、知识源管理、配置管理等 API。
"""

from typing import Optional, Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger


router = APIRouter(prefix="/api/knowledge_hub", tags=["knowledge_hub"])


# ==============================================================================
# 请求模型
# ==============================================================================

class RetrieveRequest(BaseModel):
    """检索请求"""
    query: str
    mode: Literal["direct", "vector", "hybrid", "llm"] = "hybrid"
    top_k: int = Field(default=10, ge=1, le=100)
    min_score: float = Field(default=0.3, ge=0, le=1)
    source_ids: list[str] = []
    use_cache: bool = True
    rerank: bool = True


class QueryDBRequest(BaseModel):
    """数据库查询请求"""
    question: str
    source_id: Optional[str] = None


class WebSearchRequest(BaseModel):
    """网络搜索请求"""
    query: str
    provider: Optional[str] = None
    max_results: int = Field(default=5, ge=1, le=20)
    fetch_content: bool = False


class ConfigUpdateRequest(BaseModel):
    """配置更新请求"""
    enabled: Optional[bool] = None
    default_mode: Optional[str] = None
    llm: Optional[dict] = None
    cache: Optional[dict] = None
    vector_store: Optional[dict] = None


class SourceCreateRequest(BaseModel):
    """创建知识源请求"""
    name: str
    source_type: Literal["local", "database", "web_search"]
    config: dict = {}
    local: Optional[dict] = None      # LocalSourceConfig
    database: Optional[dict] = None    # DatabaseSourceConfig
    web_search: Optional[dict] = None  # WebSearchSourceConfig
    retrieval: Optional[dict] = None   # RetrievalConfig
    enabled: bool = True
    priority: int = Field(default=5, ge=1, le=10)
    description: str = ""
    tags: list[str] = []


class RerankConfigRequest(BaseModel):
    """重排序配置请求"""
    enabled: bool = True
    semantic_weight: float = Field(default=0.5, ge=0, le=1)
    recency_weight: float = Field(default=0.2, ge=0, le=1)
    hotness_weight: float = Field(default=0.2, ge=0, le=1)
    source_weight: float = Field(default=0.1, ge=0, le=1)


# ==============================================================================
# 全局实例
# ==============================================================================

_hub = None


def get_hub():
    """获取Hub实例"""
    global _hub
    if _hub is None:
        from . import KnowledgeHub
        _hub = KnowledgeHub()
    return _hub


# ==============================================================================
# 检索 API
# ==============================================================================

@router.post("/retrieve")
async def retrieve(request: RetrieveRequest):
    """知识检索

    支持四种检索模式：
    - direct: 关键词检索（BM25）
    - vector: 向量语义检索
    - hybrid: 混合检索（向量+关键词）
    - llm: LLM 处理后返回
    """
    hub = get_hub()

    try:
        result = await hub.retrieve(
            query=request.query,
            mode=request.mode,
            use_cache=request.use_cache,
            top_k=request.top_k,
            min_score=request.min_score,
            source_ids=request.source_ids,
            rerank=request.rerank,
        )

        return {
            "code": 0,
            "data": {
                "content": result.content,
                "sources": result.sources,
                "mode": result.mode,
                "processing_time": result.processing_time,
                "llm_used": getattr(result, "llm_used", False),
            }
        }
    except Exception as e:
        logger.error(f"Retrieve failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query-db")
async def query_db(request: QueryDBRequest):
    """智能数据库查询

    使用自然语言查询数据库，LLM 自动生成 SQL。
    """
    hub = get_hub()

    try:
        result = await hub.query_database(
            question=request.question,
            source_id=request.source_id,
        )
        return {"code": 0, "data": result}
    except Exception as e:
        logger.error(f"Query DB failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/web-search")
async def web_search(request: WebSearchRequest):
    """网络搜索

    通过搜索引擎检索网络信息。
    """
    hub = get_hub()

    try:
        # 查找网络搜索连接器
        from .connectors.web_search import WebSearchConnector

        connector = None
        for sid, c in hub.connectors.items():
            if isinstance(c, WebSearchConnector):
                if request.provider is None or c.provider == request.provider:
                    connector = c
                    break

        if not connector:
            return {
                "code": 1,
                "message": "未配置网络搜索知识源",
                "data": []
            }

        results = await connector.search_with_content(
            request.query,
            fetch_content=request.fetch_content
        )

        return {
            "code": 0,
            "data": [
                {
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                    "content": r.content[:500] if r.content else "",
                    "source": r.source,
                    "score": r.score,
                }
                for r in results[:request.max_results]
            ]
        }

    except Exception as e:
        logger.error(f"Web search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# 配置 API
# ==============================================================================

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
            if isinstance(value, dict):
                # 合并字典配置
                current = getattr(hub.config, key)
                if hasattr(current, "model_dump"):
                    current_dict = current.model_dump()
                    current_dict.update(value)
                    # 重新创建配置对象
                    config_class = type(current)
                    setattr(hub.config, key, config_class(**current_dict))
                else:
                    setattr(hub.config, key, value)
            else:
                setattr(hub.config, key, value)

    return {"code": 0, "message": "Config updated"}


@router.put("/config/rerank")
async def update_rerank_config(request: RerankConfigRequest):
    """更新重排序配置"""
    hub = get_hub()

    if hub.config.default_retrieval:
        hub.config.default_retrieval.rerank = request.model_dump()

    if hub.reranker:
        hub.reranker.config = request.model_dump()

    return {"code": 0, "message": "Rerank config updated"}


@router.post("/cache/refresh")
async def refresh_cache(cache_type: str = "all"):
    """刷新缓存

    Args:
        cache_type: 缓存类型 (all/queries/documents)
    """
    hub = get_hub()

    await hub.refresh_cache(cache_type)

    return {"code": 0, "message": f"Cache cleared: {cache_type}"}


# ==============================================================================
# 知识源 API
# ==============================================================================

@router.get("/sources")
async def get_sources():
    """获取知识源列表"""
    hub = get_hub()
    sources = hub.get_sources()

    return {
        "code": 0,
        "data": [s.model_dump() for s in sources]
    }


@router.get("/sources/{source_id}")
async def get_source(source_id: str):
    """获取指定知识源"""
    hub = get_hub()
    source = hub.get_source(source_id)

    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    return {
        "code": 0,
        "data": source.model_dump()
    }


@router.post("/sources")
async def create_source(request: SourceCreateRequest):
    """创建知识源"""
    import uuid
    hub = get_hub()

    from . import SourceConfig

    source = SourceConfig(
        id=str(uuid.uuid4()),
        name=request.name,
        source_type=request.source_type,
        config=request.config,
        enabled=request.enabled,
        priority=request.priority,
        description=request.description,
        tags=request.tags,
    )

    # 设置类型特定配置
    if request.local and request.source_type == "local":
        from . import LocalSourceConfig
        source.local = LocalSourceConfig(**request.local)

    if request.database and request.source_type == "database":
        from . import DatabaseSourceConfig
        source.database = DatabaseSourceConfig(**request.database)

    if request.web_search and request.source_type == "web_search":
        from . import WebSearchSourceConfig
        source.web_search = WebSearchSourceConfig(**request.web_search)

    if request.retrieval:
        from . import RetrievalConfig
        source.retrieval = RetrievalConfig(**request.retrieval)

    success = hub.add_source(source)

    if success:
        return {
            "code": 0,
            "data": source.model_dump()
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to create source")


@router.post("/sources/{source_id}/sync")
async def sync_source(source_id: str):
    """同步知识源

    将知识源的内容索引到向量存储。
    """
    hub = get_hub()

    try:
        count = await hub.sync_source(source_id)
        return {
            "code": 0,
            "message": f"Synced {count} chunks",
            "data": {"chunks_count": count}
        }
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str):
    """删除知识源"""
    hub = get_hub()

    success = hub.remove_source(source_id)

    if success:
        return {"code": 0, "message": "Source deleted"}
    else:
        raise HTTPException(status_code=404, detail="Source not found")


# ==============================================================================
# 统计 API
# ==============================================================================

@router.get("/stats")
async def get_stats():
    """获取知识库统计信息"""
    hub = get_hub()

    sources = hub.get_sources()

    stats = {
        "total_sources": len(sources),
        "enabled_sources": len([s for s in sources if s.enabled]),
        "sources_by_type": {},
        "connectors_active": len(hub.connectors),
    }

    # 按类型统计
    for source in sources:
        source_type = source.source_type
        stats["sources_by_type"][source_type] = stats["sources_by_type"].get(source_type, 0) + 1

    # 向量存储统计
    if hub.vector_store:
        try:
            vector_stats = hub.vector_store.get_stats()
            stats["vector_store"] = vector_stats
        except Exception as e:
            stats["vector_store"] = {"error": str(e)}

    return {"code": 0, "data": stats}
