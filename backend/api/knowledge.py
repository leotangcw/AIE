"""知识库 API"""

from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from loguru import logger
from datetime import datetime

from backend.modules.agent.knowledge import (
    KnowledgeRAG,
    KnowledgeSource,
    get_knowledge_rag,
)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class SourceCreate(BaseModel):
    """创建知识源"""
    name: str
    source_type: Literal["local", "api", "database", "wiki"]
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


@router.get("/sources")
async def get_sources():
    """获取所有知识源"""
    rag = get_knowledge_rag()
    sources = rag.get_all_sources()

    return [
        {
            "id": s.id,
            "name": s.name,
            "source_type": s.source_type,
            "enabled": s.enabled,
            "priority": s.priority,
            "sync_interval": s.sync_interval,
            "created_at": s.created_at,
            "last_sync": s.last_sync,
        }
        for s in sources
    ]


@router.post("/sources")
async def create_source(create: SourceCreate):
    """创建知识源"""
    rag = get_knowledge_rag()

    source = KnowledgeSource(
        name=create.name,
        source_type=create.source_type,
        config=create.config,
        enabled=create.enabled,
        priority=create.priority,
        sync_interval=create.sync_interval,
    )

    rag.add_source(source)

    # 如果是本地知识源，同步内容
    if create.source_type == "local" and create.config.get("path"):
        rag.sync_source(source.id)

    return {
        "id": source.id,
        "name": source.name,
        "source_type": source.source_type,
    }


@router.get("/sources/{source_id}")
async def get_source(source_id: str):
    """获取知识源详情"""
    rag = get_knowledge_rag()
    source = rag.get_source(source_id)

    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    return source.to_dict()


@router.put("/sources/{source_id}")
async def update_source(source_id: str, update: SourceUpdate):
    """更新知识源"""
    rag = get_knowledge_rag()

    update_data = update.model_dump(exclude_unset=True)
    success = rag.update_source(source_id, **update_data)

    if not success:
        raise HTTPException(status_code=404, detail="Source not found")

    return {"success": True}


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str):
    """删除知识源"""
    rag = get_knowledge_rag()
    success = rag.delete_source(source_id)

    if not success:
        raise HTTPException(status_code=404, detail="Source not found")

    return {"success": True}


@router.post("/sources/{source_id}/sync")
async def sync_source(source_id: str):
    """同步知识源"""
    rag = get_knowledge_rag()
    success = rag.sync_source(source_id)

    if not success:
        raise HTTPException(status_code=404, detail="Source not found")

    return {"success": True, "message": "Source synced successfully"}


@router.post("/sources/{source_id}/documents")
async def add_document(source_id: str, file: UploadFile = File(...)):
    """上传文档到知识源"""
    import tempfile
    from pathlib import Path

    rag = get_knowledge_rag()
    source = rag.get_source(source_id)

    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    # 保存上传文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        metadata = {
            "filename": file.filename,
            "uploaded_at": datetime.now().isoformat(),
        }

        count = rag.add_document(source_id, content.decode("utf-8"), metadata)
        return {"chunks_added": count}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process document: {str(e)}")
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/retrieve")
async def retrieve(request: RetrieveRequest):
    """检索知识"""
    rag = get_knowledge_rag()

    refs = rag.retrieve(
        query=request.query,
        method=request.method,
        top_k=request.top_k,
        source_ids=request.source_ids or None,
    )

    return {
        "results": [
            {
                "id": r.source_id,
                "source_name": r.source_name,
                "content": r.content,
                "file_path": r.file_path,
                "line_start": r.line_start,
                "line_end": r.line_end,
                "score": r.score,
            }
            for r in refs
        ],
        "count": len(refs),
        "method": request.method if request.method != "auto" else rag._select_best_method(request.query),
    }


@router.post("/retrieve/all-methods")
async def retrieve_all_methods(query: str, top_k: int = 5):
    """使用所有方式检索"""
    rag = get_knowledge_rag()

    results = rag.retrieve_all_methods(query, top_k)

    return {
        method: [
            {
                "source_name": r.source_name,
                "content": r.content,
                "score": r.score,
            }
            for r in refs
        ]
        for method, refs in results.items()
    }


@router.post("/augment")
async def augment_context(query: str, context: dict, method: str = "auto", top_k: int = 3):
    """增强上下文"""
    rag = get_knowledge_rag()

    augmented = rag.augment_context(query, context, method=method, top_k=top_k)
    return augmented
