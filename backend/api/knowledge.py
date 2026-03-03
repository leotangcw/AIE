"""知识库 API"""

from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from loguru import logger

from backend.modules.agent.knowledge import (
    KnowledgeRAG,
    KnowledgeSource,
    get_knowledge_rag,
)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class SourceCreate(BaseModel):
    """创建知识源"""
    name: str
    source_type: str  # local, wiki, database, api
    config: dict = {}


class RetrieveRequest(BaseModel):
    """检索请求"""
    query: str
    top_k: int = 5
    source_ids: list[str] = []


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
        enabled=True,
    )

    rag.add_source(source)

    return {
        "id": source.id,
        "name": source.name,
        "source_type": source.source_type,
    }


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str):
    """删除知识源"""
    rag = get_knowledge_rag()
    success = rag.delete_source(source_id)

    if not success:
        raise HTTPException(status_code=404, detail="Source not found")

    return {"success": True}


@router.post("/sources/{source_id}/documents")
async def add_document(source_id: str, file: UploadFile = File(...)):
    """上传文档到知识源"""
    from pathlib import Path
    import tempfile

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
        # 提取文件名作为元数据
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

    chunks = rag.retrieve(
        query=request.query,
        top_k=request.top_k,
        source_ids=request.source_ids or None,
    )

    return {
        "results": [
            {
                "id": c.id,
                "source_id": c.source_id,
                "content": c.content,
                "metadata": c.metadata,
            }
            for c in chunks
        ],
        "count": len(chunks),
    }


@router.post("/augment")
async def augment_context(query: str, context: dict, top_k: int = 3):
    """增强上下文"""
    rag = get_knowledge_rag()

    augmented = rag.augment_context(query, context, top_k=top_k)
    return augmented


from datetime import datetime
