"""队列与任务管理 API"""

from fastapi import APIRouter, HTTPException, Request, status
from loguru import logger
from pydantic import BaseModel

router = APIRouter(prefix="/api/queue", tags=["queue"])


class QueueStatsResponse(BaseModel):
    """队列统计响应"""
    inbound_size: int
    outbound_size: int
    active_tasks: int
    rate_limiter: dict | None


class CancelTaskRequest(BaseModel):
    """取消任务请求"""
    session_id: str


class SupplementTaskRequest(BaseModel):
    """补充任务请求 - 用户在任务执行时发送新消息"""
    session_id: str
    content: str
    chat_id: str | None = None
    channel: str | None = None


def _get_handler(request: Request):
    """获取 message_handler，不存在则抛 503"""
    if not hasattr(request.app.state, "message_handler"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Message handler not initialized",
        )
    return request.app.state.message_handler


@router.get("/stats", response_model=QueueStatsResponse)
async def get_queue_stats(request: Request) -> QueueStatsResponse:
    """获取队列统计信息"""
    try:
        handler = _get_handler(request)
        stats = await handler.get_queue_stats()
        return QueueStatsResponse(**stats)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get queue stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/cancel")
async def cancel_task(request: Request, body: CancelTaskRequest) -> dict:
    """取消正在处理的任务（同时取消 WebSocket 和渠道任务）"""
    try:
        # 取消 WebSocket 会话
        from backend.ws.connection import cancel_session
        ws_cancelled = cancel_session(body.session_id)

        # 取消渠道消息处理
        channel_cancelled = False
        if hasattr(request.app.state, "message_handler"):
            handler = request.app.state.message_handler
            channel_cancelled = await handler.cancel_task(body.session_id)

        success = ws_cancelled or channel_cancelled
        return {
            "success": success,
            "message": "任务已停止" if success else "没有正在执行的任务",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to cancel task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/supplement")
async def supplement_task(request: Request, body: SupplementTaskRequest) -> dict:
    """补充任务 - 用户在任务执行时发送新消息，自动带上待办上下文

    1. 取消当前正在执行的任务
    2. 获取当前待办事项上下文
    3. 将新消息与待办上下文一起放入队列

    这实现了 JiuWenClaw 的 supplement 机制：
    - 允许用户在 AI 正在执行任务时发送新需求
    - 当前任务被中断，但待办事项被保留
    - 新消息会被追加到待办列表
    """
    try:
        # 1. 取消当前正在执行的任务
        from backend.ws.connection import cancel_session
        cancel_session(body.session_id)

        # 2. 获取待办事项上下文（使用集中统一的实现）
        from backend.modules.agent.todo_toolkit import get_interrupt_supplement
        supplement_context = await get_interrupt_supplement(body.session_id)

        # 3. 构建补充消息（包含待办上下文）
        full_content = body.content
        if supplement_context:
            full_content = f"{body.content}{supplement_context}"

        # 4. 放入队列（通过 message_handler）
        queued = False
        queue_error = None
        if hasattr(request.app.state, "message_handler"):
            handler = request.app.state.message_handler
            try:
                # 调用队列的 supplement 方法
                if hasattr(handler, "supplement_task"):
                    queued = await handler.supplement_task(
                        session_id=body.session_id,
                        content=full_content,
                        channel=body.channel,
                        chat_id=body.chat_id,
                    )
            except Exception as e:
                queue_error = str(e)
                logger.warning(f"supplement_task not available: {e}")

        # 如果 handler 没有 supplement_task 方法，尝试通用的 SessionManager.add_message
        if not queued and hasattr(request.app.state, "message_handler"):
            try:
                # 直接使用 SessionManager 保存消息（消息会被后续处理）
                from backend.database import AsyncSessionLocal
                from backend.modules.session.manager import SessionManager

                async with AsyncSessionLocal() as db:
                    session_manager = SessionManager(db)
                    await session_manager.add_message(
                        session_id=body.session_id,
                        role="user",
                        content=full_content,
                    )
                    queued = True
                    logger.info(f"[Supplement] Message saved via SessionManager for session {body.session_id}")
            except Exception as e:
                queue_error = str(e)
                logger.warning(f"Failed to save supplement message: {e}")

        return {
            "success": queued,
            "message": "补充消息已排队" if queued else f"补充消息保存失败: {queue_error}",
            "supplement_context": supplement_context,
            "queued": queued,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to supplement task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/active-tasks")
async def list_active_tasks(request: Request) -> dict:
    """列出所有活跃任务"""
    try:
        handler = _get_handler(request)
        active_tasks = handler.get_active_tasks()
        return {"active_tasks": active_tasks, "count": len(active_tasks)}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to list active tasks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
