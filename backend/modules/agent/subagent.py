"""Subagent Manager - 子 Agent 管理（增强版）

支持两种任务执行模式：
- agent tasks: 完整 LLM agent loop（spawn），用于需要推理的复杂子任务
- tool tasks: 直接调用 API（视频生成、音乐生成），不需要 LLM，通过 progress_callback 上报进度
"""

import asyncio
import json
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, Callable
from collections import deque
from loguru import logger

from backend.modules.agent.subagent_types import SubagentType, SubagentDefaults
from backend.modules.agent.task_board import TaskBoardService
from backend.modules.tools.base import Tool


class SubagentTask:
    """子 Agent 任务"""

    def __init__(
        self,
        task_id: str,
        label: str,
        message: str,
        session_id: str | None = None,
        subagent_type: SubagentType = SubagentType.GENERAL,
        timeout: int = None,
        parent_task_id: str | None = None,
        executor: Callable | None = None,
        estimated_duration: int | None = None,
    ):
        self.task_id = task_id
        self.label = label
        self.message = message
        self.session_id = session_id
        self.subagent_type = subagent_type
        self.timeout = timeout if timeout is not None else SubagentDefaults.get_timeout(subagent_type)
        self.parent_task_id = parent_task_id

        # 状态使用字符串值: "pending", "running", "done", "failed", "cancelled"
        # 与 DB TaskStatus 枚举保持一致
        self.status = "pending"
        self.progress = 0
        self.result: str | None = None
        self.error: str | None = None
        self.created_at = datetime.now()
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None

        # 扩展字段
        self.tool_calls: list[dict] = []
        self.task_board_item_id: str | None = None
        self.events: list[dict] = deque(maxlen=100)

        # 重试机制
        self.retry_count = 0
        self.max_retries = 2

        # 后台进程监控信息
        self.monitoring_info: dict = {}  # {pid, log_file, work_dir, started_at}

        # 心跳分析
        self.last_analysis: str = ""
        self.analysis_history: list[dict] = []  # 最近5次分析记录（滑窗）
        self.next_check_at: Optional[datetime] = None
        self.check_interval: int = 120
        self.wake_count: int = 0
        self.prev_progress: int = 0

        # tool task 模式
        self.executor = executor  # async def executor(progress_callback, cancel_check) -> dict
        self.estimated_duration = estimated_duration

        # Workflow 模式扩展字段
        self.system_prompt: str | None = None      # 工作流指定的自定义系统提示词
        self.event_callback = None                  # 工作流事件回调 (async def(event, tool_name, data))
        self.enable_skills: bool = False            # 是否启用技能系统
        self.model_override: dict | None = None     # 模型覆盖配置
        self.cancel_token = None                    # 取消令牌

        # 结果投递追踪
        self._result_delivered = False

        # 通知处理器（由 execute_task 设置）
        self._notification_handler = None

    def add_event(self, event_type: str, details: dict = None):
        """添加任务事件"""
        event = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            "details": details or {},
        }
        self.events.append(event)

    def add_tool_call(self, tool_name: str, args: dict, result: str = None):
        """记录工具调用"""
        self.tool_calls.append({
            "tool": tool_name,
            "args": args,
            "result": result,
            "timestamp": datetime.now().isoformat(),
        })

    @property
    def duration(self) -> Optional[float]:
        """任务执行时长（秒）"""
        if self.started_at:
            end = self.completed_at or datetime.now()
            return (end - self.started_at).total_seconds()
        return None

    @property
    def metrics(self) -> dict:
        """任务指标"""
        return {
            "duration_seconds": self.duration,
            "tool_calls": len(self.tool_calls),
            "errors": 1 if self.error else 0,
            "output_length": len(self.result) if self.result else 0,
        }

    @property
    def is_tool_task(self) -> bool:
        """是否为 tool task 模式"""
        return self.executor is not None

    @property
    def is_completed(self) -> bool:
        """是否已完成（包括失败和取消）"""
        return self.status in ("done", "failed", "cancelled")

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "label": self.label,
            "message": self.message,
            "session_id": self.session_id,
            "subagent_type": self.subagent_type.value,
            "timeout": self.timeout,
            "status": self.status,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration": self.duration,
            "metrics": self.metrics,
            "tool_calls": self.tool_calls,
            "events": list(self.events),
            "is_tool_task": self.is_tool_task,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "monitoring_info": self.monitoring_info,
            "last_analysis": self.last_analysis,
            "analysis_history": self.analysis_history,
            "next_check_at": self.next_check_at.isoformat() if self.next_check_at else None,
            "check_interval": self.check_interval,
            "wake_count": self.wake_count,
            "prev_progress": self.prev_progress,
        }


class StartBackgroundTool(Tool):
    """启动后台进程的工具（仅供子代理内部使用）

    继承 Tool 基类以兼容 ToolRegistry.execute() 的 validate_params 调用。
    注意：Tool 基类的 name/description/parameters/execute 是抽象方法，
    需要用 @property 或直接定义为属性来满足接口。
    """

    def __init__(self, workspace):
        self.workspace = workspace
        self._current_task = None
        self._sync_fn = None

    @property
    def name(self) -> str:
        return "start_background"

    @property
    def description(self) -> str:
        return (
            "启动一个后台进程执行耗时命令（下载、编译等）。进程独立运行，不阻塞当前任务。"
            "返回PID和日志文件路径，心跳系统会自动监控进程状态。"
            "可选指定 target_dir 让心跳根据目标目录文件数估算进度。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的命令",
                },
                "work_dir": {
                    "type": "string",
                    "description": "工作目录（可选，默认为工作空间）",
                },
                "target_dir": {
                    "type": "string",
                    "description": "目标目录路径（可选，心跳根据此目录文件数估算进度）",
                },
            },
            "required": ["command"],
        }

    async def execute(self, **kwargs) -> str:
        import subprocess
        import os

        command = kwargs.get("command", "")
        work_dir = kwargs.get("work_dir")
        target_dir = kwargs.get("target_dir")

        if not command:
            return json.dumps({"success": False, "error": "command is required"}, ensure_ascii=False)

        # 日志文件放在 workspace/.logs/ 下（重启不丢失）
        logs_dir = os.path.join(str(self.workspace), ".logs")
        os.makedirs(logs_dir, exist_ok=True)
        log_file = os.path.join(logs_dir, f"aie_bg_{uuid.uuid4().hex[:8]}.log")
        cwd = work_dir or str(self.workspace)

        try:
            stdout_fh = open(log_file, 'w')
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=cwd,
                stdout=stdout_fh,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            stdout_fh.close()  # Popen 已继承 fd，可以关闭

            # 记录 monitoring_info 到当前任务
            info = {
                "pid": process.pid,
                "log_file": log_file,
                "work_dir": cwd,
                "target_dir": target_dir,
                "started_at": datetime.now().isoformat(),
                "last_size": 0,
                "no_change_count": 0,
            }

            if self._current_task and hasattr(self._current_task, 'monitoring_info'):
                self._current_task.monitoring_info = info
                # 同步到 DB TaskItem
                if self._sync_fn:
                    await self._sync_fn(self._current_task)

            logger.info(f"[StartBackground] Started process PID={process.pid}, log={log_file}, target_dir={target_dir}")
            return json.dumps({
                "success": True,
                "pid": process.pid,
                "log_file": log_file,
                "work_dir": cwd,
                "target_dir": target_dir,
            }, ensure_ascii=False)

        except Exception as e:
            logger.error(f"[StartBackground] Failed to start process: {e}")
            return json.dumps({
                "success": False,
                "error": str(e),
            }, ensure_ascii=False)


class SubagentManager:
    """
    子 Agent 管理器（增强版）

    管理后台任务的创建、执行、取消和状态查询。
    支持 agent tasks 和 tool tasks 两种模式。
    """

    def __init__(
        self,
        provider,
        workspace,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        global_timeout: int = 600,
        max_concurrent: int = 3,
        security_config=None,
    ):
        self.provider = provider
        self.workspace = workspace
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.global_timeout = global_timeout
        self.max_concurrent = max_concurrent
        self.security_config = security_config

        self.tasks: dict[str, SubagentTask] = {}
        self.running_tasks: dict[str, asyncio.Task] = {}

        # 并发控制
        self._semaphore = asyncio.Semaphore(max_concurrent)

        # TaskBoard 服务（可选，用于同步任务状态）
        self._task_board_service = None

        logger.debug("SubagentManager initialized")

    async def _get_task_board_service(self):
        """获取 TaskBoardService 实例（延迟初始化，每次创建新会话）"""
        try:
            from backend.database import AsyncSessionLocal
            from backend.modules.agent.task_board import TaskBoardService
            db = AsyncSessionLocal()
            return TaskBoardService(db)
        except Exception as e:
            logger.warning(f"Failed to initialize TaskBoardService: {e}")
            return None

    async def _sync_task_to_board(self, task: SubagentTask, action: str):
        """同步任务状态到任务看板"""
        try:
            task_service = await self._get_task_board_service()
            if task_service is None:
                return

            if action == "start":
                task_item = await task_service.create_session_task(
                    title=task.label,
                    task_type="subagent",
                    session_id=task.session_id,
                    description=task.message,
                    estimated_duration=task.timeout if task.timeout else task.estimated_duration,
                )
                task.task_board_item_id = task_item.id
                logger.info(f"[TaskBoard] Created task item: {task_item.id} for subagent: {task.task_id}")
                await task_service.start_task(task_item.id)
                logger.info(f"[TaskBoard] Started task: {task_item.id}")

            elif action == "progress" and task.task_board_item_id:
                await task_service.update_progress(
                    task.task_board_item_id,
                    progress=task.progress
                )

            elif action == "complete" and task.task_board_item_id:
                await task_service.complete_task(task.task_board_item_id)
                logger.info(f"[TaskBoard] Completed task: {task.task_board_item_id}")

            elif action == "cancel" and task.task_board_item_id:
                await task_service.cancel_task(task.task_board_item_id)
                logger.info(f"[TaskBoard] Cancelled task: {task.task_board_item_id}")

            elif action == "fail" and task.task_board_item_id:
                await task_service.fail_task(
                    task.task_board_item_id,
                    error_message=task.error or "Task failed"
                )
                logger.info(f"[TaskBoard] Failed task: {task.task_board_item_id}")

        except Exception as e:
            logger.warning(f"[TaskBoard] Failed to sync task {task.task_id}: {e}")

    async def _sync_monitoring_to_board(self, task: SubagentTask):
        """将 monitoring_info 同步到 TaskBoard DB"""
        if task.task_board_item_id and task.monitoring_info:
            try:
                task_service = await self._get_task_board_service()
                if task_service:
                    await task_service.update_monitoring_info(
                        task.task_board_item_id,
                        json.dumps(task.monitoring_info)
                    )
            except Exception as e:
                logger.warning(f"[TaskBoard] Failed to sync monitoring_info: {e}")

    def create_task(
        self,
        label: str,
        message: str,
        session_id: str | None = None,
        subagent_type: SubagentType = SubagentType.GENERAL,
        timeout: int = None,
        parent_task_id: str | None = None,
        max_retries: int = 2,
        system_prompt: str | None = None,
        event_callback=None,
        enable_skills: bool = False,
        model_override: dict | None = None,
        cancel_token=None,
    ) -> str:
        """创建新的 agent task"""
        task_id = str(uuid.uuid4())

        task = SubagentTask(
            task_id=task_id,
            label=label,
            message=message,
            session_id=session_id,
            subagent_type=subagent_type,
            timeout=timeout,
            parent_task_id=parent_task_id,
        )
        task.max_retries = max_retries
        task.system_prompt = system_prompt
        task.event_callback = event_callback
        task.enable_skills = enable_skills
        task.model_override = model_override
        task.cancel_token = cancel_token

        self.tasks[task_id] = task
        task.add_event("created", {"label": label, "type": subagent_type.value})
        logger.info(f"Created agent task {task_id}: {label} (type: {subagent_type.value})")

        return task_id

    def create_tool_task(
        self,
        label: str,
        executor: Callable,
        session_id: str | None = None,
        timeout: int = 600,
        estimated_duration: int | None = None,
    ) -> str:
        """创建新的 tool task（不需要 LLM，直接调用 API）

        Args:
            label: 任务标签
            executor: 异步执行器，签名: async def executor(progress_callback, cancel_check) -> dict
                      progress_callback: async def (progress: int, message: str)
                      cancel_check: callable() -> bool
                      返回 dict，包含 success, path, url, error 等字段
            session_id: 关联的会话 ID
            timeout: 超时时间（秒）
            estimated_duration: 预估时长（秒），用于 TaskBoard 显示

        Returns:
            str: 任务 ID
        """
        task_id = str(uuid.uuid4())

        task = SubagentTask(
            task_id=task_id,
            label=label,
            message=f"[tool task] {label}",
            session_id=session_id,
            timeout=timeout,
            executor=executor,
            estimated_duration=estimated_duration,
        )

        self.tasks[task_id] = task
        task.add_event("created", {"label": label, "mode": "tool"})
        logger.info(f"Created tool task {task_id}: {label}")

        return task_id

    async def recover_tasks(self):
        """从 DB 恢复未完成的 LONG_RUNNING 任务"""
        from backend.database import AsyncSessionLocal
        from backend.models.task_item import TaskItem
        from sqlalchemy import select
        from backend.ws.task_notifications import task_notification_manager

        db = AsyncSessionLocal()
        try:
            result = await db.execute(
                select(TaskItem).where(
                    TaskItem.status.in_(["running", "sleeping"])
                )
            )
            items = result.scalars().all()

            for item in items:
                task = SubagentTask(
                    task_id=item.id,
                    label=item.title,
                    message=item.description or "",
                    session_id=item.session_id,
                    subagent_type=SubagentType.LONG_RUNNING,
                )
                task.status = item.status.lower()  # normalize
                task.progress = item.progress
                task.started_at = item.started_at
                task.monitoring_info = json.loads(item.monitoring_info or "{}")
                task.last_analysis = item.last_analysis or ""
                task.analysis_history = json.loads(item.analysis_history or "[]")
                task.next_check_at = item.next_check_at
                task.wake_count = item.wake_count or 0
                task.prev_progress = item.prev_progress or 0
                task.task_board_item_id = item.id

                # 重建通知处理器
                handler = task_notification_manager.create_handler(task.task_id, task.label)
                task._notification_handler = handler

                self.tasks[task.task_id] = task
                logger.info(f"[Recovery] Recovered task {task.task_id} (status={task.status}, progress={task.progress}%)")
        except Exception as e:
            logger.error(f"[Recovery] Failed to recover tasks: {e}")
        finally:
            await db.close()

    async def execute_task(self, task_id: str) -> None:
        """执行后台任务（带并发控制）"""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        if task.status != "pending":
            logger.warning(f"Task {task_id} is not pending, current status: {task.status}")
            return

        async def _guarded_run():
            async with self._semaphore:
                await self._execute_task_inner(task)

        async_task = asyncio.create_task(_guarded_run())
        self.running_tasks[task_id] = async_task

    async def _execute_task_inner(self, task: SubagentTask) -> None:
        """任务执行核心逻辑（已在信号量保护内），支持失败重试"""
        original_message = task.message
        last_error = None

        for attempt in range(task.max_retries + 1):
            if attempt > 0:
                # 重试：重置状态，附加失败原因
                task.message = (
                    f"{original_message}\n\n"
                    f"--- 上次失败（第{attempt}次重试，共{task.max_retries}次）---\n"
                    f"失败原因: {last_error}\n请分析原因，换方法重试。"
                )
                task.retry_count = attempt
                task.error = None
                task.result = None
                task.progress = 0
                task.tool_calls = []
                logger.info(f"Retrying task {task.task_id}: attempt {attempt}/{task.max_retries}")

            task.status = "running"
            task.started_at = datetime.now()
            task.progress = 0

            logger.info(f"Starting task {task.task_id}: {task.label} (attempt {attempt + 1})")

            # 同步任务状态到任务看板（仅在首次创建，重试时复用已有 item）
            if attempt == 0:
                await self._sync_task_to_board(task, "start")

            # 创建通知处理器（仅首次创建）
            handler = None
            if attempt == 0:
                try:
                    from backend.ws.task_notifications import task_notification_manager
                    handler = task_notification_manager.create_handler(task.task_id, task.label)
                    await handler.notify_created()
                    task._notification_handler = handler
                except Exception as e:
                    logger.warning(f"Failed to create notification handler: {e}")
            else:
                handler = task._notification_handler

            # 带超时执行（timeout=0 表示无限制）
            try:
                timeout = task.timeout if task.timeout is not None else self.global_timeout
                if timeout > 0:
                    await asyncio.wait_for(
                        self._run_task(task, handler),
                        timeout=timeout
                    )
                else:
                    await self._run_task(task, handler)

                # 检查任务结果
                if task.status == "done":
                    break  # 成功，退出重试循环
                if task.status == "sleeping":
                    # 长时任务已启动后台进程，进入心跳监控，退出重试循环
                    break
                elif task.status == "failed":
                    last_error = task.error or "未知错误"
                    if attempt < task.max_retries:
                        await asyncio.sleep(5 * (attempt + 1))  # 递增等待
                        continue
                    # 达到重试上限，最终失败
                    task.completed_at = datetime.now()
                    await self._sync_task_to_board(task, "fail")
                else:
                    # 状态未设置（不应该发生）
                    task.status = "failed"
                    task.error = "任务执行异常：状态未正确设置"
                    last_error = task.error
                    task.completed_at = datetime.now()
                    await self._sync_task_to_board(task, "fail")
                    if attempt < task.max_retries:
                        await asyncio.sleep(5 * (attempt + 1))
                        continue

            except asyncio.TimeoutError:
                task.status = "failed"
                task.error = f"任务超时 ({task.timeout or self.global_timeout}s)"
                task.completed_at = datetime.now()
                await self._sync_task_to_board(task, "fail")
                last_error = task.error
                if attempt < task.max_retries:
                    await asyncio.sleep(5 * (attempt + 1))
                    continue

            except Exception as e:
                task.status = "failed"
                task.error = str(e)
                task.completed_at = datetime.now()
                await self._sync_task_to_board(task, "fail")
                last_error = task.error
                if attempt < task.max_retries:
                    await asyncio.sleep(5 * (attempt + 1))
                    continue

            finally:
                if task.task_id in self.running_tasks:
                    del self.running_tasks[task.task_id]

            break  # 非重试情况下退出循环

        # 恢复原始消息
        task.message = original_message

    async def _run_task(self, task: SubagentTask, handler=None) -> None:
        """运行任务的内部方法，根据模式分发"""
        if task.is_tool_task:
            await self._run_tool_task(task, handler)
        else:
            await self._run_agent_task(task, handler)

    async def _run_tool_task(self, task: SubagentTask, handler=None) -> None:
        """执行 tool task（无 LLM，直接调用 executor）"""
        try:
            # 构建 cancel_check 回调
            def cancel_check():
                return task.status == "cancelled"

            # 构建 progress_callback
            async def progress_callback(progress: int, message: str | None = None):
                task.progress = min(100, max(0, progress))
                if handler:
                    try:
                        await handler.notify_progress(task.progress, message=message)
                    except Exception:
                        pass
                # 同步到 TaskBoard
                if task.task_board_item_id:
                    await self._sync_task_to_board(task, "progress")

            # 执行 executor
            result = await task.executor(progress_callback, cancel_check)

            # 处理结果
            if isinstance(result, dict):
                success = result.get("success", False)
                if success:
                    task.result = json.dumps(result, ensure_ascii=False)
                    task.status = "done"
                    task.progress = 100
                    task.completed_at = datetime.now()
                    await self._sync_task_to_board(task, "complete")
                    if handler:
                        await handler.notify_complete(task.result)
                else:
                    error_msg = result.get("error", "Unknown error")
                    task.error = error_msg
                    task.status = "failed"
                    task.completed_at = datetime.now()
                    await self._sync_task_to_board(task, "fail")
                    if handler:
                        await handler.notify_failed(error_msg)
            else:
                # executor 返回了字符串
                task.result = str(result)
                task.status = "done"
                task.progress = 100
                task.completed_at = datetime.now()
                await self._sync_task_to_board(task, "complete")
                if handler:
                    await handler.notify_complete(task.result)

            logger.info(f"Tool task {task.task_id} completed: status={task.status}")

        except asyncio.CancelledError:
            task.status = "cancelled"
            task.completed_at = datetime.now()
            await self._sync_task_to_board(task, "cancel")
            if handler:
                await handler.notify_failed("任务被取消")
            raise

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.completed_at = datetime.now()
            logger.error(f"Tool task {task.task_id} failed: {e}")
            await self._sync_task_to_board(task, "fail")
            if handler:
                try:
                    await handler.notify_failed(str(e))
                except Exception:
                    pass

        finally:
            # 清理通知处理器
            if handler:
                try:
                    from backend.ws.task_notifications import task_notification_manager
                    task_notification_manager.remove_handler(task.task_id)
                except Exception:
                    pass

    async def _run_agent_task(self, task: SubagentTask, handler=None) -> None:
        """根据类型分发任务执行"""
        if task.subagent_type == SubagentType.LONG_RUNNING:
            await self._run_long_running_task(task, handler)
        else:
            await self._run_standard_agent_task(task, handler)

    async def _run_long_running_task(self, task: SubagentTask, handler=None) -> None:
        """长时任务：启动后台进程后转入 SLEEPING，由心跳接管"""
        try:
            from backend.modules.tools.registry import ToolRegistry
            from backend.modules.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
            from backend.modules.tools.shell import ExecTool

            system_prompt = self._build_subagent_prompt(task.message, SubagentType.LONG_RUNNING)
            tools = ToolRegistry()
            tools.register(ReadFileTool(self.workspace))
            tools.register(WriteFileTool(self.workspace))
            tools.register(EditFileTool(self.workspace))
            tools.register(ListDirTool(self.workspace))

            # ExecTool 权限
            if self.security_config:
                tools.register(ExecTool(
                    workspace=self.workspace,
                    timeout=self.security_config.command_timeout,
                    allow_dangerous=not self.security_config.dangerous_commands_blocked,
                    restrict_to_workspace=self.security_config.restrict_to_workspace,
                    max_output_length=self.security_config.max_output_length,
                    deny_patterns=self.security_config.custom_deny_patterns,
                    allow_patterns=(
                        self.security_config.custom_allow_patterns
                        if self.security_config.command_whitelist_enabled
                        else None
                    ),
                ))
            else:
                tools.register(ExecTool(workspace=self.workspace))

            # 注册 start_background 工具
            bg_tool = StartBackgroundTool(self.workspace)
            bg_tool._current_task = task
            bg_tool._sync_fn = self._sync_monitoring_to_board
            tools.register(bg_tool)

            try:
                from backend.modules.tools.web import WebSearchTool, WebFetchTool
                tools.register(WebSearchTool())
                tools.register(WebFetchTool())
            except ImportError:
                pass

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task.message},
            ]

            # 最多 5 轮迭代（准备 → 启动 → 确认），比之前的3轮更宽裕
            max_iterations = 5
            start_background_called = False

            for iteration in range(max_iterations):
                content_buffer = ""
                tool_calls_buffer = []

                # 如果还未调用 start_background，在迭代 3+ 前注入强制提醒
                if iteration >= 2 and not start_background_called:
                    reminder = (
                        f"[系统提醒 - 第{iteration + 1}轮] 你还没有调用 start_background！"
                        f"剩余轮次: {max_iterations - iteration}。"
                        f"现在必须立即调用 start_background 工具启动后台进程，"
                        f"不要再做准备工作了。"
                    )
                    messages.append({"role": "user", "content": reminder})
                    logger.info(f"[LongRunning] Injected reminder at iteration {iteration + 1} for task {task.task_id}")

                async for chunk in self.provider.chat_stream(
                    messages=messages,
                    tools=tools.get_definitions(),
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                ):
                    if chunk.is_content and chunk.content:
                        content_buffer += chunk.content
                    if chunk.is_tool_call and chunk.tool_call:
                        tool_calls_buffer.append(chunk.tool_call)

                if tool_calls_buffer:
                    tool_call_dicts = [
                        {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}}
                        for tc in tool_calls_buffer
                    ]
                    messages.append({"role": "assistant", "content": content_buffer or "", "tool_calls": tool_call_dicts})

                    for tc in tool_calls_buffer:
                        result = await tools.execute(tool_name=tc.name, arguments=tc.arguments)
                        messages.append({"role": "tool", "tool_call_id": tc.id, "name": tc.name, "content": result})
                        task.add_tool_call(tc.name, tc.arguments, result)

                        if tc.name == "start_background":
                            start_background_called = True
                            logger.info(f"[LongRunning] start_background called at iteration {iteration + 1}")
                else:
                    # LLM 没有调用任何工具，直接输出了文本
                    # 检查文本中是否有 [TASK_SUCCESS] 或 [TASK_FAILED]
                    if "[TASK_SUCCESS" in content_buffer or "[TASK_FAILED" in content_buffer:
                        break
                    # 否则如果没有工具调用也没有标记，继续下一轮（不要退出）
                    if not start_background_called:
                        messages.append({"role": "user", "content": "你没有调用任何工具。请调用 start_background 启动后台进程。"})
                        continue
                    break

                # 检查是否已启动后台进程
                if task.monitoring_info:
                    break

            # 检查是否成功启动
            if not task.monitoring_info:
                task.status = "failed"
                task.error = "子Agent未能启动后台进程"
                await self._sync_task_to_board(task, "fail")
                if handler:
                    await handler.notify_failed(task.error)
                return

            # 转入 sleeping 状态
            task.status = "sleeping"
            task.last_analysis = "任务已启动，等待首次心跳分析"
            task.next_check_at = datetime.utcnow() + timedelta(minutes=1)

            # 同步到 TaskBoard
            if not task.task_board_item_id:
                await self._sync_task_to_board(task, "start")
            await self._sync_monitoring_to_board(task)

            if handler:
                await handler.notify_progress(5, message="后台进程已启动，心跳监控中")

            logger.info(f"[LongRunning] Task {task.task_id} entered sleeping, pid={task.monitoring_info.get('pid')}")

        except asyncio.CancelledError:
            task.status = "cancelled"
            if handler:
                await handler.notify_failed("任务被取消")
            raise
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            await self._sync_task_to_board(task, "fail")
            if handler:
                await handler.notify_failed(str(e))
            logger.error(f"[LongRunning] Task {task.task_id} failed: {e}")

    async def _run_standard_agent_task(self, task: SubagentTask, handler=None) -> None:
        """执行 agent task（完整 LLM agent loop）"""
        try:
            # 构建子 Agent 专用的系统提示词
            if task.system_prompt:
                # 使用工作流指定的自定义系统提示词
                system_prompt = task.system_prompt
            else:
                system_prompt = self._build_subagent_prompt(task.message, task.subagent_type)

            # 构建消息列表
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task.message},
            ]

            # 构建工具注册表
            from backend.modules.tools.registry import ToolRegistry
            from backend.modules.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
            from backend.modules.tools.shell import ExecTool

            tools = ToolRegistry()
            tools.register(ReadFileTool(self.workspace))
            tools.register(WriteFileTool(self.workspace))
            tools.register(EditFileTool(self.workspace))
            tools.register(ListDirTool(self.workspace))

            # 从 security_config 读取权限，与主代理保持一致
            if self.security_config:
                exec_timeout = self.security_config.command_timeout
                exec_restrict = self.security_config.restrict_to_workspace
                exec_allow_dangerous = not self.security_config.dangerous_commands_blocked
                exec_max_output = self.security_config.max_output_length
                exec_deny_patterns = self.security_config.custom_deny_patterns
                exec_allow_patterns = (
                    self.security_config.custom_allow_patterns
                    if self.security_config.command_whitelist_enabled
                    else None
                )
            else:
                exec_timeout = 300
                exec_restrict = True
                exec_allow_dangerous = False
                exec_max_output = 10000
                exec_deny_patterns = None
                exec_allow_patterns = None

            tools.register(ExecTool(
                workspace=self.workspace,
                timeout=exec_timeout,
                allow_dangerous=exec_allow_dangerous,
                restrict_to_workspace=exec_restrict,
                max_output_length=exec_max_output,
                deny_patterns=exec_deny_patterns,
                allow_patterns=exec_allow_patterns,
            ))

            # 为 long_running 任务注册 start_background 工具
            if task.subagent_type == SubagentType.LONG_RUNNING:
                bg_tool = StartBackgroundTool(self.workspace)
                bg_tool._current_task = task
                bg_tool._sync_fn = self._sync_monitoring_to_board
                tools.register(bg_tool)

            try:
                from backend.modules.tools.web import WebSearchTool, WebFetchTool
                tools.register(WebSearchTool())
                tools.register(WebFetchTool())
            except ImportError:
                logger.warning("Web tools not available for subagent")

            # 收集响应
            response_chunks = []
            iteration = 0
            max_iterations = 50 if task.subagent_type == SubagentType.LONG_RUNNING else 15

            # 模型覆盖：工作流可指定使用不同的模型
            model = self.model
            if task.model_override:
                override_model = task.model_override.get("model")
                if override_model:
                    model = override_model

            # 取消检查函数
            def _is_cancelled():
                return bool(task.cancel_token and task.cancel_token.is_cancelled)

            while iteration < max_iterations:
                iteration += 1

                # 检查取消令牌
                if _is_cancelled():
                    raise asyncio.CancelledError("Task cancelled via cancel_token")

                tool_definitions = tools.get_definitions()

                content_buffer = ""
                tool_calls_buffer = []

                async for chunk in self.provider.chat_stream(
                    messages=messages,
                    tools=tool_definitions,
                    model=model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                ):
                    if chunk.is_content and chunk.content:
                        content_buffer += chunk.content
                        # 通过 event_callback 推送实时文本 chunk
                        if task.event_callback:
                            try:
                                await task.event_callback("chunk", "", chunk.content)
                            except Exception:
                                pass

                    if chunk.is_tool_call and chunk.tool_call:
                        tool_calls_buffer.append(chunk.tool_call)

                if content_buffer:
                    response_chunks.append(content_buffer)

                if tool_calls_buffer:
                    tool_call_dicts = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in tool_calls_buffer
                    ]
                    messages.append({
                        "role": "assistant",
                        "content": content_buffer or "",
                        "tool_calls": tool_call_dicts,
                    })

                    for tool_call in tool_calls_buffer:
                        # 通过 event_callback 通知工具调用开始
                        if task.event_callback:
                            try:
                                await task.event_callback("tool_call", tool_call.name, tool_call.arguments)
                            except Exception:
                                pass

                        result = await tools.execute(
                            tool_name=tool_call.name,
                            arguments=tool_call.arguments
                        )

                        # 通过 event_callback 通知工具调用结果
                        if task.event_callback:
                            try:
                                await task.event_callback("tool_result", tool_call.name, result)
                            except Exception:
                                pass

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.name,
                            "content": result,
                        })

                        # 记录工具调用
                        task.add_tool_call(
                            tool_call.name,
                            tool_call.arguments,
                            result,
                        )

                        task.progress = 5  # 固定值，实际进度由心跳监控驱动

                    # 通过 WebSocket 上报进度
                    if handler:
                        try:
                            last_tool_name = tool_calls_buffer[-1].name if tool_calls_buffer else "思考中"
                            await handler.notify_progress(task.progress, message=f"子代理: {last_tool_name}")
                        except Exception:
                            pass
                else:
                    break

            # 解析最终结果（成败判断）
            final_response = "".join(response_chunks)
            task.result = final_response

            if "[TASK_FAILED" in final_response:
                # 子代理明确标记失败
                match = re.search(r'\[TASK_FAILED:\s*(.+?)\]', final_response)
                error_msg = match.group(1).strip() if match else "子代理报告任务失败"
                task.status = "failed"
                task.error = error_msg
                task.completed_at = datetime.now()
                await self._sync_task_to_board(task, "fail")
                if handler:
                    await handler.notify_failed(error_msg)
                logger.info(f"Agent task {task.task_id} marked as failed by subagent: {error_msg}")
            else:
                # 后备检查：所有 exec 调用都失败且没有明确标记成功
                exec_calls = [tc for tc in task.tool_calls if tc.get("tool") == "exec"]
                if exec_calls:
                    exec_failures = [tc for tc in exec_calls if "Exit code:" in (tc.get("result") or "")]
                    if len(exec_failures) == len(exec_calls) and "[TASK_SUCCESS" not in final_response:
                        task.status = "failed"
                        task.error = "所有命令执行失败"
                        task.completed_at = datetime.now()
                        await self._sync_task_to_board(task, "fail")
                        if handler:
                            await handler.notify_failed(task.error)
                        logger.info(f"Agent task {task.task_id} failed: all exec commands failed")
                        return

                # 正常完成
                task.status = "done"
                task.progress = 100
                task.completed_at = datetime.now()
                await self._sync_task_to_board(task, "complete")
                if handler:
                    await handler.notify_complete(task.result)
                logger.info(f"Agent task {task.task_id} completed successfully")

        except asyncio.CancelledError:
            task.status = "cancelled"
            task.completed_at = datetime.now()
            logger.info(f"Agent task {task.task_id} was cancelled")
            await self._sync_task_to_board(task, "cancel")
            if handler:
                await handler.notify_failed("任务被取消")
            raise

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.completed_at = datetime.now()
            logger.error(f"Agent task {task.task_id} failed: {e}")
            await self._sync_task_to_board(task, "fail")
            if handler:
                try:
                    await handler.notify_failed(str(e))
                except Exception:
                    pass

        finally:
            if handler:
                try:
                    from backend.ws.task_notifications import task_notification_manager
                    task_notification_manager.remove_handler(task.task_id)
                except Exception:
                    pass

    def _build_subagent_prompt(self, task: str, subagent_type: SubagentType = SubagentType.GENERAL) -> str:
        """构建子 Agent 专用的系统提示词"""
        workspace_path = str(self.workspace.expanduser().resolve())

        # 获取类型专属的附加提示
        type_extra = ""
        if subagent_type == SubagentType.LONG_RUNNING:
            type_extra = """
## 长时任务指南（必须严格遵守）

### 工具使用规则
- **start_background** = 启动耗时命令（下载、编译、git clone等）。这是启动长时任务的唯一正确方式。
- **exec** = 只允许用于快速准备（ls、mkdir、rm、cat等几秒完成的命令）。绝对禁止用 exec 执行实际任务。

### 执行流程
1. 用 exec 做准备工作（检查目录、清理旧文件）—— 每个命令应在几秒内完成
2. 用 start_background 启动实际任务命令，指定 target_dir
3. 收到 start_background 返回的 {"success": true, "pid": ...} 后，标记 [TASK_SUCCESS]

### 禁止事项
- 禁止用 exec 执行下载、编译、克隆等耗时命令（会阻塞超时导致任务失败）
- 禁止忘记调用 start_background（这是最常见的失败原因）
"""

        return f"""# 子代理 (Subagent)

你是主代理创建的子代理，专门负责完成特定任务。

## 你的任务
{task}

## 工作规则
1. **专注任务**: 只完成分配的任务，不做其他事情
2. **简洁高效**: 最终响应会报告给主代理，保持简洁但信息完整
3. **不要闲聊**: 不要发起对话或承担额外任务
4. **彻底完成**: 确保任务完整完成，提供清晰的结果总结
5. **不要因错误就放弃**: 尝试其他方法解决问题

## 可用能力
- 读写工作空间文件
- 执行 Shell 命令
- 网络搜索和抓取网页
- 使用所有标准工具

## 限制
- 不能直接向用户发送消息（无 message 工具）
- 不能创建其他子代理（无 spawn 工具）
- 无法访问主代理的对话历史

## 工作空间
{workspace_path}

## 完成标准
任务完成后，你必须在回复最后一行标注结果：
- 成功：`[TASK_SUCCESS]`
- 失败：`[TASK_FAILED: 原因]`

规则：
- 不要因错误就放弃，尝试其他方法
- 长时命令用 start_background 启动，不要用 exec 阻塞等待
- 确实无法完成时说明原因并标记 [TASK_FAILED]
{type_extra}
任务完成后，提供清晰的总结：
- 完成了什么
- 发现了什么（如果是调查任务）
- 遇到的问题（如果有）
- 建议的后续步骤（如果需要）"""

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self.tasks.get(task_id)
        if not task:
            logger.warning(f"Cannot cancel task {task_id}: not found")
            return False

        if task.status != "running":
            logger.warning(f"Cannot cancel task {task_id}: not running")
            return False

        # 先标记状态为 cancelled，这样 executor 内的 cancel_check 能感知
        task.status = "cancelled"

        async_task = self.running_tasks.get(task_id)
        if async_task:
            async_task.cancel()
            logger.info(f"Cancelled task {task_id}")
            return True

        return False

    def get_task(self, task_id: str) -> SubagentTask | None:
        """获取任务信息"""
        return self.tasks.get(task_id)

    def get_task_result(self, task_id: str) -> str | None:
        """获取任务结果"""
        task = self.tasks.get(task_id)
        if task and task.status == "done":
            return task.result
        return None

    def get_session_tasks(self, session_id: str) -> list[SubagentTask]:
        """获取会话的所有任务"""
        return [t for t in self.tasks.values() if t.session_id == session_id]

    def get_completed_undelivered_tasks(self, session_id: str) -> list[SubagentTask]:
        """获取已完成但结果未被投递的任务"""
        return [
            t for t in self.tasks.values()
            if t.session_id == session_id
            and t.status == "done"
            and not t._result_delivered
        ]

    def list_tasks(
        self,
        status: str | None = None,
        session_id: str | None = None,
    ) -> list[SubagentTask]:
        """列出任务"""
        tasks = list(self.tasks.values())

        if status:
            tasks = [t for t in tasks if t.status == status]

        if session_id:
            tasks = [t for t in tasks if t.session_id == session_id]

        tasks.sort(key=lambda t: t.created_at, reverse=True)

        return tasks

    def get_running_tasks(self) -> list[SubagentTask]:
        """获取所有运行中的任务"""
        return self.list_tasks(status="running")

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        task = self.tasks.get(task_id)
        if not task:
            logger.warning(f"Cannot delete task {task_id}: not found")
            return False

        if task.status == "running":
            asyncio.create_task(self.cancel_task(task_id))

        del self.tasks[task_id]
        logger.info(f"Deleted task {task_id}")

        return True

    def get_running_count(self) -> int:
        """Return the number of currently running subagents."""
        return len(self.running_tasks)

    def register_notification_callback(self, callback) -> None:
        """注册通知回调函数（保留兼容性）"""
        pass

    async def _notify(self, task_id: str, event_type: str) -> None:
        """发送通知（保留兼容性）"""
        pass

    def get_stats(self) -> dict[str, int]:
        """获取任务统计信息"""
        return {
            "total": len(self.tasks),
            "pending": len([t for t in self.tasks.values() if t.status == "pending"]),
            "running": len([t for t in self.tasks.values() if t.status == "running"]),
            "completed": len([t for t in self.tasks.values() if t.status == "done"]),
            "failed": len([t for t in self.tasks.values() if t.status == "failed"]),
            "cancelled": len([t for t in self.tasks.values() if t.status == "cancelled"]),
        }

    async def cleanup_old_tasks(self, max_age_hours: int = 24) -> int:
        """清理旧任务"""
        from datetime import timedelta

        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        cleaned = 0

        for task_id, task in list(self.tasks.items()):
            if task.status in ("done", "failed", "cancelled"):
                if task.completed_at and task.completed_at < cutoff_time:
                    del self.tasks[task_id]
                    cleaned += 1

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} old tasks")

        return cleaned
