"""Heartbeat WebSocket 事件"""

import time
from typing import Optional

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field


class HeartbeatEventPayload(BaseModel):
    """心跳事件负载"""

    task_id: str
    task_name: str
    status: str  # sent | ok-empty | ok | skipped | failed
    preview: Optional[str] = None  # first 200 chars
    duration_ms: Optional[float] = None
    ts: int = Field(default_factory=lambda: int(time.time()))  # unix timestamp
    reason: Optional[str] = None
    indicator_type: Optional[str] = None  # ok | alert | error


class HeartbeatEvent(BaseModel):
    """WebSocket 心跳事件"""

    model_config = ConfigDict(populate_by_name=True)

    type: str = Field(default="heartbeat_event", description="消息类型")
    task_id: str = Field(..., description="任务 ID")
    task_name: str = Field(..., description="任务名称")
    status: str = Field(..., description="状态")
    preview: Optional[str] = Field(None, description="预览")
    duration_ms: Optional[float] = Field(None, description="耗时")
    ts: int = Field(..., description="时间戳")
    reason: Optional[str] = Field(None, description="原因")
    indicator_type: Optional[str] = Field(None, description="指示器类型")

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return self.model_dump_json(by_alias=True)


class HeartbeatMetricsEvent(BaseModel):
    """WebSocket 心跳指标事件"""

    model_config = ConfigDict(populate_by_name=True)

    type: str = Field(default="heartbeat_metrics", description="消息类型")
    context_length: int = Field(..., description="context 长度")
    context_limit: int = Field(..., description="context 限制")
    memory_size: int = Field(..., description="memory 大小")
    queue_depth: int = Field(..., description="队列深度")
    session_idle_seconds: Optional[float] = Field(None, description="会话空闲秒数")
    timestamp: str = Field(..., description="时间戳")

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return self.model_dump_json(by_alias=True)


async def push_heartbeat_event(session_id: str, payload: HeartbeatEventPayload):
    """推送心跳事件到 session 的 WebSocket 连接"""
    from backend.ws.connection import connection_manager

    try:
        event = HeartbeatEvent(
            task_id=payload.task_id,
            task_name=payload.task_name,
            status=payload.status,
            preview=payload.preview,
            duration_ms=payload.duration_ms,
            ts=payload.ts,
            reason=payload.reason,
            indicator_type=payload.indicator_type,
        )
        await connection_manager.send_to_session(session_id, event)
    except Exception as e:
        logger.warning(f"Failed to push heartbeat event: {e}")


async def push_metrics_event(session_id: str, metrics: dict):
    """推送指标事件到 session 的 WebSocket 连接"""
    from backend.ws.connection import connection_manager

    try:
        event = HeartbeatMetricsEvent(
            context_length=metrics.get("context_length", 0),
            context_limit=metrics.get("context_limit", 200000),
            memory_size=metrics.get("memory_size", 0),
            queue_depth=metrics.get("queue_depth", 0),
            session_idle_seconds=metrics.get("session_idle_seconds"),
            timestamp=metrics.get("timestamp", ""),
        )
        await connection_manager.send_to_session(session_id, event)
    except Exception as e:
        logger.warning(f"Failed to push metrics event: {e}")
