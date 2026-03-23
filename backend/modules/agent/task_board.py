"""任务看板服务 - 提供任务创建、更新、查询功能"""

import uuid
import json
import re
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
    async def refresh_task_progress(provider, workspace, task_id: str) -> dict:
        """
        使用模型主动检查任务真实进度

        这是一个独立的监控函数，会:
        1. 获取任务信息
        2. 让模型判断如何检查任务状态
        3. 根据模型的工具调用结果更新任务状态

        Returns:
            dict: {
                "task_id": str,
                "status": str,  # running/done/failed
                "progress": int,  # 0-100
                "description": str,  # 更新后的描述（包含进度信息）
                "error_message": str | None,
            }
        """
        from datetime import datetime
        from pathlib import Path

        async with AsyncSessionLocal() as db:
            service = TaskBoardService(db)
            task = await service.get_task(task_id)

            if not task:
                return {"error": "Task not found"}

            # 构建任务检查提示词
            task_info = f"""你需要检查以下任务的真实状态：

任务信息：
- 任务ID: {task.id}
- 任务名称: {task.title}
- 任务描述: {task.description or '无'}
- 任务类型: {task.task_type}
- 开始时间: {task.started_at.isoformat() if task.started_at else '未知'}
- 预估时长: {task.estimated_duration}秒 (如果知道)
- 当前状态: {task.status}

请使用适当的工具检查这个任务的真实状态：
1. 如果是下载任务 → 使用 ls、du 检查文件大小和数量
2. 如果是进程任务 → 使用 ps 检查进程是否还在运行
3. 如果是其他任务 → 根据任务描述判断应该检查什么

检查后返回：
- 任务是否还在运行
- 任务进度百分比（如果可以估算）
- 任何有用的状态信息

只返回JSON格式，不要其他内容："""

            # 创建临时上下文让模型检查
            try:
                # 简单的LLM调用来检查任务状态
                from backend.modules.tools.registry import ToolRegistry
                from backend.modules.tools.filesystem import ListDirTool
                from backend.modules.tools.shell import ExecTool

                # 准备工具 - allow_dangerous=True 允许执行命令
                tools = ToolRegistry()
                tools.register(ListDirTool(workspace))
                tools.register(ExecTool(
                    workspace=workspace,
                    timeout=60,
                    allow_dangerous=True,
                    restrict_to_workspace=True,
                ))

                # 构建消息
                messages = [
                    {"role": "system", "content": "你是一个任务状态检查助手，负责检查后台任务的真实进度。"},
                    {"role": "user", "content": task_info}
                ]

                # 调用模型
                tool_definitions = tools.get_definitions()

                response_chunks = []
                tool_calls_buffer = []

                async for chunk in provider.chat_stream(
                    messages=messages,
                    tools=tool_definitions,
                    model=provider.default_model,
                    temperature=0.3,
                    max_tokens=2000,
                ):
                    if chunk.is_content and chunk.content:
                        response_chunks.append(chunk.content)
                    if chunk.is_tool_call and chunk.tool_call:
                        tool_calls_buffer.append(chunk.tool_call)

                # 处理工具调用
                for tool_call in tool_calls_buffer:
                    result = await tools.execute(
                        tool_name=tool_call.name,
                        arguments=tool_call.arguments
                    )
                    messages.append({
                        "role": "assistant",
                        "tool_calls": [{
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.name,
                                "arguments": json.dumps(tool_call.arguments),
                            },
                        }],
                        "content": "".join(response_chunks) if response_chunks else ""
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.name,
                        "content": result,
                    })

                # 再次调用获取最终判断
                messages.append({
                    "role": "user",
                    "content": "基于以上检查结果，返回最终的任务状态判断。只需要返回JSON格式：{\"status\": \"running/done/failed\", \"progress\": 0-100, \"description\": \"进度描述\"}"
                })

                final_response = []
                async for chunk in provider.chat_stream(
                    messages=messages,
                    model=provider.default_model,
                    temperature=0.1,
                    max_tokens=500,
                ):
                    if chunk.is_content and chunk.content:
                        final_response.append(chunk.content)

                final_text = "".join(final_response)

                # 解析JSON响应
                try:
                    # 尝试提取JSON
                    json_match = re.search(r'\{[^}]+\}', final_text, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group())

                        # 获取模型判断的状态
                        new_status = result.get("status", "running")

                        # 更新任务状态 - 即使数据库是done，也要根据真实状态更新
                        # 如果模型判断还在运行，就改回running
                        if new_status == "running":
                            task.status = TaskStatus.RUNNING.value
                            # 清除完成时间
                            task.completed_at = None
                        elif new_status == "done":
                            task.status = TaskStatus.DONE.value
                            if not task.completed_at:
                                task.completed_at = datetime.utcnow()
                        elif new_status == "failed":
                            task.status = TaskStatus.FAILED.value
                            if not task.completed_at:
                                task.completed_at = datetime.utcnow()

                        # 更新进度
                        if result.get("progress"):
                            task.progress = min(100, max(0, result["progress"]))

                        # 更新描述 - 追加进度信息
                        if result.get("description"):
                            # 避免重复追加
                            if f"[进度更新:" not in (task.description or ""):
                                task.description = (task.description or "") + f"\n\n[进度更新: {result['description']}]"

                        await db.commit()
                        await db.refresh(task)

                        return {
                            "task_id": task.id,
                            "status": task.status,
                            "progress": task.progress,
                            "description": result.get("description", ""),
                        }
                except Exception as e:
                    logger.warning(f"Failed to parse model response: {e}, response: {final_text}")

                return {"error": "Failed to parse model response", "raw": final_text}

            except Exception as e:
                logger.exception(f"Error refreshing task {task_id}: {e}")
                return {"error": str(e)}

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

            elapsed = (now - task.started_at).total_seconds()
            estimated = task.estimated_duration or 300  # 默认5分钟

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
        """检测长时间等待（无进展）的任务"""
        from datetime import timedelta

        # 使用 timedelta 计算阈值时间
        threshold_time = datetime.utcnow() - timedelta(seconds=self.LONG_WAITING_THRESHOLD)

        result = await self.db.execute(
            select(TaskItem)
            .where(TaskItem.status == TaskStatus.RUNNING.value)
            .where(TaskItem.updated_at < threshold_time)
        )
        tasks = result.scalars().all()

        long_waiting = []
        now = datetime.utcnow()

        for task in tasks:
            if not task.updated_at:
                continue

            idle_seconds = (now - task.updated_at).total_seconds()
            if idle_seconds > self.LONG_WAITING_THRESHOLD:
                long_waiting.append({
                    "task_id": task.id,
                    "title": task.title,
                    "idle_seconds": int(idle_seconds),
                })

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


# =========================================================================
# 便捷函数
# =========================================================================

async def run_task_heartbeat():
    """运行任务心跳检测 - 供 Cron 调用"""
    async with AsyncSessionLocal() as db:
        service = TaskHeartbeatService(db)

        # 扫描超时任务
        scan_result = await service.scan_running_tasks()

        # 检测长时间等待
        long_waiting = await service.check_long_waiting_tasks()

        # 清理已完成任务
        archived_count = await service.cleanup_completed_tasks()

        return {
            "scan_result": scan_result,
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

