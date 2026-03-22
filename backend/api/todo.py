"""Todo List API - 提供 Todo 列表查询接口"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.task_item import TaskItem
from backend.modules.agent.task_board import TaskBoardService

router = APIRouter(prefix="/api/todo", tags=["todo"])


# ============================================================================
# Pydantic Schemas
# ============================================================================


class TodoItemResponse(BaseModel):
    """Todo 项响应"""
    id: str
    content: str
    status: str
    createdAt: str = ""
    updatedAt: str = ""

    class Config:
        from_attributes = True


class TodoListResponse(BaseModel):
    """Todo 列表响应"""
    todos: List[TodoItemResponse] = Field(default_factory=list)
    session_id: str


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("/session/{session_id}", response_model=TodoListResponse)
async def get_session_todo_list(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取会话的 Todo 列表

    返回当前会话的 Todo 列表，包含所有待办事项。
    用于页面刷新时恢复 Todo 列表状态。
    """
    try:
        async with db:
            task_board = TaskBoardService(db)

            # 获取会话的所有顶级任务
            parent_tasks = await task_board.get_parent_tasks(session_id)

            # 找出 todo list (通过 description 识别)
            todo_lists = [
                t for t in parent_tasks
                if "LLM 管理的 Todo 列表" in (t.description or "")
            ]

            if not todo_lists:
                return TodoListResponse(todos=[], session_id=session_id)

            latest_todo_list = todo_lists[0]

            # 获取子任务
            children = await task_board.get_child_tasks(latest_todo_list.id)

            if not children:
                return TodoListResponse(todos=[], session_id=session_id)

            # 转换为前端格式
            todos = []
            for task in children:
                # 状态映射
                status = task.status.lower() if task.status else "pending"
                if status == "done":
                    status = "completed"
                elif status in ("failed", "cancelled"):
                    status = "pending"
                elif status == "running":
                    status = "in_progress"
                else:
                    status = "pending"

                # 提取 content (去掉编号)
                content = task.title
                if ". " in content:
                    parts = content.split(". ", 1)
                    if parts[0].isdigit():
                        content = parts[1]

                todos.append(TodoItemResponse(
                    id=task.id,
                    content=content,
                    status=status,
                    createdAt=task.created_at.isoformat() if task.created_at else "",
                    updatedAt=task.updated_at.isoformat() if task.updated_at else "",
                ))

            return TodoListResponse(todos=todos, session_id=session_id)

    except Exception as e:
        logger.error(f"Failed to get todo list for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"获取 Todo 列表失败: {str(e)}")
