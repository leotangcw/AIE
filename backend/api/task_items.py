"""任务看板 API - 提供任务项查询接口"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.task_item import TaskItem, TaskScope, TaskStatus

router = APIRouter(prefix="/api/task-items", tags=["task-board"])


# ============================================================================
# Pydantic Schemas
# ============================================================================


class TaskItemResponse(BaseModel):
    """任务项响应"""
    id: str
    title: str
    description: Optional[str]
    task_scope: str
    session_id: Optional[str]
    task_type: str
    parent_id: Optional[str]
    cron_id: Optional[str]
    cron_expression: Optional[str]
    next_run_at: Optional[str]
    last_run_status: Optional[str]
    last_run_at: Optional[str]
    status: str
    progress: int
    started_at: Optional[str]
    completed_at: Optional[str]
    estimated_duration: Optional[int]
    actual_duration: Optional[int]
    error_message: Optional[str]
    retry_count: int
    max_retries: int
    created_at: Optional[str]
    updated_at: Optional[str]

    class Config:
        from_attributes = True


class TaskItemWithSubtasks(BaseModel):
    """带子任务的任务项"""
    id: str
    title: str
    description: Optional[str]
    task_scope: str
    session_id: Optional[str]
    task_type: str
    status: str
    progress: int
    started_at: Optional[str]
    completed_at: Optional[str]
    estimated_duration: Optional[int]
    actual_duration: Optional[int]
    error_message: Optional[str]
    sub_tasks: List[TaskItemResponse] = Field(default_factory=list)


class TaskBoardResponse(BaseModel):
    """任务看板响应"""
    system_tasks: List[TaskItemResponse] = Field(default_factory=list)
    running_tasks: List[TaskItemResponse] = Field(default_factory=list)
    done_tasks: List[TaskItemResponse] = Field(default_factory=list)


class TaskStatsResponse(BaseModel):
    """任务统计"""
    total: int
    pending: int
    running: int
    done: int
    failed: int


# ============================================================================
# Helpers
# ============================================================================


def _to_response(item: TaskItem) -> TaskItemResponse:
    """转换为响应模型"""
    return TaskItemResponse(**item.to_dict())


# ============================================================================
# Endpoints - System Level (周期任务)
# ============================================================================


@router.get("/system", response_model=List[TaskItemResponse])
async def get_system_tasks(
    status_filter: Optional[str] = Query(None, description="状态过滤，逗号分隔"),
    db: AsyncSession = Depends(get_db),
) -> List[TaskItemResponse]:
    """获取所有周期任务 (SYSTEM级别)"""
    try:
        query = select(TaskItem).where(TaskItem.task_scope == TaskScope.SYSTEM.value)

        if status_filter:
            statuses = [s.strip() for s in status_filter.split(",")]
            query = query.where(TaskItem.status.in_(statuses))

        query = query.order_by(TaskItem.next_run_at.asc().nullslast())
        result = await db.execute(query)
        tasks = result.scalars().all()

        return [_to_response(t) for t in tasks]
    except Exception as exc:
        logger.exception(f"Failed to get system tasks: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/system/stats", response_model=TaskStatsResponse)
async def get_system_stats(db: AsyncSession = Depends(get_db)) -> TaskStatsResponse:
    """获取周期任务统计"""
    try:
        # 统计各状态数量
        query = select(TaskItem).where(TaskItem.task_scope == TaskScope.SYSTEM.value)
        result = await db.execute(query)
        tasks = result.scalars().all()

        stats = {
            "total": len(tasks),
            "pending": sum(1 for t in tasks if t.status == TaskStatus.PENDING.value),
            "running": sum(1 for t in tasks if t.status == TaskStatus.RUNNING.value),
            "done": sum(1 for t in tasks if t.status == TaskStatus.DONE.value),
            "failed": sum(1 for t in tasks if t.status == TaskStatus.FAILED.value),
        }
        return TaskStatsResponse(**stats)
    except Exception as exc:
        logger.exception(f"Failed to get system stats: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================================================
# Endpoints - Session Level (用户任务)
# ============================================================================


@router.get("/session/{session_id}", response_model=TaskBoardResponse)
async def get_session_tasks(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> TaskBoardResponse:
    """获取会话任务看板"""
    try:
        # 1. 周期任务 (SYSTEM)
        sys_query = select(TaskItem).where(TaskItem.task_scope == TaskScope.SYSTEM.value)
        sys_result = await db.execute(sys_query)
        system_tasks = [_to_response(t) for t in sys_result.scalars().all()]

        # 2. 进行中的任务 (SESSION - PENDING/RUNNING)
        running_query = (
            select(TaskItem)
            .where(TaskItem.task_scope == TaskScope.SESSION.value)
            .where(TaskItem.session_id == session_id)
            .where(TaskItem.parent_id.is_(None))  # 只查顶级任务
            .where(TaskItem.status.in_([TaskStatus.PENDING.value, TaskStatus.RUNNING.value]))
            .order_by(TaskItem.created_at.desc())
        )
        running_result = await db.execute(running_query)
        running_tasks = [_to_response(t) for t in running_result.scalars().all()]

        # 3. 已完成任务 (SESSION - DONE)
        done_query = (
            select(TaskItem)
            .where(TaskItem.task_scope == TaskScope.SESSION.value)
            .where(TaskItem.session_id == session_id)
            .where(TaskItem.parent_id.is_(None))
            .where(TaskItem.status == TaskStatus.DONE.value)
            .order_by(TaskItem.completed_at.desc())
            .limit(20)  # 限制返回数量
        )
        done_result = await db.execute(done_query)
        done_tasks = [_to_response(t) for t in done_result.scalars().all()]

        return TaskBoardResponse(
            system_tasks=system_tasks,
            running_tasks=running_tasks,
            done_tasks=done_tasks,
        )
    except Exception as exc:
        logger.exception(f"Failed to get session tasks: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/session/{session_id}/running", response_model=List[TaskItemResponse])
async def get_session_running_tasks(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> List[TaskItemResponse]:
    """获取会话进行中的任务"""
    try:
        query = (
            select(TaskItem)
            .where(TaskItem.task_scope == TaskScope.SESSION.value)
            .where(TaskItem.session_id == session_id)
            .where(TaskItem.parent_id.is_(None))
            .where(TaskItem.status.in_([TaskStatus.PENDING.value, TaskStatus.RUNNING.value]))
            .order_by(TaskItem.created_at.desc())
        )
        result = await db.execute(query)
        tasks = result.scalars().all()
        return [_to_response(t) for t in tasks]
    except Exception as exc:
        logger.exception(f"Failed to get running tasks: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/session/{session_id}/done", response_model=List[TaskItemResponse])
async def get_session_done_tasks(
    session_id: str,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> List[TaskItemResponse]:
    """获取会话已完成的任务"""
    try:
        query = (
            select(TaskItem)
            .where(TaskItem.task_scope == TaskScope.SESSION.value)
            .where(TaskItem.session_id == session_id)
            .where(TaskItem.parent_id.is_(None))
            .where(TaskItem.status == TaskStatus.DONE.value)
            .order_by(TaskItem.completed_at.desc())
            .limit(limit)
        )
        result = await db.execute(query)
        tasks = result.scalars().all()
        return [_to_response(t) for t in tasks]
    except Exception as exc:
        logger.exception(f"Failed to get done tasks: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================================================
# Endpoints - 通用
# ============================================================================


@router.get("/{task_id}", response_model=TaskItemResponse)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
) -> TaskItemResponse:
    """获取任务详情"""
    result = await db.execute(select(TaskItem).where(TaskItem.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return _to_response(task)


@router.get("/{task_id}/subtasks", response_model=List[TaskItemResponse])
async def get_subtasks(
    task_id: str,
    db: AsyncSession = Depends(get_db),
) -> List[TaskItemResponse]:
    """获取子任务列表"""
    result = await db.execute(
        select(TaskItem)
        .where(TaskItem.parent_id == task_id)
        .order_by(TaskItem.created_at.asc())
    )
    tasks = result.scalars().all()
    return [_to_response(t) for t in tasks]


@router.get("/{task_id}/with-subtasks", response_model=TaskItemWithSubtasks)
async def get_task_with_subtasks(
    task_id: str,
    db: AsyncSession = Depends(get_db),
) -> TaskItemWithSubtasks:
    """获取任务详情(含子任务)"""
    # 获取主任务
    result = await db.execute(select(TaskItem).where(TaskItem.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    # 获取子任务
    subtasks_result = await db.execute(
        select(TaskItem)
        .where(TaskItem.parent_id == task_id)
        .order_by(TaskItem.created_at.asc())
    )
    sub_tasks = [_to_response(t) for t in subtasks_result.scalars().all()]

    return TaskItemWithSubtasks(
        id=task.id,
        title=task.title,
        description=task.description,
        task_scope=task.task_scope,
        session_id=task.session_id,
        task_type=task.task_type,
        status=task.status,
        progress=task.progress,
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        estimated_duration=task.estimated_duration,
        actual_duration=task.actual_duration,
        error_message=task.error_message,
        sub_tasks=sub_tasks,
    )


@router.get("/stats/{session_id}", response_model=TaskStatsResponse)
async def get_session_stats(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> TaskStatsResponse:
    """获取会话任务统计"""
    try:
        query = (
            select(TaskItem)
            .where(TaskItem.task_scope == TaskScope.SESSION.value)
            .where(TaskItem.session_id == session_id)
            .where(TaskItem.parent_id.is_(None))
        )
        result = await db.execute(query)
        tasks = result.scalars().all()

        return TaskStatsResponse(
            total=len(tasks),
            pending=sum(1 for t in tasks if t.status == TaskStatus.PENDING.value),
            running=sum(1 for t in tasks if t.status == TaskStatus.RUNNING.value),
            done=sum(1 for t in tasks if t.status == TaskStatus.DONE.value),
            failed=sum(1 for t in tasks if t.status == TaskStatus.FAILED.value),
        )
    except Exception as exc:
        logger.exception(f"Failed to get session stats: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{task_id}/refresh")
async def refresh_task_progress(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取任务当前状态（纯 DB 查询，不调用 LLM）"""
    from loguru import logger

    try:
        # 调用纯 DB 查询
        from backend.modules.agent.task_board import TaskBoardService
        result = await TaskBoardService.refresh_task_progress(task_id)
        return result

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to refresh task {task_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
