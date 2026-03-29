"""知识库 API

已迁移至 KnowledgeHub 系统。保持原有 /api/knowledge 端点路径以兼容旧客户端。
所有底层实现使用 KnowledgeHub 模块，通过 app.state.shared 共享实例。
"""

import uuid
from typing import Literal
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from pydantic import BaseModel
from loguru import logger
from datetime import datetime

from backend.modules.knowledge_hub.config import SourceConfig, LocalSourceConfig
from backend.modules.knowledge_hub.processors.base import KnowledgeResult

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def _get_hub(req: Request):
    """从 app.state.shared 获取共享的 KnowledgeHub 实例"""
    hub = req.app.state.shared.get("knowledge_hub")
    if hub is None:
        raise HTTPException(status_code=503, detail="KnowledgeHub not initialized")
    return hub


# ==============================================================================
# 请求模型
# ==============================================================================

class SourceCreate(BaseModel):
    """创建知识源"""
    name: str
    source_type: Literal["local", "api", "database", "wiki"] = "local"
    config: dict = {}
    enabled: bool = True
    priority: int = 5
    sync_interval: int = 60


class SourceUpdate(BaseModel):
    """更新知识源"""
    name: str = None
    config: dict = None
    enabled: bool = None
    priority: int = None
    sync_interval: int = None


class RetrieveRequest(BaseModel):
    """检索请求"""
    query: str
    method: Literal["auto", "rag-skill", "bm25", "vector"] = "auto"
    top_k: int = 5
    source_ids: list[str] = []


class ConsolidateRequest(BaseModel):
    """沉淀请求"""
    session_id: str


# ==============================================================================
# 旧方法名到新检索模式的映射
# ==============================================================================

_METHOD_MAP = {
    "auto": "hybrid",
    "bm25": "direct",
    "vector": "vector",
    "rag-skill": "direct",
}


# ==============================================================================
# 知识源管理 API
# ==============================================================================

@router.get("/sources")
async def get_sources(req: Request):
    """获取所有知识源"""
    hub = _get_hub(req)
    sources = hub.get_sources()

    return [
        {
            "id": s.id,
            "name": s.name,
            "source_type": s.source_type,
            "enabled": s.enabled,
            "priority": s.priority,
            "sync_interval": 60,  # KnowledgeHub 使用连接器级别控制
            "created_at": None,
            "last_sync": None,
        }
        for s in sources
    ]


@router.post("/sources")
async def create_source(body: SourceCreate, req: Request):
    """创建知识源"""
    hub = _get_hub(req)

    # 映射旧的 source_type 到 KnowledgeHub 支持的类型
    hub_type = body.source_type
    if hub_type in ("api", "wiki"):
        hub_type = "local"

    source = SourceConfig(
        id=str(uuid.uuid4()),
        name=body.name,
        source_type=hub_type,
        config=body.config,
        enabled=body.enabled,
        priority=body.priority,
    )

    # 本地知识源额外设置 LocalSourceConfig
    if hub_type == "local" and body.config.get("path"):
        source.local = LocalSourceConfig(path=body.config["path"])

    success = await hub.add_source(source)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to create source")

    # 如果是本地知识源，尝试同步
    if hub_type == "local" and body.config.get("path"):
        try:
            await hub.sync_source(source.id)
        except Exception as e:
            logger.warning(f"自动同步失败（源已创建）: {e}")

    return {
        "id": source.id,
        "name": source.name,
        "source_type": source.source_type,
    }


@router.get("/sources/{source_id}")
async def get_source(source_id: str, req: Request):
    """获取知识源详情"""
    hub = _get_hub(req)
    source = hub.get_source(source_id)

    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    return source.model_dump()


@router.put("/sources/{source_id}")
async def update_source(source_id: str, body: SourceUpdate, req: Request):
    """更新知识源"""
    hub = _get_hub(req)
    source = hub.get_source(source_id)

    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    # 更新字段
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None and hasattr(source, key):
            setattr(source, key, value)

    # KnowledgeHub 的 config 存在配置列表中，修改后直接生效
    return {"success": True}


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str, req: Request):
    """删除知识源"""
    hub = _get_hub(req)
    success = await hub.remove_source(source_id)

    if not success:
        raise HTTPException(status_code=404, detail="Source not found")

    return {"success": True}


@router.post("/sources/{source_id}/sync")
async def sync_source(source_id: str, req: Request):
    """同步知识源"""
    hub = _get_hub(req)

    try:
        count = await hub.sync_source(source_id)
        return {"success": True, "message": f"Source synced successfully ({count} chunks)"}
    except Exception as e:
        logger.error(f"同步失败: {e}")
        raise HTTPException(status_code=404, detail=f"Sync failed: {str(e)}")


@router.post("/sources/{source_id}/documents")
async def add_document(source_id: str, file: UploadFile = File(...), req: Request = None):
    """上传文档到知识源

    KnowledgeHub 通过 sync_source 处理文档索引。
    此端点保存文件内容到向量存储。
    """
    import tempfile
    from pathlib import Path

    hub = _get_hub(req)
    source = hub.get_source(source_id)

    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    # 保存上传文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        # KnowledgeHub 使用向量存储进行文档管理
        metadata = {
            "filename": file.filename,
            "uploaded_at": datetime.now().isoformat(),
            "source_id": source_id,
        }

        # 将内容直接添加到向量存储
        if hub.vector_store:
            text_content = content.decode("utf-8", errors="replace")
            hub.vector_store.add(
                content=text_content,
                metadata=metadata,
                source_type="knowledge",
                source_id=source_id,
            )
            return {"chunks_added": 1}
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


# ==============================================================================
# 检索 API
# ==============================================================================

@router.post("/retrieve")
async def retrieve(body: RetrieveRequest, req: Request):
    """检索知识"""
    hub = _get_hub(req)

    # 映射旧方法名到新检索模式
    mode = _METHOD_MAP.get(body.method, "hybrid")

    result: KnowledgeResult = await hub.retrieve(
        query=body.query,
        mode=mode,
        use_cache=True,
        top_k=body.top_k,
        source_ids=body.source_ids or None,
    )

    # 将 KnowledgeResult 转换为旧格式
    return {
        "results": [
            {
                "id": s.get("source_id", s.get("source", "")),
                "source_name": s.get("source", s.get("source_id", "")),
                "content": s.get("content", ""),
                "file_path": s.get("file_path"),
                "line_start": None,
                "line_end": None,
                "score": s.get("score", s.get("original_score", 0)),
            }
            for s in result.sources
        ],
        "count": len(result.sources),
        "method": mode,
    }


@router.post("/retrieve/all-methods")
async def retrieve_all_methods(query: str, req: Request, top_k: int = 5):
    """使用所有方式检索"""
    hub = _get_hub(req)

    modes = ["direct", "vector", "hybrid"]
    results = {}

    for mode in modes:
        try:
            result = await hub.retrieve(
                query=query,
                mode=mode,
                use_cache=False,
                top_k=top_k,
            )
            results[mode] = [
                {
                    "source_name": s.get("source", ""),
                    "content": s.get("content", ""),
                    "score": s.get("score", 0),
                }
                for s in result.sources
            ]
        except Exception as e:
            logger.warning(f"检索模式 {mode} 失败: {e}")
            results[mode] = []

    return results


@router.post("/augment")
async def augment_context(query: str, req: Request, context: dict = None, method: str = "auto", top_k: int = 3):
    """增强上下文"""
    if context is None:
        context = {}
    hub = _get_hub(req)

    # 映射旧方法名到新检索模式
    mode = _METHOD_MAP.get(method, "hybrid")

    result = await hub.retrieve(
        query=query,
        mode=mode,
        use_cache=True,
        top_k=top_k,
    )

    if not result.sources:
        return context

    # 构建知识上下文
    knowledge_context = "\n\n".join([
        f"[知识 {i+1} ({s.get('source', '')})]: {s.get('content', '')}"
        for i, s in enumerate(result.sources)
    ])

    # 构建增强后的上下文
    augmented = {
        **context,
        "knowledge_context": knowledge_context,
        "knowledge_sources": [s.get("source", "") for s in result.sources],
        "knowledge_count": len(result.sources),
        "knowledge_method": mode,
    }

    return augmented
