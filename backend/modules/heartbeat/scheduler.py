"""HeartbeatScheduler - Gateway 级心跳调度器"""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from loguru import logger

from backend.modules.heartbeat.models import HeartbeatTask, TaskStatus
from backend.modules.heartbeat.service import HeartbeatService
from backend.modules.heartbeat.task_runner import HeartbeatTaskRunner

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from backend.modules.agent.loop import AgentLoop
    from backend.ws.connection import ConnectionManager


# 北京时区
SHANGHAI_TZ = timezone(timedelta(hours=8))

# Coalescing 窗口 (250ms)
COALESCE_WINDOW_MS = 250

# 重试延迟 (1s)
RETRY_DELAY_MS = 1000

# 默认间隔 (30 分钟)
DEFAULT_INTERVAL_SECONDS = 1800


@dataclass
class PendingWake:
    """待处理的唤醒请求"""

    task: HeartbeatTask
    reason: str  # interval | manual | retry
    requested_at: float


class HeartbeatScheduler:
    """
    Gateway 级心跳调度器

    特性：
    - 自管理的 asyncio sleep 循环，不依赖 CronExecutor
    - Per-session 任务调度
    - 支持 interval 和 cron 表达式
    - Coalescing: 250ms 窗口内合并同 session 同类型任务
    - 优先级: RETRY > INTERVAL > MANUAL
    - active_hours 检查（支持 timezone）
    """

    def __init__(
        self,
        db_session_factory: "async_sessionmaker",
        agent_loop: Optional["AgentLoop"] = None,
        connection_manager: Optional["ConnectionManager"] = None,
        workspace: Optional[Path] = None,
    ):
        self.db_session_factory = db_session_factory
        self.agent_loop = agent_loop
        self.connection_manager = connection_manager
        self.workspace = workspace or Path(".")

        self._running = False
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

        # Coalescing: 同 session 同类型任务的待处理唤醒
        self._pending_wakes: dict[str, PendingWake] = {}

        # 全局配置
        self._enabled = True
        self._default_interval = DEFAULT_INTERVAL_SECONDS

        self._task_runner: Optional[HeartbeatTaskRunner] = None

        logger.info("HeartbeatScheduler initialized")

    async def start(self):
        """启动调度器"""
        async with self._lock:
            if self._running:
                logger.warning("HeartbeatScheduler already running")
                return

            self._running = True
            self._task_runner = HeartbeatTaskRunner(
                db_session_factory=self.db_session_factory,
                agent_loop=self.agent_loop,
                connection_manager=self.connection_manager,
            )

            self._task = asyncio.create_task(self._run_loop())
            logger.info("HeartbeatScheduler started")

    async def stop(self):
        """停止调度器"""
        async with self._lock:
            if not self._running:
                return

            self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info("HeartbeatScheduler stopped")

    def is_running(self) -> bool:
        """检查调度器是否运行"""
        return self._running

    async def _run_loop(self):
        """主调度循环"""
        while self._running:
            try:
                # 获取最近需要执行的任务（只查一次）
                next_run, due_tasks = await self._get_next_wake_time_and_tasks()

                if next_run is None:
                    # 没有待执行任务，睡眠后重试
                    await asyncio.sleep(60)
                    continue

                delay = (next_run - datetime.utcnow()).total_seconds()

                if delay > 0:
                    # 睡眠直到下一个任务到期
                    # 但每分钟检查一次 pending wakes
                    sleep_time = min(delay, 60)
                    await asyncio.sleep(sleep_time)

                # 处理到期任务（已传入 tasks，避免重复查询）
                await self._process_due_tasks(due_tasks)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"HeartbeatScheduler loop error: {e}")
                await asyncio.sleep(10)

    async def _get_next_wake_time_and_tasks(self) -> tuple[Optional[datetime], list[HeartbeatTask]]:
        """获取下一个任务到期时间及当前到期任务列表"""
        async with self.db_session_factory() as db:
            service = HeartbeatService(db)
            due_tasks = await service.get_due_tasks()

            if due_tasks:
                next_run = min(t.next_run_at for t in due_tasks if t.next_run_at)
                return next_run, due_tasks

            # 无到期任务，获取最近一个待执行任务
            all_tasks = await service.get_tasks(enabled_only=True)
            if not all_tasks:
                return None, []

            next_tasks = [
                t for t in all_tasks if t.next_run_at and t.status != TaskStatus.RUNNING
            ]
            if not next_tasks:
                return None, []

            next_run = min(t.next_run_at for t in next_tasks)
            return next_run, []

    async def _process_due_tasks(self, tasks: list[HeartbeatTask]):
        """处理所有到期任务"""
        if not tasks:
            return

            # 按 session_id 分组，coalescing
            for task in tasks:
                key = f"{task.session_id}:{task.task_type}"
                if key in self._pending_wakes:
                    existing = self._pending_wakes[key]
                    # 保留更高优先级的
                    if self._higher_priority(task, existing.task):
                        self._pending_wakes[key] = PendingWake(
                            task=task, reason="interval", requested_at=time.time()
                        )
                else:
                    self._pending_wakes[key] = PendingWake(
                        task=task, reason="interval", requested_at=time.time()
                    )

            # 等待 coalescing 窗口（复制当前 keys，避免新条目被误删）
            pending_keys = list(self._pending_wakes.keys())
            await asyncio.sleep(COALESCE_WINDOW_MS / 1000)

            # 执行所有待处理任务（只处理等待期间存在的 key）
            for key in pending_keys:
                wake = self._pending_wakes.pop(key, None)
                if wake and self._running:
                    asyncio.create_task(
                        self._execute_task(wake.task, wake.reason)
                    )

    async def _execute_task(self, task: HeartbeatTask, reason: str):
        """执行单个任务"""
        if not self._task_runner:
            logger.error("Task runner not initialized")
            return

        try:
            # 检查 active_hours
            if not self._is_active_now(task.active_hours):
                logger.debug(
                    f"Task {task.name} skipped: outside active hours {task.active_hours}"
                )
                return

            await self._task_runner.execute(
                task=task,
                reason=reason,
                workspace=self.workspace,
            )

        except Exception as e:
            logger.error(f"Failed to execute task {task.id}: {e}")

    def _is_active_now(
        self,
        active_hours: dict | None,
        now: datetime | None = None,
    ) -> bool:
        """判断当前时间是否在 active_hours 窗口内"""
        if not active_hours:
            return True

        now = now or datetime.now(SHANGHAI_TZ)
        start_str = active_hours.get("start", "00:00")
        end_str = active_hours.get("end", "24:00")
        tz_str = active_hours.get("timezone", "Asia/Shanghai")

        try:
            import pytz

            tz = pytz.timezone(tz_str)
            now_local = now.astimezone(tz)
        except Exception:
            tz = pytz.timezone("Asia/Shanghai")
            now_local = now.astimezone(tz)

        # 解析 HH:MM
        try:
            start_h, start_m = map(int, start_str.split(":"))
            end_h, end_m = map(int, end_str.split(":"))
        except Exception:
            logger.warning(f"Invalid active_hours format: {active_hours}")
            return True

        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60 + end_m
        now_minutes = now_local.hour * 60 + now_local.minute

        if start_minutes <= end_minutes:
            # 普通区间：如 08:00-22:00
            return start_minutes <= now_minutes < end_minutes
        else:
            # 跨午夜区间：如 22:00-06:00
            return now_minutes >= start_minutes or now_minutes < end_minutes

    def _higher_priority(self, new_task: HeartbeatTask, existing_task: HeartbeatTask) -> bool:
        """判断新任务是否比已有任务优先级更高"""
        # RETRY > INTERVAL > MANUAL
        # 这里简化处理，新任务总是替换旧任务（因为新任务更新鲜）
        return new_task.next_run_at > existing_task.next_run_at

    async def request_heartbeat(
        self,
        session_id: str,
        task_type: str = "HEALTH_CHECK",
        reason: str = "manual",
    ):
        """请求立即执行心跳（用于外部触发）"""
        async with self.db_session_factory() as db:
            service = HeartbeatService(db)
            tasks = await service.get_tasks(session_id=session_id, enabled_only=True)

            matching = [t for t in tasks if t.task_type == task_type]
            if not matching:
                logger.warning(f"No {task_type} task found for session {session_id}")
                return

            for task in matching:
                key = f"{task.session_id}:{task.task_type}"
                self._pending_wakes[key] = PendingWake(
                    task=task, reason=reason, requested_at=time.time()
                )

    async def set_enabled(self, enabled: bool):
        """设置是否启用"""
        self._enabled = enabled
        logger.info(f"HeartbeatScheduler {'enabled' if enabled else 'disabled'}")

    async def set_default_interval(self, interval_seconds: float):
        """设置默认间隔"""
        self._default_interval = interval_seconds
