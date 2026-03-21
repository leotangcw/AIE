"""TodoToolkit - Session级别的轻量级待办事项工具包

供 LLM Agent 调用的待办事项工具，实现 JiuWenClaw 风格的 todo 管理。
任务通过 TaskBoardService 持久化到数据库，并通过 WebSocket 实时推送更新。
"""

import asyncio
import threading
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from loguru import logger

from backend.database import AsyncSessionLocal
from backend.models.task_item import TaskItem, TaskScope, TaskStatus
from backend.modules.agent.task_board import TaskBoardService


class TodoStatus(str, Enum):
    """Todo 状态枚举"""
    WAITING = "waiting"      # 待执行
    RUNNING = "running"      # 执行中
    COMPLETED = "completed"  # 已完成
    CANCELLED = "cancelled"  # 已取消


# 前端 TodoItem 格式
class FrontendTodoItem:
    """前端 TodoList 组件使用的数据格式"""
    def __init__(
        self,
        id: str,
        content: str,
        activeForm: str = "",
        status: str = "pending",
        createdAt: str = "",
        updatedAt: str = "",
    ):
        self.id = id
        self.content = content
        self.activeForm = activeForm
        self.status = status
        self.createdAt = createdAt
        self.updatedAt = updatedAt

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "activeForm": self.activeForm,
            "status": self.status,
            "createdAt": self.createdAt,
            "updatedAt": self.updatedAt,
        }


class TodoToolkit:
    """Session 级别的待办事项工具包

    提供 5 个 LLM 可调用的工具:
    - todo_create: 创建新的待办列表
    - todo_complete: 标记任务为已完成
    - todo_insert: 插入新任务到列表
    - todo_remove: 删除任务
    - todo_list: 列出所有任务

    状态映射 (后端 -> 前端):
    - waiting -> pending
    - running -> in_progress
    - completed -> completed
    - cancelled -> pending (取消的任务显示在 pending)
    """

    # 工具名称集合，用于检测是否调用了 todo 工具
    TOOL_NAMES = frozenset([
        "todo_create",
        "todo_complete",
        "todo_insert",
        "todo_remove",
        "todo_clear",
        "todo_list",
    ])

    def __init__(self, session_id: str, db: Optional[Any] = None):
        """初始化 TodoToolkit

        Args:
            session_id: 会话 ID
            db: 可选的数据库会话
        """
        self.session_id = session_id
        self._db = db
        self._lock = threading.Lock()

        # 状态映射
        self._status_map = {
            "waiting": "pending",
            "running": "in_progress",
            "completed": "completed",
            "cancelled": "pending",
        }
        self._reverse_status_map = {
            "pending": TodoStatus.WAITING,
            "in_progress": TodoStatus.RUNNING,
            "completed": TodoStatus.COMPLETED,
        }

    async def _get_db(self):
        """获取数据库会话"""
        if self._db is not None:
            return self._db
        return AsyncSessionLocal()

    async def _get_task_board(self, db) -> TaskBoardService:
        """获取 TaskBoardService 实例"""
        return TaskBoardService(db)

    def _task_to_frontend(self, task: TaskItem) -> FrontendTodoItem:
        """将 TaskItem 转换为前端格式"""
        # 状态映射
        backend_status = task.status.lower() if task.status else "pending"
        if backend_status == "done":
            backend_status = "completed"
        elif backend_status == "failed":
            backend_status = "pending"

        frontend_status = self._status_map.get(backend_status, "pending")

        # 时间格式化
        created_at = task.created_at.isoformat() if task.created_at else ""
        updated_at = task.updated_at.isoformat() if task.updated_at else ""

        return FrontendTodoItem(
            id=task.id,
            content=task.title,  # 使用 title 作为 content
            activeForm="",  # TodoToolkit 不追踪 activeForm
            status=frontend_status,
            createdAt=created_at,
            updatedAt=updated_at,
        )

    async def _load_tasks(self) -> list[TaskItem]:
        """从数据库加载当前会话的所有 Todo 任务

        Todo 任务通过 parent_id 关联到主 todo list
        主 todo list 没有 parent_id
        """
        db = await self._get_db()
        async with db:
            task_board = await self._get_task_board(db)

            # 获取会话的所有顶级任务 (todo list)
            parent_tasks = await task_board.get_parent_tasks(self.session_id)

            # 找出所有 todo list (通过 description 识别)
            todo_lists = [t for t in parent_tasks if "LLM 管理的 Todo 列表" in (t.description or "")]

            if not todo_lists:
                return []

            # 返回最新的 todo list 的子任务
            latest_todo_list = todo_lists[0]
            children = await task_board.get_child_tasks(latest_todo_list.id)
            return children

    async def _get_todo_list_parent(self) -> Optional[TaskItem]:
        """获取当前会话的 Todo List 父任务"""
        db = await self._get_db()
        async with db:
            task_board = await self._get_task_board(db)
            parent_tasks = await task_board.get_parent_tasks(self.session_id)
            todo_lists = [t for t in parent_tasks if "LLM 管理的 Todo 列表" in (t.description or "")]
            return todo_lists[0] if todo_lists else None

    async def _save_tasks(self, tasks: list[TaskItem]) -> None:
        """保存任务列表到数据库 (简化版本，直接更新)"""
        db = await self._get_db()
        async with db:
            for task in tasks:
                db.add(task)
            await db.commit()

    async def _emit_todo_updated(self, tasks: list[TaskItem]) -> None:
        """广播 todo.updated 事件到 WebSocket

        Args:
            tasks: 当前所有任务
        """
        try:
            frontend_tasks = [self._task_to_frontend(t).to_dict() for t in tasks]

            # 构建 WebSocket 消息
            from backend.ws.task_notifications import ServerMessage
            from backend.ws.connection import connection_manager
            from pydantic import Field

            class TodoUpdatedMessage(ServerMessage):
                type: str = "todo.updated"
                todos: list = Field(default_factory=list)
                session_id: str = ""

            msg = TodoUpdatedMessage(
                todos=frontend_tasks,
                session_id=self.session_id,
            )

            await connection_manager.send_to_session(self.session_id, msg)
            logger.debug(f"[TodoToolkit] Emitted todo.updated with {len(tasks)} tasks")
        except Exception as e:
            logger.warning(f"[TodoToolkit] Failed to emit todo.updated: {e}")

    # =========================================================================
    # Tool Implementations
    # =========================================================================

    async def todo_create(self, tasks: list[str]) -> str:
        """创建新的待办列表

        如果已存在待办列表，返回错误。

        Args:
            tasks: 任务描述列表

        Returns:
            str: 操作结果
        """
        db = await self._get_db()
        async with db:
            # 检查是否已存在 todo list
            existing = await self._get_todo_list_parent()
            if existing:
                return f"错误：待办列表已存在。如需添加新任务，请使用 todo_insert。"

            task_board = await self._get_task_board(db)

            # 创建父任务 (todo list)
            now = datetime.utcnow()
            parent_task = await task_board.create_session_task(
                title="Todo List",
                task_type="todo",
                session_id=self.session_id,
                description="LLM 管理的 Todo 列表",
            )

            # 为每个任务创建子任务
            created_tasks = []
            for idx, task_desc in enumerate(tasks, 1):
                task = await task_board.create_session_task(
                    title=f"{idx}. {task_desc[:100]}",
                    task_type="todo",
                    session_id=self.session_id,
                    description=task_desc,
                    parent_id=parent_task.id,
                )
                created_tasks.append(task)

            # 加载所有任务用于广播 - 清除缓存确保拿到最新数据
            task_board.db.expire_all()  # 同步方法
            all_tasks = await task_board.get_child_tasks(parent_task.id)

            # 广播更新
            await self._emit_todo_updated(all_tasks)

            return f"已创建 {len(tasks)} 个待办任务"

    async def todo_complete(self, idx: int, result: str = "done") -> str:
        """标记任务为已完成

        Args:
            idx: 任务编号 (从 1 开始)
            result: 完成结果

        Returns:
            str: 操作结果
        """
        db = await self._get_db()
        async with db:
            tasks = await self._load_tasks()
            if not tasks:
                return "错误：没有待办列表"

            # 找到对应编号的任务
            target_task = None
            for task in tasks:
                # title 格式为 "1. task description"
                if task.title.startswith(f"{idx}. "):
                    target_task = task
                    break

            if not target_task:
                return f"错误：任务编号 {idx} 不存在"

            if target_task.status in (TaskStatus.COMPLETED.value, TaskStatus.CANCELLED.value):
                return f"错误：任务 {idx} 已处于 {target_task.status} 状态"

            # 标记为完成
            task_board = await self._get_task_board(db)
            await task_board.complete_task(target_task.id)

            # 重新加载任务 - 清除缓存确保拿到最新数据
            task_board.db.expire_all()  # 同步方法
            parent = await self._get_todo_list_parent()
            all_tasks = await task_board.get_child_tasks(parent.id) if parent else []

            # 广播更新
            await self._emit_todo_updated(all_tasks)

            return f"任务 {idx} 已标记为完成"

    async def todo_insert(self, idx: int, tasks: list[str]) -> str:
        """插入新任务到列表

        Args:
            idx: 插入位置 (从 1 开始，0 表示追加到末尾)
            tasks: 要插入的任务描述列表

        Returns:
            str: 操作结果
        """
        db = await self._get_db()
        async with db:
            task_board = await self._get_task_board(db)

            # 获取现有的 todo list
            parent = await self._get_todo_list_parent()
            if not parent:
                # 如果没有 todo list，直接创建
                return await self.todo_create(tasks)

            existing_tasks = await task_board.get_child_tasks(parent.id)

            # 解析现有任务的编号
            task_map = {}
            for t in existing_tasks:
                parts = t.title.split(". ", 1)
                if len(parts) == 2:
                    try:
                        num = int(parts[0])
                        task_map[num] = t
                    except ValueError:
                        pass

            max_idx = max(task_map.keys()) if task_map else 0

            # 确定插入位置
            if idx <= 0:
                insert_pos = max_idx + 1
            else:
                insert_pos = idx

            # 插入新任务
            inserted = []
            for i, task_desc in enumerate(tasks):
                new_idx = insert_pos + i
                task = await task_board.create_session_task(
                    title=f"{new_idx}. {task_desc[:100]}",
                    task_type="todo",
                    session_id=self.session_id,
                    description=task_desc,
                    parent_id=parent.id,
                )
                inserted.append(task)

            # 重新编号插入位置之后的任务
            for num in sorted(task_map.keys()):
                if num >= insert_pos:
                    old_task = task_map[num]
                    new_num = num + len(tasks)
                    old_task.title = f"{new_num}. {old_task.title.split('. ', 1)[1]}"

            # 统一提交所有更改
            await task_board.db.commit()

            # 重新加载所有任务 - 清除缓存确保拿到最新数据
            task_board.db.expire_all()  # 同步方法
            all_tasks = await task_board.get_child_tasks(parent.id)
            all_tasks.sort(key=lambda t: int(t.title.split(".")[0]) if "." in t.title else 0)

            # 广播更新
            await self._emit_todo_updated(all_tasks)

            return f"已插入 {len(tasks)} 个任务到位置 {insert_pos}"

    async def todo_remove(self, idx: int) -> str:
        """删除任务

        Args:
            idx: 任务编号 (从 1 开始)

        Returns:
            str: 操作结果
        """
        db = await self._get_db()
        async with db:
            task_board = await self._get_task_board(db)

            tasks = await self._load_tasks()
            if not tasks:
                return "错误：没有待办列表"

            # 找到对应编号的任务
            target_task = None
            for task in tasks:
                if task.title.startswith(f"{idx}. "):
                    target_task = task
                    break

            if not target_task:
                return f"错误：任务编号 {idx} 不存在"

            # 删除任务
            task_id = target_task.id
            parent_id = target_task.parent_id
            await task_board.db.delete(target_task)
            await task_board.db.commit()

            # 重新加载剩余任务并重新编号 - 使用 fresh query 确保拿到最新数据
            task_board.db.expire_all()  # 清除缓存（同步方法）

            if parent_id:
                remaining = await task_board.get_child_tasks(parent_id)

                # 按编号排序
                remaining.sort(key=lambda t: int(t.title.split(".")[0]) if "." in t.title and t.title[0].isdigit() else 0)

                # 重新编号 - 只处理有编号的任务
                for i, task in enumerate(remaining, 1):
                    num_str = task.title.split(". ")[0] if ". " in task.title else ""
                    if num_str.isdigit():
                        old_desc = task.title.split(". ", 1)[1] if ". " in task.title else task.title
                        task.title = f"{i}. {old_desc}"

                await task_board.db.commit()
                all_tasks = remaining
            else:
                all_tasks = []

            # 广播更新
            await self._emit_todo_updated(all_tasks)

            return f"已删除任务 {idx}"

    async def todo_clear(self) -> str:
        """清空所有待办任务（批量删除）

        Returns:
            str: 操作结果
        """
        db = await self._get_db()
        async with db:
            task_board = await self._get_task_board(db)

            # 获取父任务
            parent = await self._get_todo_list_parent()
            if not parent:
                return "待办列表为空"

            # 获取所有子任务
            tasks = await task_board.get_child_tasks(parent.id)
            if not tasks:
                return "待办列表为空"

            # 一次性删除所有子任务
            for task in tasks:
                await task_board.db.delete(task)

            # 删除父任务（todo list 本身）
            await task_board.db.delete(parent)

            await task_board.db.commit()

            # 广播更新（空列表）
            await self._emit_todo_updated([])

            return f"已清空所有待办任务（共删除 {len(tasks)} 个）"

    async def todo_list(self) -> str:
        """列出所有待办任务

        Returns:
            str: 格式化后的任务列表
        """
        tasks = await self._load_tasks()

        if not tasks:
            return "待办列表为空"

        lines = ["# 待办列表\n"]
        for task in tasks:
            status_icon = {
                TodoStatus.WAITING.value: "[ ]",
                TodoStatus.RUNNING.value: "[→]",
                TodoStatus.COMPLETED.value: "[x]",
                TodoStatus.CANCELLED.value: "[-]",
            }.get(task.status.lower() if task.status else "", "[?]")

            lines.append(f"{status_icon} {task.title}")

        return "\n".join(lines)

    # =========================================================================
    # Tool Definition Generator (for LLM)
    # =========================================================================

    @staticmethod
    def get_tool_definitions() -> list[dict]:
        """获取所有 todo 工具的定义 (用于注册到 LLM)

        Returns:
            list[dict]: 工具定义列表 (OpenAI function calling 格式)
        """
        # 定义基础工具结构
        tools = [
            {
                "name": "todo_create",
                "description": "创建新的待办列表。如果已存在待办列表会返回错误，此时应使用 todo_insert 添加任务。\n\n参数 tasks 是任务描述列表，例如：['完成任务A', '完成任务B']",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tasks": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "任务描述列表",
                        }
                    },
                    "required": ["tasks"],
                },
            },
            {
                "name": "todo_complete",
                "description": "标记指定编号的任务为已完成。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "idx": {
                            "type": "integer",
                            "description": "任务编号 (从 todo_list 获取)",
                        },
                        "result": {
                            "type": "string",
                            "description": "完成结果 (可选，默认 'done')",
                        },
                    },
                    "required": ["idx"],
                },
            },
            {
                "name": "todo_insert",
                "description": "插入新任务到待办列表的指定位置。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "idx": {
                            "type": "integer",
                            "description": "插入位置 (从 1 开始，0 或省略表示追加到末尾)",
                        },
                        "tasks": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "要插入的任务描述列表",
                        },
                    },
                    "required": ["tasks"],
                },
            },
            {
                "name": "todo_remove",
                "description": "删除指定编号的任务。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "idx": {
                            "type": "integer",
                            "description": "任务编号 (从 todo_list 获取)",
                        },
                    },
                    "required": ["idx"],
                },
            },
            {
                "name": "todo_clear",
                "description": "清空所有待办任务。当需要删除所有任务时使用此工具，比逐个删除更高效。",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "todo_list",
                "description": "列出当前待办列表中的所有任务及其状态。",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

        # 转换为 OpenAI function calling 格式
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"],
                },
            }
            for t in tools
        ]


# ============================================================================
# ============================================================================
# Convenience Functions (for external use)
# ============================================================================


async def emit_todo_updated(session_id: str, tasks: list[TaskItem]) -> None:
    """广播 todo.updated 事件"""
    toolkit = TodoToolkit(session_id)
    await toolkit._emit_todo_updated(tasks)


def format_todo_summary(tasks: list[dict]) -> str:
    """格式化待办事项摘要 (用于 interrupt supplement 上下文)

    Args:
        tasks: TodoItem 列表

    Returns:
        str: 格式化的摘要
    """
    if not tasks:
        return "无进行中的待办"

    pending = [t for t in tasks if t.get("status") in ("pending", "in_progress")]
    if not pending:
        return "所有任务已完成"

    lines = []
    for t in pending:
        status = "进行中" if t.get("status") == "in_progress" else "待处理"
        lines.append(f"  - [{status}] {t.get('content', '')}")

    return "\n".join(lines)


# Constants for magic strings
NO_PENDING_TASKS = "无进行中的待办"
ALL_TASKS_COMPLETED = "所有任务已完成"


async def get_interrupt_supplement(session_id: str) -> str:
    """获取中断补充上下文（集中统一的实现）

    从待办事项中获取当前进行中的任务，格式化为中断上下文。

    Args:
        session_id: 会话 ID

    Returns:
        str: 格式化的中断上下文，如果无待办则返回空字符串
    """
    from backend.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            toolkit = TodoToolkit(session_id=session_id, db=db)
            tasks = await toolkit._load_tasks()

            if not tasks:
                return ""

            todo_dicts = []
            for task in tasks:
                content = task.title.split(". ", 1)[1] if ". " in task.title else task.title
                status = "in_progress" if task.status.lower() == "running" else "pending"
                todo_dicts.append({"content": content, "status": status})

            summary = format_todo_summary(todo_dicts)
            if summary and summary not in (NO_PENDING_TASKS, ALL_TASKS_COMPLETED):
                return f"\n\n[任务中断 - 当前待办事项]\n{summary}"
            return ""

    except Exception as e:
        logger.warning(f"[TodoToolkit] Failed to get interrupt supplement: {e}")
        return ""
