"""KnowledgeHub API路由

提供知识检索、知识源管理、配置管理等 API。
通过 app.state.shared 共享唯一的 KnowledgeHub 实例。
"""

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from pydantic import BaseModel, Field
from loguru import logger


router = APIRouter(prefix="/api/knowledge_hub", tags=["knowledge_hub"])


def _get_hub(req: Request):
    """从 app.state.shared 获取共享的 KnowledgeHub 实例"""
    hub = req.app.state.shared.get("knowledge_hub")
    if hub is None:
        raise HTTPException(status_code=503, detail="KnowledgeHub not initialized")
    return hub


# ==============================================================================
# 请求模型
# ==============================================================================

class RetrieveRequest(BaseModel):
    """检索请求"""
    query: str
    mode: Literal["direct", "vector", "hybrid", "llm", "graph"] = "hybrid"
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


class SourceUpdateRequest(BaseModel):
    """更新知识源请求"""
    name: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    config: Optional[dict] = None


class RerankConfigRequest(BaseModel):
    """重排序配置请求"""
    enabled: bool = True
    semantic_weight: float = Field(default=0.5, ge=0, le=1)
    recency_weight: float = Field(default=0.2, ge=0, le=1)
    hotness_weight: float = Field(default=0.2, ge=0, le=1)
    source_weight: float = Field(default=0.1, ge=0, le=1)


# ==============================================================================
# 检索 API
# ==============================================================================

@router.post("/retrieve")
async def retrieve(body: RetrieveRequest, req: Request):
    """知识检索

    支持四种检索模式：
    - direct: 关键词检索（BM25）
    - vector: 向量语义检索
    - hybrid: 混合检索（向量+关键词）
    - llm: LLM 处理后返回
    - graph: 图谱检索
    """
    hub = _get_hub(req)

    try:
        result = await hub.retrieve(
            query=body.query,
            mode=body.mode,
            use_cache=body.use_cache,
            top_k=body.top_k,
            min_score=body.min_score,
            source_ids=body.source_ids,
            rerank=body.rerank,
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
async def query_db(body: QueryDBRequest, req: Request):
    """智能数据库查询

    使用自然语言查询数据库，LLM 自动生成 SQL。
    """
    hub = _get_hub(req)

    try:
        result = await hub.query_database(
            question=body.question,
            source_id=body.source_id,
        )
        return {"code": 0, "data": result}
    except Exception as e:
        logger.error(f"Query DB failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/web-search")
async def web_search(body: WebSearchRequest, req: Request):
    """网络搜索

    通过搜索引擎检索网络信息。
    """
    hub = _get_hub(req)

    try:
        # 查找网络搜索连接器
        from .connectors.web_search import WebSearchConnector

        connector = None
        for sid, c in hub.connectors.items():
            if isinstance(c, WebSearchConnector):
                if body.provider is None or c.provider == body.provider:
                    connector = c
                    break

        if not connector:
            return {
                "code": 1,
                "message": "未配置网络搜索知识源",
                "data": []
            }

        results = await connector.search_with_content(
            body.query,
            fetch_content=body.fetch_content
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
                for r in results[:body.max_results]
            ]
        }

    except Exception as e:
        logger.error(f"Web search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# 配置 API
# ==============================================================================

@router.get("/config")
async def get_config(req: Request):
    """获取配置"""
    hub = _get_hub(req)
    return {
        "code": 0,
        "data": hub.config.model_dump()
    }


@router.put("/config")
async def update_config(body: ConfigUpdateRequest, req: Request):
    """更新配置"""
    hub = _get_hub(req)

    update_data = body.model_dump(exclude_unset=True)
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
async def update_rerank_config(body: RerankConfigRequest, req: Request):
    """更新重排序配置"""
    hub = _get_hub(req)

    if hub.config.default_retrieval:
        hub.config.default_retrieval.rerank = body.model_dump()

    if hub.reranker:
        hub.reranker.config = body.model_dump()

    return {"code": 0, "message": "Rerank config updated"}


@router.post("/cache/refresh")
async def refresh_cache(cache_type: str = "all", req: Request = None):
    """刷新缓存

    Args:
        cache_type: 缓存类型 (all/queries/documents)
    """
    hub = _get_hub(req)

    await hub.refresh_cache(cache_type)

    return {"code": 0, "message": f"Cache cleared: {cache_type}"}


# ==============================================================================
# 知识源 API
# ==============================================================================

@router.get("/sources")
async def get_sources(req: Request):
    """获取知识源列表"""
    hub = _get_hub(req)
    sources = hub.get_sources()

    return {
        "code": 0,
        "data": [s.model_dump() for s in sources]
    }


@router.get("/sources/{source_id}")
async def get_source(source_id: str, req: Request):
    """获取指定知识源"""
    hub = _get_hub(req)
    source = hub.get_source(source_id)

    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    return {
        "code": 0,
        "data": source.model_dump()
    }


@router.post("/sources")
async def create_source(body: SourceCreateRequest, req: Request):
    """创建知识源"""
    hub = _get_hub(req)

    from . import SourceConfig

    source = SourceConfig(
        id=str(uuid.uuid4()),
        name=body.name,
        source_type=body.source_type,
        config=body.config,
        enabled=body.enabled,
        priority=body.priority,
        description=body.description,
        tags=body.tags,
    )

    # 设置类型特定配置
    if body.local and body.source_type == "local":
        from . import LocalSourceConfig
        source.local = LocalSourceConfig(**body.local)

    if body.database and body.source_type == "database":
        from . import DatabaseSourceConfig
        source.database = DatabaseSourceConfig(**body.database)

    if body.web_search and body.source_type == "web_search":
        from . import WebSearchSourceConfig
        source.web_search = WebSearchSourceConfig(**body.web_search)

    if body.retrieval:
        from . import RetrievalConfig
        source.retrieval = RetrievalConfig(**body.retrieval)

    success = await hub.add_source(source)

    if success:
        return {
            "code": 0,
            "data": source.model_dump()
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to create source")


@router.put("/sources/{source_id}")
async def update_source(source_id: str, body: SourceUpdateRequest, req: Request):
    """更新知识源"""
    hub = _get_hub(req)
    source = hub.get_source(source_id)

    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None and hasattr(source, key):
            setattr(source, key, value)

    # 启用/禁用时管理连接器
    if "enabled" in update_data:
        if source.enabled and source_id not in hub.connectors:
            try:
                connector = await hub._create_connector(source)
                if connector:
                    hub.connectors[source_id] = connector
            except Exception as e:
                logger.warning(f"Failed to create connector on enable: {e}")
        elif not source.enabled and source_id in hub.connectors:
            connector = hub.connectors.pop(source_id)
            if hasattr(connector, "disconnect"):
                try:
                    await connector.disconnect()
                except Exception as e:
                    logger.warning(f"Failed to disconnect connector: {e}")

    return {"code": 0, "message": "Source updated"}


@router.post("/sources/{source_id}/sync")
async def sync_source(source_id: str, req: Request):
    """同步知识源

    将知识源的内容索引到向量存储。
    """
    hub = _get_hub(req)

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


@router.post("/sources/{source_id}/documents")
async def add_document(source_id: str, file: UploadFile = File(...), req: Request = None):
    """上传文档到知识源

    保存文件内容到向量存储，关联到指定的知识源。
    """
    import tempfile

    hub = _get_hub(req)
    source = hub.get_source(source_id)

    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        metadata = {
            "filename": file.filename,
            "uploaded_at": datetime.now().isoformat(),
            "source_id": source_id,
        }

        if hub.vector_store:
            text_content = content.decode("utf-8", errors="replace")
            hub.vector_store.add(
                content=text_content,
                metadata=metadata,
                source_type="knowledge",
                source_id=source_id,
            )
            return {"code": 0, "data": {"chunks_added": 1}}
        else:
            raise HTTPException(
                status_code=400,
                detail="Vector store not available for document upload"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process document: {str(e)}")
    finally:
        tmp_path.unlink(missing_ok=True)


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str, req: Request):
    """删除知识源"""
    hub = _get_hub(req)

    success = await hub.remove_source(source_id)

    if success:
        return {"code": 0, "message": "Source deleted"}
    else:
        raise HTTPException(status_code=404, detail="Source not found")


# ==============================================================================
# 目录浏览 API
# ==============================================================================

@router.get("/browse-directory")
async def browse_directory(path: str, req: Request):
    """浏览服务器目录结构

    用于前端选择本地知识源的目录路径。
    """
    resolved = os.path.realpath(path)
    if not os.path.isdir(resolved):
        raise HTTPException(status_code=404, detail="Directory not found")

    try:
        entries = []
        for entry in sorted(os.listdir(resolved)):
            full = os.path.join(resolved, entry)
            entries.append({
                "name": entry,
                "path": full,
                "is_dir": os.path.isdir(full),
            })
        return {"code": 0, "data": entries}
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")


# ==============================================================================
# 统计 API
# ==============================================================================

@router.get("/stats")
async def get_stats(req: Request):
    """获取知识库统计信息"""
    hub = _get_hub(req)

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
