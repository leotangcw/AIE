"""Vector Memory API - Integration with Memory-MCP-Server.

This module provides API endpoints for the hierarchical L0/L1/L2 memory system
powered by Memory-MCP-Server via MCP Protocol.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/memory/vector", tags=["memory", "vector"])


# Lazy import to avoid circular imports
def get_memory_adapter():
    """Get the MemoryAdapter from app state."""
    from backend.modules.mcp.memory_adapter import get_memory_adapter as _get_adapter
    return _get_adapter()


# ==================== Request/Response Models ====================

class StoreMemoryRequest(BaseModel):
    content: str = Field(..., description="记忆内容")
    name: str = Field(..., description="记忆名称")
    context_type: str = Field("memory", description="类型: memory/resource/skill")
    tags: list[str] = Field(default_factory=list, description="标签")
    source: str = Field("chat", description="来源: chat/document/event")
    metadata: dict = Field(default_factory=dict, description="元数据")
    user_id: Optional[str] = Field(None, description="用户ID")
    session_id: Optional[str] = Field(None, description="会话ID")


class StoreMemoryResponse(BaseModel):
    success: bool
    id: Optional[str] = None
    uri: Optional[str] = None
    message: Optional[str] = None


class RecallMemoryRequest(BaseModel):
    query: str = Field(..., description="查询文本")
    context_type: str = Field("all", description="类型过滤: memory/resource/skill/all")
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    limit: int = Field(5, description="返回数量")
    level: int = Field(2, description="内容层级: 0=摘要, 1=概述, 2=完整")


class MemoryResult(BaseModel):
    uri: str
    name: str
    content: str
    context_type: str
    level: int
    score: float
    tags: list[str]
    source: str


class RecallMemoryResponse(BaseModel):
    success: bool
    results: list[MemoryResult] = Field(default_factory=list)
    total: int = 0
    message: Optional[str] = None


class GetMemoryRequest(BaseModel):
    uri: str = Field(..., description="记忆URI")
    level: Optional[int] = Field(None, description="内容层级")


class VectorStatsResponse(BaseModel):
    total_memories: int = 0
    by_context_type: dict[str, int] = Field(default_factory=dict)
    by_level: dict[int, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    total_vectors: int = 0


class ListMemoriesResponse(BaseModel):
    success: bool
    memories: list[dict] = Field(default_factory=list)
    count: int = 0


# ==================== API Endpoints ====================

@router.post("/store", response_model=StoreMemoryResponse)
async def store_memory(request: StoreMemoryRequest) -> StoreMemoryResponse:
    """存储新记忆到向量记忆库"""
    try:
        adapter = get_memory_adapter()
        result = await adapter.store(
            content=request.content,
            name=request.name,
            context_type=request.context_type,
            tags=request.tags,
            source=request.source,
            metadata=request.metadata,
            user_id=request.user_id,
            session_id=request.session_id,
        )

        if result:
            return StoreMemoryResponse(
                success=True,
                id=result.get("id"),
                uri=result.get("uri"),
            )
        else:
            return StoreMemoryResponse(
                success=False,
                message="Memory-MCP-Server not available",
            )
    except Exception as e:
        logger.exception(f"Failed to store memory: {e}")
        return StoreMemoryResponse(success=False, message=str(e))


@router.post("/recall", response_model=RecallMemoryResponse)
async def recall_memories(request: RecallMemoryRequest) -> RecallMemoryResponse:
    """检索相关记忆"""
    try:
        adapter = get_memory_adapter()
        result = await adapter.recall(
            query=request.query,
            context_type=request.context_type,
            user_id=request.user_id,
            agent_id=request.agent_id,
            session_id=request.session_id,
            limit=request.limit,
            level=request.level,
        )

        if result is None:
            return RecallMemoryResponse(success=False, message="Memory-MCP-Server not available")

        results = []
        for r in result.get("results", []):
            results.append(MemoryResult(
                uri=r.get("uri", ""),
                name=r.get("name", ""),
                content=r.get("content", ""),
                context_type=r.get("context_type", ""),
                level=r.get("level", 2),
                score=r.get("final_score", 0.0),
                tags=r.get("tags", []),
                source=r.get("source", ""),
            ))

        return RecallMemoryResponse(
            success=True,
            results=results,
            total=len(results),
        )
    except Exception as e:
        logger.exception(f"Failed to recall memories: {e}")
        return RecallMemoryResponse(success=False, message=str(e))


@router.get("/get", response_model=dict | None)
async def get_memory(uri: str, level: int | None = None) -> dict | None:
    """获取指定记忆"""
    try:
        adapter = get_memory_adapter()
        return await adapter.get(uri=uri, level=level)
    except Exception as e:
        logger.exception(f"Failed to get memory: {e}")
        return None


@router.get("/stats", response_model=VectorStatsResponse | None)
async def get_vector_stats() -> VectorStatsResponse | None:
    """获取向量记忆统计"""
    try:
        adapter = get_memory_adapter()
        result = await adapter.stats()
        if result:
            return VectorStatsResponse(**result)
        return None
    except Exception as e:
        logger.exception(f"Failed to get stats: {e}")
        return None


@router.get("/list", response_model=ListMemoriesResponse)
async def list_memories(
    uri_prefix: str | None = None,
    context_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> ListMemoriesResponse:
    """列出记忆"""
    try:
        adapter = get_memory_adapter()
        memories = await adapter.list_memories(
            uri_prefix=uri_prefix,
            context_type=context_type,
            limit=limit,
            offset=offset,
        )
        return ListMemoriesResponse(
            success=True,
            memories=memories,
            count=len(memories),
        )
    except Exception as e:
        logger.exception(f"Failed to list memories: {e}")
        return ListMemoriesResponse(success=False, memories=[], count=0)


@router.delete("/delete")
async def delete_memory(uri: str) -> dict:
    """删除记忆"""
    try:
        adapter = get_memory_adapter()
        deleted = await adapter.delete(uri)
        return {"success": deleted}
    except Exception as e:
        logger.exception(f"Failed to delete memory: {e}")
        return {"success": False, "error": str(e)}
