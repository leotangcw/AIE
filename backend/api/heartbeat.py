"""Heartbeat API 路由"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.modules.heartbeat.models import HeartbeatTask, TaskType, ScheduleType
from backend.modules.heartbeat.schemas import (
    ActiveHoursSchema,
    DeleteResponse,
    HeartbeatConfigResponse,
    HeartbeatConfigUpdate,
    HeartbeatMetricsResponse,
    HeartbeatTaskCreate,
    HeartbeatTaskResponse,
    HeartbeatTaskUpdate,
)
from backend.modules.heartbeat.service import HeartbeatService
from backend.modules.heartbeat.task_runner import HeartbeatTaskRunner

router = APIRouter(prefix="/api/heartbeat", tags=["heartbeat"])


def task_to_response(task: HeartbeatTask) -> HeartbeatTaskResponse:
    """将 HeartbeatTask 转换为响应模型"""
    return HeartbeatTaskResponse(
        id=task.id,
        session_id=task.session_id,
        name=task.name,
        task_type=task.task_type,
        schedule_type=task.schedule_type,
        interval_seconds=task.interval_seconds,
        cron_expr=task.cron_expr,
        active_hours=task.active_hours,
        config=task.config,
        prompt_template=task.prompt_template,
        status=task.status,
        last_run_at=task.last_run_at.isoformat() if task.last_run_at else None,
        last_result=task.last_result,
        last_error=task.last_error,
        next_run_at=task.next_run_at.isoformat() if task.next_run_at else None,
        enabled=task.enabled,
        created_at=task.created_at.isoformat() if task.created_at else None,
        updated_at=task.updated_at.isoformat() if task.updated_at else None,
    )


@router.get("/tasks", response_model=list[HeartbeatTaskResponse])
async def list_heartbeat_tasks(
    session_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> list[HeartbeatTaskResponse]:
    """获取心跳任务列表"""
    service = HeartbeatService(db)
    tasks = await service.get_tasks(session_id=session_id)
    return [task_to_response(t) for t in tasks]


@router.post("/tasks", response_model=HeartbeatTaskResponse)
async def create_heartbeat_task(
    request: HeartbeatTaskCreate,
    db: AsyncSession = Depends(get_db),
) -> HeartbeatTaskResponse:
    """创建新的心跳任务"""
    service = HeartbeatService(db)

    # 验证任务类型
    valid_types = [TaskType.HEALTH_CHECK, TaskType.METRIC_COLLECT, TaskType.SESSION_KEEPALIVE, TaskType.CUSTOM]
    if request.task_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid task_type: {request.task_type}. Must be one of {valid_types}",
        )

    # 验证调度类型
    if request.schedule_type not in [ScheduleType.INTERVAL, ScheduleType.CRON]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid schedule_type: {request.schedule_type}",
        )

    # interval 模式必须指定 interval_seconds
    if request.schedule_type == ScheduleType.INTERVAL and not request.interval_seconds:
        request.interval_seconds = 1800  # 默认 30 分钟

    # cron 模式必须指定 cron_expr
    if request.schedule_type == ScheduleType.CRON and not request.cron_expr:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="cron_expr is required for cron schedule_type",
        )

    # 处理 active_hours
    active_hours_dict = None
    if request.active_hours:
        active_hours_dict = {
            "start": request.active_hours.start,
            "end": request.active_hours.end,
            "timezone": request.active_hours.timezone,
        }

    task = await service.create_task(
        session_id=request.session_id,
        name=request.name,
        task_type=request.task_type,
        schedule_type=request.schedule_type,
        interval_seconds=request.interval_seconds,
        cron_expr=request.cron_expr,
        active_hours=active_hours_dict,
        config=request.config,
        prompt_template=request.prompt_template,
        enabled=request.enabled,
    )

    logger.info(f"Created heartbeat task: {task.id}")
    return task_to_response(task)


@router.delete("/tasks/{task_id}", response_model=DeleteResponse)
async def delete_heartbeat_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
) -> DeleteResponse:
    """删除心跳任务"""
    service = HeartbeatService(db)
    deleted = await service.delete_task(task_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )

    return DeleteResponse(success=True, message=f"Task {task_id} deleted")


@router.patch("/tasks/{task_id}", response_model=HeartbeatTaskResponse)
async def update_heartbeat_task(
    task_id: str,
    request: HeartbeatTaskUpdate,
    db: AsyncSession = Depends(get_db),
) -> HeartbeatTaskResponse:
    """更新心跳任务"""
    service = HeartbeatService(db)

    # 处理 active_hours
    active_hours_dict = None
    if request.active_hours is not None:
        active_hours_dict = {
            "start": request.active_hours.start,
            "end": request.active_hours.end,
            "timezone": request.active_hours.timezone,
        }

    task = await service.update_task(
        task_id=task_id,
        name=request.name,
        schedule_type=request.schedule_type,
        interval_seconds=request.interval_seconds,
        cron_expr=request.cron_expr,
        active_hours=active_hours_dict,
        config=request.config,
        prompt_template=request.prompt_template,
        enabled=request.enabled,
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )

    return task_to_response(task)


@router.post("/tasks/{task_id}/run")
async def run_heartbeat_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """立即执行一次心跳任务"""
    from backend.app import app

    service = HeartbeatService(db)
    task = await service.get_task(task_id)

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )

    # 获取 scheduler
    scheduler = getattr(app.state, "heartbeat_scheduler", None)
    if not scheduler:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Heartbeat scheduler not available",
        )

    # 直接执行
    runner = HeartbeatTaskRunner(
        db_session_factory=scheduler.db_session_factory,
        agent_loop=scheduler.agent_loop if hasattr(scheduler, "agent_loop") else None,
        connection_manager=scheduler.connection_manager if hasattr(scheduler, "connection_manager") else None,
    )

    workspace = getattr(app.state, "shared", {}).get("workspace", None) or Path(".")

    try:
        result = await runner.execute(
            task=task,
            reason="manual",
            workspace=workspace,
        )
        return {
            "success": True,
            "task_id": task_id,
            "status": result.status,
            "preview": result.preview,
            "error": result.error,
        }
    except Exception as e:
        logger.error(f"Failed to run task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/config", response_model=HeartbeatConfigResponse)
async def get_heartbeat_config():
    """获取全局心跳配置"""
    from backend.app import app

    scheduler = getattr(app.state, "heartbeat_scheduler", None)

    return HeartbeatConfigResponse(
        enabled=scheduler.is_running() if scheduler else False,
        interval_seconds=scheduler._default_interval if scheduler else 1800,
        active_hours=None,  # TODO: 从配置获取
    )


@router.put("/config", response_model=HeartbeatConfigResponse)
async def update_heartbeat_config(
    request: HeartbeatConfigUpdate,
):
    """更新全局心跳配置"""
    from backend.app import app

    scheduler = getattr(app.state, "heartbeat_scheduler", None)

    if not scheduler:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Heartbeat scheduler not available",
        )

    if request.enabled is not None:
        if request.enabled:
            await scheduler.start()
        else:
            await scheduler.stop()

    if request.interval_seconds is not None:
        await scheduler.set_default_interval(request.interval_seconds)

    return HeartbeatConfigResponse(
        enabled=scheduler.is_running(),
        interval_seconds=scheduler._default_interval,
        active_hours=None,
    )


@router.get("/history")
async def get_heartbeat_history(
    limit: int = 20,
    session_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """获取执行历史"""
    service = HeartbeatService(db)
    history = await service.get_history(limit=limit, session_id=session_id)
    return history


@router.get("/metrics", response_model=HeartbeatMetricsResponse)
async def get_heartbeat_metrics(
    session_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> HeartbeatMetricsResponse:
    """获取当前指标"""
    from backend.app import app

    service = HeartbeatService(db)
    workspace = getattr(app.state, "shared", {}).get("workspace", None)

    metrics = await service.get_metrics(session_id=session_id, workspace=workspace)

    return HeartbeatMetricsResponse(**metrics)


@router.post("/tasks/default")
async def create_default_tasks(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """为 session 创建默认任务"""
    service = HeartbeatService(db)
    tasks = await service.create_default_tasks(session_id=session_id)
    return {
        "success": True,
        "created": len(tasks),
        "tasks": [task_to_response(t) for t in tasks],
    }
