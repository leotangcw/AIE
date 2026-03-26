"""GraphRAG API 端点

提供知识图谱检索的 HTTP 接口：
- POST /api/graph_rag/insert — 索引文档
- POST /api/graph_rag/query — 查询知识
- GET /api/graph_rag/stats — 获取统计
- GET /api/graph_rag/namespaces — 列出命名空间
- DELETE /api/graph_rag/namespace/{namespace} — 清空命名空间
"""

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from pydantic import BaseModel, Field

from .core import GraphRAGClient, get_graph_rag, LIGHTERAG_AVAILABLE
from .config import GraphRAGSettings, QueryResult, InsertResult

router = APIRouter(prefix="/api/graph_rag", tags=["graph_rag"])


# Request/Response Models
class InsertRequest(BaseModel):
    """索引请求"""

    content: str | list[str] = Field(..., description="文档内容或内容列表")
    namespace: str = Field(default="default", description="命名空间")
    workspace: str = Field(default="default", description="工作空间")
    file_paths: Optional[list[str]] = Field(default=None, description="文件路径列表")
    doc_type: str = Field(default="document", description="文档类型")


class InsertResponse(BaseModel):
    """索引响应"""

    success: bool = Field(..., description="是否成功")
    namespace: str = Field(..., description="命名空间")
    document_count: int = Field(default=0, description="文档数量")
    message: Optional[str] = Field(default=None, description="消息")
    processing_time: float = Field(default=0.0, description="处理时间（秒）")


class QueryRequest(BaseModel):
    """查询请求"""

    query: str = Field(..., description="查询问题")
    namespace: str = Field(default="default", description="命名空间")
    workspace: str = Field(default="default", description="工作空间")
    mode: Literal["local", "global", "hybrid", "naive", "mix"] = Field(
        default="hybrid", description="查询模式"
    )
    top_k: int = Field(default=10, ge=1, le=100, description="返回结果数量")
    only_need_context: bool = Field(default=False, description="仅返回上下文")


class QueryResponse(BaseModel):
    """查询响应"""

    content: str = Field(default="", description="回答内容")
    mode: str = Field(default="", description="查询模式")
    context: Optional[str] = Field(default=None, description="检索上下文")
    processing_time: float = Field(default=0.0, description="处理时间（秒）")
    error: Optional[str] = Field(default=None, description="错误信息")


class StatsResponse(BaseModel):
    """统计响应"""

    available: bool = Field(default=False, description="是否可用")
    namespace: str = Field(default="", description="命名空间")
    workspace: str = Field(default="", description="工作空间")
    node_count: int = Field(default=0, description="节点数量")
    edge_count: int = Field(default=0, description="边数量")
    document_count: int = Field(default=0, description="文档数量")
    error: Optional[str] = Field(default=None, description="错误信息")


class NamespaceInfo(BaseModel):
    """命名空间信息"""

    namespace: str
    workspace: str
    stats: StatsResponse


class NamespacesResponse(BaseModel):
    """命名空间列表响应"""

    namespaces: list[NamespaceInfo] = Field(default_factory=list)
    total: int = Field(default=0)


class ClearResponse(BaseModel):
    """清空响应"""

    success: bool = Field(..., description="是否成功")
    namespace: str = Field(..., description="命名空间")
    message: str = Field(default="", description="消息")


class StatusResponse(BaseModel):
    """状态响应"""

    available: bool = Field(..., description="LightRAG 是否可用")
    message: str = Field(default="", description="状态消息")


# Helper function
def _get_client(namespace: str, workspace: str) -> GraphRAGClient:
    """获取 GraphRAG 客户端"""
    return GraphRAGClient(namespace=namespace, workspace=workspace)


# API Endpoints
@router.get("/status", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    """获取 GraphRAG 状态"""
    if LIGHTERAG_AVAILABLE:
        return StatusResponse(
            available=True, message="LightRAG is available and ready"
        )
    else:
        return StatusResponse(
            available=False,
            message="LightRAG not installed. Install with: pip install lightrag-hku",
        )


@router.post("/insert", response_model=InsertResponse)
async def insert_document(request: InsertRequest) -> InsertResponse:
    """索引文档到知识图谱

    自动从文档中抽取实体和关系，构建知识图谱。
    """
    if not LIGHTERAG_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LightRAG not installed. Install with: pip install lightrag-hku",
        )

    try:
        client = await get_graph_rag(
            namespace=request.namespace, workspace=request.workspace
        )

        result: InsertResult = await client.insert(
            content=request.content,
            file_paths=request.file_paths,
            doc_type=request.doc_type,
        )

        return InsertResponse(
            success=result.success,
            namespace=result.namespace,
            document_count=result.document_count,
            message="Documents indexed successfully" if result.success else result.error,
            processing_time=result.processing_time,
        )

    except Exception as e:
        logger.exception(f"Failed to insert document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=QueryResponse)
async def query_knowledge(request: QueryRequest) -> QueryResponse:
    """查询知识图谱

    支持多种查询模式：
    - local: 基于实体的局部检索，适合具体事实查询
    - global: 基于社区的全局检索，适合概括性问题
    - hybrid: 混合 local + global
    - naive: 纯向量检索，适合简单相似度搜索
    - mix: KG + 向量 + 重排序，最高质量
    """
    if not LIGHTERAG_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LightRAG not installed. Install with: pip install lightrag-hku",
        )

    try:
        client = await get_graph_rag(
            namespace=request.namespace, workspace=request.workspace
        )

        result: QueryResult = await client.query(
            query=request.query,
            mode=request.mode,
            top_k=request.top_k,
            only_need_context=request.only_need_context,
        )

        return QueryResponse(
            content=result.content,
            mode=result.mode,
            context=result.context,
            processing_time=result.processing_time,
            error=result.error,
        )

    except Exception as e:
        logger.exception(f"Failed to query knowledge: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    namespace: str = "default", workspace: str = "default"
) -> StatsResponse:
    """获取知识图谱统计信息"""
    if not LIGHTERAG_AVAILABLE:
        return StatsResponse(
            available=False,
            namespace=namespace,
            workspace=workspace,
            error="LightRAG not installed",
        )

    try:
        client = await get_graph_rag(namespace=namespace, workspace=workspace)
        stats = await client.get_stats()

        return StatsResponse(
            available=stats.available,
            namespace=stats.namespace,
            workspace=stats.workspace,
            node_count=stats.node_count,
            edge_count=stats.edge_count,
            document_count=stats.document_count,
            error=stats.error,
        )

    except Exception as e:
        logger.exception(f"Failed to get stats: {e}")
        return StatsResponse(
            available=False,
            namespace=namespace,
            workspace=workspace,
            error=str(e),
        )


@router.get("/namespaces", response_model=NamespacesResponse)
async def list_namespaces(workspace: str = "default") -> NamespacesResponse:
    """列出所有命名空间

    注意：此接口返回已缓存的命名空间，可能不包含所有已创建的命名空间。
    """
    # 获取所有已缓存的客户端实例
    from .core import GraphRAGClient

    namespaces = []
    for key, client in GraphRAGClient._instances.items():
        if client.workspace == workspace:
            stats = await client.get_stats()
            namespaces.append(
                NamespaceInfo(
                    namespace=client.namespace,
                    workspace=client.workspace,
                    stats=StatsResponse(
                        available=stats.available,
                        namespace=stats.namespace,
                        workspace=stats.workspace,
                        node_count=stats.node_count,
                        edge_count=stats.edge_count,
                        document_count=stats.document_count,
                        error=stats.error,
                    ),
                )
            )

    return NamespacesResponse(namespaces=namespaces, total=len(namespaces))


@router.delete("/namespace/{namespace}", response_model=ClearResponse)
async def clear_namespace(
    namespace: str, workspace: str = "default"
) -> ClearResponse:
    """清空命名空间

    警告：此操作将删除该命名空间下的所有知识图谱数据，不可恢复。
    """
    if not LIGHTERAG_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LightRAG not installed",
        )

    try:
        client = await get_graph_rag(namespace=namespace, workspace=workspace)
        success = await client.clear()

        if success:
            # 清除缓存的实例
            GraphRAGClient.clear_instance(namespace, workspace)
            return ClearResponse(
                success=True,
                namespace=namespace,
                message=f"Namespace '{namespace}' cleared successfully",
            )
        else:
            return ClearResponse(
                success=False,
                namespace=namespace,
                message=f"Failed to clear namespace '{namespace}'",
            )

    except Exception as e:
        logger.exception(f"Failed to clear namespace: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Batch operations
class BatchInsertRequest(BaseModel):
    """批量索引请求"""

    documents: list[dict] = Field(..., description="文档列表")
    namespace: str = Field(default="default", description="命名空间")
    workspace: str = Field(default="default", description="工作空间")


class BatchInsertResponse(BaseModel):
    """批量索引响应"""

    success: bool = Field(..., description="是否成功")
    namespace: str = Field(..., description="命名空间")
    total_documents: int = Field(default=0, description="总文档数")
    successful_count: int = Field(default=0, description="成功数量")
    failed_count: int = Field(default=0, description="失败数量")
    processing_time: float = Field(default=0.0, description="处理时间（秒）")


@router.post("/batch/insert", response_model=BatchInsertResponse)
async def batch_insert_documents(request: BatchInsertRequest) -> BatchInsertResponse:
    """批量索引文档

    每个文档应包含 content 字段，可选 file_paths 和 doc_type 字段。
    """
    if not LIGHTERAG_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LightRAG not installed",
        )

    try:
        import time

        start_time = time.time()
        client = await get_graph_rag(
            namespace=request.namespace, workspace=request.workspace
        )

        total = len(request.documents)
        successful = 0
        failed = 0

        for doc in request.documents:
            content = doc.get("content")
            if not content:
                failed += 1
                continue

            file_paths = doc.get("file_paths")
            doc_type = doc.get("doc_type", "document")

            result = await client.insert(
                content=content, file_paths=file_paths, doc_type=doc_type
            )

            if result.success:
                successful += 1
            else:
                failed += 1

        processing_time = time.time() - start_time

        return BatchInsertResponse(
            success=failed == 0,
            namespace=request.namespace,
            total_documents=total,
            successful_count=successful,
            failed_count=failed,
            processing_time=processing_time,
        )

    except Exception as e:
        logger.exception(f"Failed to batch insert: {e}")
        raise HTTPException(status_code=500, detail=str(e))
