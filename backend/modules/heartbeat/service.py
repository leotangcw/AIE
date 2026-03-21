"""HeartbeatService - 心跳任务 CRUD 服务"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from croniter import croniter
from loguru import logger
from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.heartbeat.models import (
    HeartbeatTask,
    ScheduleType,
    TaskStatus,
    TaskType,
)


# 北京时区
SHANGHAI_TZ = timezone(timedelta(hours=8))

# 默认间隔
DEFAULT_INTERVAL_SECONDS = 1800  # 30 分钟


class HeartbeatService:
    """心跳任务服务 - 提供数据库 CRUD 操作"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_tasks(
        self,
        session_id: Optional[str] = None,
        enabled_only: bool = False,
    ) -> list[HeartbeatTask]:
        """获取心跳任务列表"""
        query = select(HeartbeatTask)

        if session_id:
            query = query.where(HeartbeatTask.session_id == session_id)

        if enabled_only:
            query = query.where(HeartbeatTask.enabled == True)  # noqa: E712

        query = query.order_by(HeartbeatTask.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_task(self, task_id: str) -> Optional[HeartbeatTask]:
        """获取单个心跳任务"""
        result = await self.db.execute(
            select(HeartbeatTask).where(HeartbeatTask.id == task_id)
        )
        return result.scalar_one_or_none()

    async def create_task(
        self,
        session_id: str,
        name: str,
        task_type: str,
        schedule_type: str = ScheduleType.INTERVAL,
        interval_seconds: Optional[float] = None,
        cron_expr: Optional[str] = None,
        active_hours: Optional[dict[str, Any]] = None,
        config: Optional[dict[str, Any]] = None,
        prompt_template: Optional[str] = None,
        enabled: bool = True,
    ) -> HeartbeatTask:
        """创建心跳任务"""
        task_id = str(uuid.uuid4())

        # 计算下次执行时间
        next_run = await self.calculate_next_run_from_params(
            schedule_type=schedule_type,
            interval_seconds=interval_seconds,
            cron_expr=cron_expr,
        )

        task = HeartbeatTask(
            id=task_id,
            session_id=session_id,
            name=name,
            task_type=task_type,
            schedule_type=schedule_type,
            interval_seconds=interval_seconds,
            cron_expr=cron_expr,
            active_hours=active_hours,
            config=config,
            prompt_template=prompt_template,
            status=TaskStatus.IDLE,
            next_run_at=next_run,
            enabled=enabled,
        )

        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)

        logger.info(f"Created heartbeat task: {task_id} ({name})")
        return task

    async def update_task(
        self,
        task_id: str,
        name: Optional[str] = None,
        schedule_type: Optional[str] = None,
        interval_seconds: Optional[float] = None,
        cron_expr: Optional[str] = None,
        active_hours: Optional[dict[str, Any]] = None,
        config: Optional[dict[str, Any]] = None,
        prompt_template: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> Optional[HeartbeatTask]:
        """更新心跳任务"""
        task = await self.get_task(task_id)
        if not task:
            return None

        if name is not None:
            task.name = name
        if schedule_type is not None:
            task.schedule_type = schedule_type
        if interval_seconds is not None:
            task.interval_seconds = interval_seconds
        if cron_expr is not None:
            task.cron_expr = cron_expr
        if active_hours is not None:
            task.active_hours = active_hours
        if config is not None:
            task.config = config
        if prompt_template is not None:
            task.prompt_template = prompt_template
        if enabled is not None:
            task.enabled = enabled
            if not enabled:
                task.status = TaskStatus.DISABLED

        # 重新计算下次执行时间
        if schedule_type or interval_seconds or cron_expr:
            task.next_run_at = await self.calculate_next_run(task)

        task.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(task)

        logger.info(f"Updated heartbeat task: {task_id}")
        return task

    async def delete_task(self, task_id: str) -> bool:
        """删除心跳任务"""
        result = await self.db.execute(
            delete(HeartbeatTask).where(HeartbeatTask.id == task_id)
        )
        await self.db.commit()
        deleted = result.rowcount > 0

        if deleted:
            logger.info(f"Deleted heartbeat task: {task_id}")

        return deleted

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        error: Optional[str] = None,
    ) -> Optional[HeartbeatTask]:
        """更新任务状态"""
        task = await self.get_task(task_id)
        if not task:
            return None

        task.status = status
        task.last_run_at = datetime.utcnow()
        if error:
            task.last_error = error

        task.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(task)

        return task

    async def update_task_result(
        self,
        task_id: str,
        status: str,
        result: dict[str, Any],
        error: Optional[str] = None,
    ) -> Optional[HeartbeatTask]:
        """更新任务执行结果"""
        task = await self.get_task(task_id)
        if not task:
            return None

        task.status = TaskStatus.IDLE if status != "failed" else TaskStatus.ERROR
        task.last_run_at = datetime.utcnow()
        task.last_result = result
        task.last_error = error

        task.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(task)

        return task

    async def update_next_run(
        self,
        task_id: str,
        next_run: Optional[datetime],
    ) -> Optional[HeartbeatTask]:
        """更新下次执行时间"""
        task = await self.get_task(task_id)
        if not task:
            return None

        task.next_run_at = next_run
        task.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(task)

        return task

    async def get_due_tasks(self) -> list[HeartbeatTask]:
        """获取当前应执行的任务"""
        now = datetime.utcnow()

        query = (
            select(HeartbeatTask)
            .where(HeartbeatTask.enabled == True)  # noqa: E712
            .where(HeartbeatTask.next_run_at <= now)
            .where(HeartbeatTask.status != TaskStatus.RUNNING)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_history(
        self,
        limit: int = 20,
        session_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """获取执行历史"""
        query = select(HeartbeatTask).order_by(HeartbeatTask.last_run_at.desc())

        if session_id:
            query = query.where(HeartbeatTask.session_id == session_id)

        query = query.limit(limit)
        result = await self.db.execute(query)
        tasks = result.scalars().all()

        history = []
        for task in tasks:
            if task.last_run_at:
                history.append(
                    {
                        "task_id": task.id,
                        "task_name": task.name,
                        "task_type": task.task_type,
                        "status": task.last_result.get("status") if task.last_result else None,
                        "preview": task.last_result.get("preview") if task.last_result else None,
                        "duration_ms": task.last_result.get("duration_ms") if task.last_result else None,
                        "last_run_at": task.last_run_at.isoformat() if task.last_run_at else None,
                        "last_error": task.last_error,
                    }
                )

        return history

    async def get_metrics(
        self,
        session_id: Optional[str] = None,
        workspace: Optional[Any] = None,
    ) -> dict[str, Any]:
        """获取当前指标"""
        from backend.models.message import Message

        # 获取用户最后一条消息时间
        session_idle_seconds = None
        query = select(func.max(Message.created_at)).where(Message.role == "user")
        if session_id:
            query = query.where(Message.session_id == session_id)
        result = await self.db.execute(query)
        last_msg_time = result.scalar()
        if last_msg_time:
            now_utc = datetime.now(timezone.utc)
            if last_msg_time.tzinfo is None:
                last_msg_time = last_msg_time.replace(tzinfo=timezone.utc)
            session_idle_seconds = (now_utc - last_msg_time).total_seconds()

        # 获取上下文长度（从消息历史估算）
        # 每个字符约等于 2 个 token，所以除以 2
        context_length = 0
        msg_query = select(Message.content)
        if session_id:
            msg_query = msg_query.where(Message.session_id == session_id)
        msg_result = await self.db.execute(msg_query)
        messages = msg_result.scalars().all()
        for msg in messages:
            if msg:
                context_length += len(msg)
        # 转换为近似 token 数
        context_length = context_length // 2

        # 获取 memory 大小
        memory_size = 0
        if workspace:
            memory_file = workspace / "memory" / "memory.md"
            if memory_file.exists():
                try:
                    memory_size = len(memory_file.read_text(encoding="utf-8"))
                except Exception:
                    pass

        return {
            "context_length": context_length,
            "context_limit": 200000,
            "memory_size": memory_size,
            "queue_depth": 0,
            "session_idle_seconds": round(session_idle_seconds, 1) if session_idle_seconds else None,
            "timestamp": datetime.now(SHANGHAI_TZ).isoformat(),
        }

    @staticmethod
    async def calculate_next_run(task: HeartbeatTask) -> Optional[datetime]:
        """计算下次执行时间"""
        return await HeartbeatService.calculate_next_run_from_params(
            schedule_type=task.schedule_type,
            interval_seconds=task.interval_seconds,
            cron_expr=task.cron_expr,
            last_run=task.last_run_at,
        )

    @staticmethod
    async def calculate_next_run_from_params(
        schedule_type: str,
        interval_seconds: Optional[float] = None,
        cron_expr: Optional[str] = None,
        last_run: Optional[datetime] = None,
    ) -> Optional[datetime]:
        """根据调度参数计算下次执行时间"""
        now = datetime.utcnow()

        if schedule_type == ScheduleType.INTERVAL:
            interval = interval_seconds or DEFAULT_INTERVAL_SECONDS
            if last_run:
                return last_run + timedelta(seconds=interval)
            return now + timedelta(seconds=interval)

        elif schedule_type == ScheduleType.CRON and cron_expr:
            try:
                tz = croniter(cron_expr, now).get_timezone()
                cron = croniter(cron_expr, now, tz=tz)
                if last_run:
                    # 找下一个不早于 last_run 的时间
                    next_time = cron.get_next()
                    while next_time.timestamp() <= last_run.timestamp():
                        next_time = cron.get_next()
                    return datetime.fromtimestamp(next_time, tz=tz).replace(tzinfo=None)
                return cron.get_next(datetime)
            except Exception as e:
                logger.warning(f"Invalid cron expr: {cron_expr} - {e}")
                return now + timedelta(seconds=DEFAULT_INTERVAL_SECONDS)

        return now + timedelta(seconds=DEFAULT_INTERVAL_SECONDS)

    async def create_default_tasks(self, session_id: str) -> list[HeartbeatTask]:
        """为新 session 创建默认任务"""
        tasks = []

        # HEALTH_CHECK 任务 - 每 30 分钟
        task = await self.create_task(
            session_id=session_id,
            name="健康检查",
            task_type=TaskType.HEALTH_CHECK,
            schedule_type=ScheduleType.INTERVAL,
            interval_seconds=1800,  # 30 分钟
            active_hours={"start": "08:00", "end": "22:00", "timezone": "Asia/Shanghai"},
            enabled=True,
        )
        tasks.append(task)

        # METRIC_COLLECT 任务 - 每 5 分钟
        task = await self.create_task(
            session_id=session_id,
            name="指标采集",
            task_type=TaskType.METRIC_COLLECT,
            schedule_type=ScheduleType.INTERVAL,
            interval_seconds=300,  # 5 分钟
            enabled=True,
        )
        tasks.append(task)

        return tasks
