"""HeartbeatTaskRunner - 任务执行器"""

import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from loguru import logger

from backend.modules.heartbeat.models import HeartbeatTask, TaskStatus, TaskType
from backend.modules.heartbeat.tasks import (
    HEARTBEAT_OK,
    HeartbeatResult,
    get_task_handler,
)

if TYPE_CHECKING:
    from backend.modules.agent.loop import AgentLoop
    from backend.ws.connection import ConnectionManager


# 北京时区
SHANGHAI_TZ = timezone(timedelta(hours=8))


class HeartbeatTaskRunner:
    """心跳任务执行器 - 负责执行单个心跳任务"""

    def __init__(
        self,
        db_session_factory,
        agent_loop: Optional["AgentLoop"] = None,
        connection_manager: Optional["ConnectionManager"] = None,
    ):
        self.db_session_factory = db_session_factory
        self.agent_loop = agent_loop
        self.connection_manager = connection_manager

    async def execute(
        self,
        task: HeartbeatTask,
        reason: str = "interval",
        workspace: Optional[Path] = None,
    ) -> HeartbeatResult:
        """
        执行心跳任务

        Args:
            task: 心跳任务
            reason: 执行原因 (interval | manual | retry)
            workspace: 工作空间路径

        Returns:
            HeartbeatResult: 执行结果
        """
        from backend.modules.heartbeat.service import HeartbeatService

        start_time = time.monotonic()
        task_id = task.id

        # 更新任务状态为 running
        async with self.db_session_factory() as db:
            service = HeartbeatService(db)
            await service.update_task_status(task_id, TaskStatus.RUNNING)

        try:
            # 获取任务处理器
            handler = get_task_handler(task.task_type)
            if not handler:
                raise ValueError(f"Unknown task type: {task.task_type}")

            # 根据任务类型执行
            result = await self._dispatch_task(handler, task, workspace)

            duration_ms = (time.monotonic() - start_time) * 1000

            # 更新任务状态和结果
            async with self.db_session_factory() as db:
                service = HeartbeatService(db)
                await service.update_task_result(
                    task_id=task_id,
                    status=result.status,
                    result={
                        "status": result.status,
                        "preview": result.preview,
                        "duration_ms": round(duration_ms, 1),
                        "output": result.response,
                    },
                    error=result.error,
                )
                # 计算下次执行时间
                next_run = await service.calculate_next_run(task)
                await service.update_next_run(task_id, next_run)

            # 推送 WebSocket 事件
            await self._push_event(task, result, duration_ms, reason)

            logger.debug(
                f"Heartbeat task executed: {task.name} ({task_id}) - {result.status} in {duration_ms:.1f}ms"
            )

            return result

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            error_msg = str(e)
            logger.error(f"Heartbeat task failed: {task_id} - {error_msg}")

            # 更新任务状态为 error
            async with self.db_session_factory() as db:
                service = HeartbeatService(db)
                await service.update_task_status(task_id, TaskStatus.ERROR, error_msg)
                # 计算下次执行时间
                next_run = await service.calculate_next_run(task)
                await service.update_next_run(task_id, next_run)

            # 推送失败事件
            await self._push_event(
                task,
                HeartbeatResult(status="failed", error=error_msg),
                duration_ms,
                reason,
            )

            return HeartbeatResult(status="failed", error=error_msg)

    async def _dispatch_task(
        self,
        handler,
        task: HeartbeatTask,
        workspace: Optional[Path],
    ) -> HeartbeatResult:
        """分派任务到对应处理器"""
        task_type = task.task_type

        if task_type == TaskType.HEALTH_CHECK:
            return await handler.execute(
                workspace=workspace or Path("."),
                agent_loop=self.agent_loop,
                session_id=task.session_id,
            )

        elif task_type == TaskType.METRIC_COLLECT:
            # 从 agent_loop 获取真实 context_length
            context_len = 0
            if self.agent_loop and hasattr(self.agent_loop, 'get_context_length'):
                try:
                    context_len = self.agent_loop.get_context_length()
                except Exception:
                    pass
            return await handler.execute(
                workspace=workspace or Path("."),
                context_length=context_len,
                queue_stats={},
            )

        elif task_type == TaskType.SESSION_KEEPALIVE:
            return await handler.execute()

        elif task_type == TaskType.CUSTOM:
            return await handler.execute(
                prompt_template=task.prompt_template or "",
                workspace=workspace or Path("."),
                agent_loop=self.agent_loop,
                session_id=task.session_id,
            )

        else:
            return HeartbeatResult(
                status="failed",
                error=f"Unknown task type: {task_type}",
            )

    async def _push_event(
        self,
        task: HeartbeatTask,
        result: HeartbeatResult,
        duration_ms: float,
        reason: str,
    ):
        """推送 WebSocket 事件"""
        if not self.connection_manager:
            return

        from backend.modules.heartbeat.events import HeartbeatEvent

        # 确定 indicator 类型
        if result.status == "ok-empty":
            indicator_type = "ok"
        elif result.status == "ok":
            indicator_type = "alert"
        elif result.status == "failed":
            indicator_type = "error"
        else:
            indicator_type = None

        event = HeartbeatEvent(
            task_id=task.id,
            task_name=task.name,
            status=result.status,
            preview=result.preview,
            duration_ms=round(duration_ms, 1),
            ts=int(time.time()),
            reason=reason,
            indicator_type=indicator_type,
        )

        try:
            await self.connection_manager.send_to_session(task.session_id, event)
        except Exception as e:
            logger.warning(f"Failed to push heartbeat event: {e}")
