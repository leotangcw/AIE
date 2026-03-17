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


class SourceCreateRequest(BaseModel):
    """创建知识源请求"""
    name: str
    source_type: Literal["local", "database", "web", "feishu", "wecom"]
    config: dict = {}
    enabled: bool = True
    priority: int = 5


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


@router.get("/sources")
async def get_sources():
    """获取知识源列表"""
    hub = get_hub()
    sources = hub.get_sources()

    return {
        "code": 0,
        "data": [s.model_dump() for s in sources]
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
        priority=request.priority
    )

    hub.add_source(source)

    return {
        "code": 0,
        "data": source.model_dump()
    }


@router.post("/sources/{source_id}/sync")
async def sync_source(source_id: str):
    """同步知识源"""
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
