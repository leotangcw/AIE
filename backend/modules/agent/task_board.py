"""任务看板服务 - 提供任务创建、更新、查询功能"""

import uuid
from datetime import datetime
from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import AsyncSessionLocal
from backend.models.task_item import TaskItem, TaskScope, TaskStatus


class TaskBoardService:
    """任务看板服务 - 用于与 Cron、Subagent、Workflow 等系统集成"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # 创建任务
    # =========================================================================

    async def create_task(
        self,
        title: str,
        task_scope: str,
        task_type: str,
        session_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        description: str = "",
        cron_id: Optional[str] = None,
        cron_expression: Optional[str] = None,
        estimated_duration: Optional[int] = None,
    ) -> TaskItem:
        """创建新任务"""
        task = TaskItem(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            task_scope=task_scope,
            session_id=session_id,
            task_type=task_type,
            parent_id=parent_id,
            cron_id=cron_id,
            cron_expression=cron_expression,
            estimated_duration=estimated_duration,
            status=TaskStatus.PENDING.value,
            progress=0,
        )

        if task_scope == TaskScope.SESSION.value:
            task.session_id = session_id

        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)

        logger.info(f"[TaskBoard] Created task: {task.id} - {title}")
        return task

    async def create_session_task(
        self,
        title: str,
        task_type: str,
        session_id: str,
        description: str = "",
        parent_id: Optional[str] = None,
        estimated_duration: Optional[int] = None,
    ) -> TaskItem:
        """创建会话级任务"""
        return await self.create_task(
            title=title,
            task_scope=TaskScope.SESSION.value,
            task_type=task_type,
            session_id=session_id,
            parent_id=parent_id,
            description=description,
            estimated_duration=estimated_duration,
        )

    async def create_system_task(
        self,
        title: str,
        task_type: str,
        cron_id: str,
        cron_expression: str,
        description: str = "",
    ) -> TaskItem:
        """创建系统级周期任务"""
        return await self.create_task(
            title=title,
            task_scope=TaskScope.SYSTEM.value,
            task_type=task_type,
            cron_id=cron_id,
            cron_expression=cron_expression,
            description=description,
        )

    # =========================================================================
    # 更新任务
    # =========================================================================

    async def update_status(
        self,
        task_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> Optional[TaskItem]:
        """更新任务状态"""
        task = await self.get_task(task_id)
        if not task:
            return None

        task.status = status

        if status == TaskStatus.RUNNING.value and not task.started_at:
            task.started_at = datetime.utcnow()

        if status == TaskStatus.DONE.value:
            task.completed_at = datetime.utcnow()
            if task.started_at:
                task.actual_duration = int(
                    (task.completed_at - task.started_at).total_seconds()
                )

        if status == TaskStatus.FAILED.value:
            task.retry_count += 1
            if error_message:
                task.error_message = error_message
            # 失败时重置进度，避免显示虚假的高进度值
            task.prev_progress = task.progress
            task.progress = 0

        await self.db.commit()
        await self.db.refresh(task)

        # 如果是子任务，更新父任务状态
        if task.parent_id:
            await self._update_parent_status(task.parent_id)

        return task

    async def update_progress(
        self,
        task_id: str,
        progress: int,
    ) -> Optional[TaskItem]:
        """更新任务进度"""
        task = await self.get_task(task_id)
        if not task:
            return None

        task.progress = min(100, max(0, progress))
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def update_monitoring_info(self, task_id: str, info_json: str):
        """更新任务的监控信息"""
        task = await self.get_task(task_id)
        if not task:
            return

        task.monitoring_info = info_json
        task.updated_at = datetime.utcnow()
        await self.db.commit()

    async def update_analysis(
        self,
        task_id: str,
        progress: int,
        last_analysis: str,
        analysis_history: list[dict],
        next_check_at,
        prev_progress: int,
        wake_count: int,
    ):
        """更新心跳分析结果"""
        import json
        result = await self.db.execute(
            select(TaskItem).where(TaskItem.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            return

        task.prev_progress = prev_progress
        task.progress = progress
        task.last_analysis = last_analysis
        task.analysis_history = json.dumps(analysis_history, ensure_ascii=False)
        task.next_check_at = next_check_at
        task.wake_count = wake_count
        task.updated_at = datetime.utcnow()
        await self.db.commit()

    async def start_task(self, task_id: str) -> Optional[TaskItem]:
        """开始任务"""
        return await self.update_status(task_id, TaskStatus.RUNNING.value)

    async def complete_task(self, task_id: str) -> Optional[TaskItem]:
        """完成任务"""
        return await self.update_status(task_id, TaskStatus.DONE.value)

    async def fail_task(
        self,
        task_id: str,
        error_message: str = "",
    ) -> Optional[TaskItem]:
        """标记任务失败"""
        return await self.update_status(
            task_id, TaskStatus.FAILED.value, error_message
        )

    async def cancel_task(self, task_id: str) -> Optional[TaskItem]:
        """取消任务"""
        return await self.update_status(task_id, TaskStatus.CANCELLED.value)

    # =========================================================================
    # 查询任务
    # =========================================================================

    async def get_task(self, task_id: str) -> Optional[TaskItem]:
        """获取任务"""
        result = await self.db.execute(
            select(TaskItem).where(TaskItem.id == task_id)
        )
        return result.scalar_one_or_none()

    async def get_session_tasks(
        self,
        session_id: str,
        include_subtasks: bool = True,
    ) -> list[TaskItem]:
        """获取会话所有任务"""
        result = await self.db.execute(
            select(TaskItem)
            .where(TaskItem.session_id == session_id)
            .order_by(TaskItem.created_at.desc())
        )
        tasks = list(result.scalars().all())

        if include_subtasks:
            return tasks
        else:
            # 只返回顶级任务
            return [t for t in tasks if t.parent_id is None]

    async def get_running_tasks(self) -> list[TaskItem]:
        """获取所有进行中的任务"""
        result = await self.db.execute(
            select(TaskItem)
            .where(TaskItem.status == TaskStatus.RUNNING.value)
            .order_by(TaskItem.started_at.asc())
        )
        tasks = result.scalars().all()
        return list(tasks) if tasks else []

    async def get_system_tasks(self) -> list[TaskItem]:
        """获取所有系统级任务"""
        result = await self.db.execute(
            select(TaskItem)
            .where(TaskItem.task_scope == TaskScope.SYSTEM.value)
            .order_by(TaskItem.next_run_at.asc().nullslast())
        )
        tasks = result.scalars().all()
        return list(tasks) if tasks else []

    async def get_child_tasks(self, parent_id: str) -> list[TaskItem]:
        """获取子任务"""
        result = await self.db.execute(
            select(TaskItem)
            .where(TaskItem.parent_id == parent_id)
            .order_by(TaskItem.created_at.asc())
        )
        tasks = result.scalars().all()
        return list(tasks) if tasks else []

    async def get_parent_tasks(self, session_id: str) -> list[TaskItem]:
        """获取会话的顶级任务"""
        result = await self.db.execute(
            select(TaskItem)
            .where(TaskItem.session_id == session_id)
            .where(TaskItem.parent_id.is_(None))
            .order_by(TaskItem.created_at.desc())
        )
        tasks = result.scalars().all()
        return list(tasks) if tasks else []

    # =========================================================================
    # 私有方法
    # =========================================================================

    async def _update_parent_status(self, parent_id: str):
        """更新父任务状态 - 基于子任务状态聚合"""
        parent = await self.get_task(parent_id)
        if not parent:
            return

        child_tasks = await self.get_child_tasks(parent_id)
        if not child_tasks:
            return

        # 状态聚合逻辑
        statuses = [t.status for t in child_tasks]

        if all(s == TaskStatus.DONE.value for s in statuses):
            new_status = TaskStatus.DONE.value
        elif any(s == TaskStatus.RUNNING.value for s in statuses):
            new_status = TaskStatus.RUNNING.value
        elif any(s == TaskStatus.FAILED.value for s in statuses):
            new_status = TaskStatus.FAILED.value
        elif all(s == TaskStatus.PENDING.value for s in statuses):
            new_status = TaskStatus.PENDING.value
        else:
            new_status = TaskStatus.RUNNING.value

        # 计算进度
        if child_tasks:
            avg_progress = sum(t.progress for t in child_tasks) // len(child_tasks)
            parent.progress = avg_progress

        parent.status = new_status

        if new_status == TaskStatus.DONE.value:
            parent.completed_at = datetime.utcnow()
            if parent.started_at:
                parent.actual_duration = int(
                    (parent.completed_at - parent.started_at).total_seconds()
                )

        await self.db.commit()
        await self.db.refresh(parent)

    # =========================================================================
    # 静态方法 - 供其他模块快速调用
    # =========================================================================

    @staticmethod
    async def quick_create_session_task(
        title: str,
        task_type: str,
        session_id: str,
    ) -> TaskItem:
        """快速创建会话任务"""
        async with AsyncSessionLocal() as db:
            service = TaskBoardService(db)
            return await service.create_session_task(
                title=title,
                task_type=task_type,
                session_id=session_id,
            )

    # =========================================================================
    # 任务进度刷新 - 使用模型主动检查
    # =========================================================================

    @staticmethod
    async def refresh_task_progress(task_id: str) -> dict:
        """
        获取任务当前状态（纯 DB 查询，不再调用 LLM）

        Returns:
            dict: {
                "task_id": str,
                "status": str,
                "progress": int,
                "description": str,
                "error_message": str | None,
            }
        """
        async with AsyncSessionLocal() as db:
            service = TaskBoardService(db)
            task = await service.get_task(task_id)

            if not task:
                return {"error": "Task not found"}

            return {
                "task_id": task.id,
                "status": task.status,
                "progress": task.progress,
                "description": task.description or "",
                "error_message": task.error_message,
            }

    @staticmethod
    async def quick_create_system_task(
        title: str,
        cron_id: str,
        cron_expression: str,
    ) -> TaskItem:
        """快速创建系统任务"""
        async with AsyncSessionLocal() as db:
            service = TaskBoardService(db)
            return await service.create_system_task(
                title=title,
                task_type="cron",  # 系统定时任务类型
                cron_id=cron_id,
                cron_expression=cron_expression,
            )


# =========================================================================
# 心跳服务 - 任务超时检测
# =========================================================================

class TaskHeartbeatService:
    """任务心跳服务 - 检测长时间运行的任务"""

    # 超时阈值倍数
    TIMEOUT_MULTIPLIER_WARNING = 1.5   # 超过预估时长1.5倍 → 警告
    TIMEOUT_MULTIPLIER_FAILED = 3.0     # 超过预估时长3倍 → 标记失败
    LONG_WAITING_THRESHOLD = 1800       # 30分钟无进展 → 长时间等待
    STUCK_FAILED_THRESHOLD = 3600       # 60分钟无进展 → 标记卡死/失败

    def __init__(self, db: AsyncSession):
        self.db = db

    async def scan_running_tasks(self) -> dict:
        """扫描进行中的任务，检测超时"""
        result = await self.db.execute(
            select(TaskItem)
            .where(TaskItem.status == TaskStatus.RUNNING.value)
            .where(TaskItem.started_at.isnot(None))
        )
        tasks = result.scalars().all()

        warnings = []
        timeouts = []

        now = datetime.utcnow()

        for task in tasks:
            if not task.started_at:
                continue

            estimated = task.estimated_duration
            # 跳过无时间限制的任务（如 long_running 类型，estimated_duration=0）
            if not estimated or estimated == 0:
                continue

            elapsed = (now - task.started_at).total_seconds()

            # 检测超时
            if elapsed > estimated * self.TIMEOUT_MULTIPLIER_FAILED:
                # 超过3倍预估时长 → 标记失败
                task.status = TaskStatus.FAILED.value
                task.error_message = f"任务执行超时 (已运行 {elapsed:.0f}秒，预估 {estimated}秒)"
                task.completed_at = now
                task.actual_duration = int(elapsed)
                timeouts.append(task.id)
                logger.warning(f"[TaskHeartbeat] Task {task.id} timed out after {elapsed:.0f}s")

            elif elapsed > estimated * self.TIMEOUT_MULTIPLIER_WARNING:
                # 超过1.5倍预估时长 → 记录警告
                warnings.append({
                    "task_id": task.id,
                    "title": task.title,
                    "elapsed": int(elapsed),
                    "estimated": estimated,
                })
                logger.info(f"[TaskHeartbeat] Task {task.id} running slow: {elapsed:.0f}s / {estimated}s")

        if timeouts or warnings:
            await self.db.commit()

        return {
            "warnings": warnings,
            "timeouts": timeouts,
        }

    async def check_long_waiting_tasks(self) -> list:
        """检测长时间等待（无进展）的任务，超时标记为卡死"""
        from datetime import timedelta

        # 使用 timedelta 计算阈值时间
        threshold_time = datetime.utcnow() - timedelta(seconds=self.LONG_WAITING_THRESHOLD)
        stuck_threshold_time = datetime.utcnow() - timedelta(seconds=self.STUCK_FAILED_THRESHOLD)

        result = await self.db.execute(
            select(TaskItem)
            .where(TaskItem.status == TaskStatus.RUNNING.value)
            .where(TaskItem.updated_at < threshold_time)
        )
        tasks = result.scalars().all()

        long_waiting = []
        now = datetime.utcnow()
        stuck_count = 0

        for task in tasks:
            if not task.updated_at:
                continue

            idle_seconds = (now - task.updated_at).total_seconds()
            if idle_seconds > self.STUCK_FAILED_THRESHOLD:
                # 超过卡死阈值 → 标记为失败
                task.status = TaskStatus.FAILED.value
                task.error_message = f"任务卡死（无进展 {idle_seconds/60:.0f} 分钟）"
                task.completed_at = now
                if task.started_at:
                    task.actual_duration = int(
                        (task.completed_at - task.started_at).total_seconds())
                stuck_count += 1
                logger.warning(f"[TaskHeartbeat] Task {task.id} stuck for {idle_seconds/60:.0f}min, marked as failed")
                long_waiting.append({
                    "task_id": task.id,
                    "title": task.title,
                    "idle_seconds": int(idle_seconds),
                    "stuck": True,
                })
            elif idle_seconds > self.LONG_WAITING_THRESHOLD:
                long_waiting.append({
                    "task_id": task.id,
                    "title": task.title,
                    "idle_seconds": int(idle_seconds),
                    "stuck": False,
                })

        if stuck_count > 0:
            await self.db.commit()

        return long_waiting

    async def cleanup_completed_tasks(self, hours: int = 24):
        """清理已完成的任务（归档）"""
        from datetime import timedelta

        threshold = datetime.utcnow() - timedelta(hours=hours)
        result = await self.db.execute(
            select(TaskItem)
            .where(TaskItem.status == TaskStatus.DONE.value)
            .where(TaskItem.completed_at < threshold)
        )
        tasks = result.scalars().all()

        # 将状态改为已归档 (使用 CANCELLED 作为标记)
        for task in tasks:
            task.status = "archived"

        if tasks:
            await self.db.commit()
            logger.info(f"[TaskHeartbeat] Archived {len(tasks)} completed tasks")

        return len(tasks)

    async def monitor_background_processes(self, subagent_manager) -> list:
        """检查所有运行中任务的后台进程状态"""
        import json
        import os

        results = []
        if not subagent_manager:
            return results

        for task in subagent_manager.tasks.values():
            if task.status not in ("running", "sleeping") or not task.monitoring_info:
                continue

            pid = task.monitoring_info.get("pid")
            if not pid:
                continue

            # 检查进程是否存活（通过 waitpid 获取退出码）
            exit_code = None
            alive = True
            try:
                pid_result = os.waitpid(pid, os.WNOHANG)
                if pid_result[0] != 0:  # 进程已退出 (返回值为退出进程的 pid)
                    exit_code = os.WEXITSTATUS(pid_result[1])
                    alive = False
            except ChildProcessError:
                alive = False
            except OSError:
                # PID 不存在或无权限
                alive = False

            # 更新 TaskBoard
            if task.task_board_item_id:
                task_item = await self.db.execute(
                    select(TaskItem).where(TaskItem.id == task.task_board_item_id)
                )
                task_item = task_item.scalar_one_or_none()
                if task_item:
                    if alive:
                        # 进程仍在运行
                        task_item.updated_at = datetime.utcnow()

                        # 基于日志文件大小变化检测卡死
                        log_file = task.monitoring_info.get("log_file")
                        stuck = False
                        if log_file and os.path.exists(log_file):
                            try:
                                current_size = os.path.getsize(log_file)
                                last_size = task.monitoring_info.get("last_size", 0)
                                task.monitoring_info["last_size"] = current_size

                                if last_size > 0 and current_size == last_size:
                                    no_change = task.monitoring_info.get("no_change_count", 0) + 1
                                    task.monitoring_info["no_change_count"] = no_change

                                    if no_change >= 6:  # 30分钟 (5分钟间隔 × 6次)
                                        stuck = True
                                        task_item.prev_progress = task_item.progress
                                        task_item.progress = 0
                                        task_item.status = TaskStatus.FAILED.value
                                        task_item.error_message = (
                                            f"后台进程卡死（日志文件30分钟无变化, 大小={current_size}字节）"
                                        )
                                        task.status = "failed"
                                        task.error = "后台进程卡死"
                                        logger.warning(
                                            f"[TaskHeartbeat] Task {task.task_id} "
                                            f"stuck: log unchanged for 30min"
                                        )
                                    else:
                                        task.monitoring_info["no_change_count"] = 0
                                else:
                                    task.monitoring_info["no_change_count"] = 0
                            except OSError:
                                pass

                        if not stuck:
                            # 估算进度（基于目标目录文件数或日志产出）
                            progress = self._estimate_progress_from_log(
                                task.monitoring_info
                            )
                            if progress is not None:
                                task_item.progress = min(99, progress)
                            results.append({
                                "task_id": task.task_id,
                                "status": "running",
                                "pid": pid,
                                "progress": progress,
                            })
                    else:
                        # 进程已退出，基于退出码判断成败
                        now = datetime.utcnow()
                        success = self._check_process_result(
                            task.monitoring_info.get("log_file"),
                            exit_code,
                        )
                        if success:
                            task_item.status = TaskStatus.DONE.value
                            task_item.progress = 100
                            task.status = "done"
                            task.progress = 100
                        else:
                            task_item.prev_progress = task_item.progress
                            task_item.progress = 0
                            task_item.status = TaskStatus.FAILED.value
                            task_item.error_message = (
                                f"后台进程退出 (exit_code={exit_code})"
                            )
                            task.status = "failed"
                            task.error = task_item.error_message
                        task_item.completed_at = now
                        if task_item.started_at:
                            task_item.actual_duration = int(
                                (task_item.completed_at - task_item.started_at).total_seconds())
                        results.append({
                            "task_id": task.task_id,
                            "status": task.status,
                            "pid": pid,
                            "exit_code": exit_code,
                        })
                        logger.info(
                            f"[TaskHeartbeat] Background process {pid} "
                            f"finished: {task.status}, exit_code={exit_code}"
                        )

                    # 同步更新 monitoring_info 到 DB（含卡死检测状态）
                    try:
                        task_item.monitoring_info = json.dumps(task.monitoring_info)
                    except Exception:
                        pass

        await self.db.commit()
        return results

    @staticmethod
    def _estimate_progress_from_log(monitoring_info: dict) -> int | None:
        """从目标目录文件数或日志文件估算进度"""
        import os

        if not monitoring_info:
            return None

        # 策略1: 基于目标目录中的文件数估算
        target_dir = monitoring_info.get("target_dir")
        if target_dir and os.path.isdir(target_dir):
            try:
                file_count = 0
                for entry in os.listdir(target_dir):
                    fp = os.path.join(target_dir, entry)
                    if os.path.isfile(fp):
                        file_count += 1
                if file_count > 0:
                    # 根据文件数给粗略进度（假设大模型有 20+ 文件）
                    return min(95, file_count * 5)
            except OSError:
                pass

        # 策略2: 日志文件有实际输出（进程在产出的最低信号）
        log_file = monitoring_info.get("log_file")
        if log_file and os.path.exists(log_file):
            try:
                size = os.path.getsize(log_file)
                if size > 100:
                    return 5  # 有进展但不精确
            except OSError:
                pass

        return None

    @staticmethod
    def _check_process_result(log_file: str = None, exit_code: int = None) -> bool:
        """检查进程退出结果，优先使用退出码"""
        import os

        # 退出码 0 = 成功
        if exit_code is not None:
            return exit_code == 0

        # 无法获取退出码时，回退到日志内容分析
        if not log_file or not os.path.exists(log_file):
            return False
        try:
            with open(log_file, 'r', errors='replace') as f:
                content = f.read()[-2000:]
            error_indicators = [
                "Error", "ERROR", "FAILED", "Exception",
                "Traceback", "Permission denied",
            ]
            errors = sum(1 for e in error_indicators if e in content)
            return errors < 2  # 少量错误不算失败（降低误判率）
        except Exception:
            return False


# =========================================================================
# 便捷函数
# =========================================================================

async def run_task_heartbeat(subagent_manager=None):
    """运行任务心跳检测 - 供 Cron 调用"""
    async with AsyncSessionLocal() as db:
        service = TaskHeartbeatService(db)

        # 扫描超时任务
        scan_result = await service.scan_running_tasks()

        # 监控后台进程
        process_results = []
        if subagent_manager:
            process_results = await service.monitor_background_processes(subagent_manager)

        # 检测长时间等待（含卡死处理）
        long_waiting = await service.check_long_waiting_tasks()

        # 清理已完成任务
        archived_count = await service.cleanup_completed_tasks()

        return {
            "scan_result": scan_result,
            "process_monitoring": process_results,
            "long_waiting": long_waiting,
            "archived": archived_count,
        }


# =========================================================================
# Task Heartbeat Cron Job 集成
# =========================================================================

# Task Heartbeat Job ID
TASK_HEARTBEAT_JOB_ID = "builtin:task_heartbeat"

# Task Heartbeat 默认 schedule: 每 5 分钟
TASK_HEARTBEAT_SCHEDULE = "*/5 * * * *"


async def ensure_task_heartbeat_job(db_session_factory):
    """确保内置 task_heartbeat cron job 存在（app 启动时调用）"""
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select
    from backend.models.cron_job import CronJob

    # 北京时区
    SHANGHAI_TZ = timezone(timedelta(hours=8))

    try:
        async with db_session_factory() as db:
            result = await db.execute(
                select(CronJob).where(CronJob.id == TASK_HEARTBEAT_JOB_ID)
            )
            existing = result.scalar_one_or_none()

            if existing:
                # 已存在，确保启用
                if not existing.enabled:
                    existing.enabled = True
                    existing.updated_at = datetime.now(SHANGHAI_TZ).replace(tzinfo=None)
                    from croniter import croniter
                    now_sh = datetime.now(SHANGHAI_TZ).replace(tzinfo=None)
                    existing.next_run = croniter(existing.schedule, now_sh).get_next(datetime)
                    await db.commit()
                return

            # 创建新的 job
            now_sh = datetime.now(SHANGHAI_TZ).replace(tzinfo=None)
            from croniter import croniter
            next_run = croniter(TASK_HEARTBEAT_SCHEDULE, now_sh).get_next(datetime)

            job = CronJob(
                id=TASK_HEARTBEAT_JOB_ID,
                name="任务心跳检测",
                schedule=TASK_HEARTBEAT_SCHEDULE,
                message="__task_heartbeat__",  # 特殊标记，executor 识别
                enabled=True,
                deliver_response=False,
                last_run=None,
                next_run=next_run,
                last_status=None,
                last_error=None,
                run_count=0,
                error_count=0,
                created_at=now_sh,
                updated_at=now_sh,
            )
            db.add(job)
            await db.commit()
            logger.info(f"[TaskHeartbeat] Created builtin cron job: {TASK_HEARTBEAT_JOB_ID}")

    except Exception as e:
        logger.warning(f"[TaskHeartbeat] Failed to ensure task heartbeat job: {e}")

