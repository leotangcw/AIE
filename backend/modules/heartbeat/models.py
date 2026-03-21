"""HeartbeatTask 数据库模型"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Float, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class HeartbeatTask(Base):
    """心跳任务表 - Session 级任务表，任务完成或取消后删除"""

    __tablename__ = "heartbeat_tasks"

    # 主键
    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # 任务标识
    session_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    task_type: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # HEALTH_CHECK | METRIC_COLLECT | SESSION_KEEPALIVE | CUSTOM

    # 调度配置
    schedule_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # interval | cron
    interval_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cron_expr: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    active_hours: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )  # {"start": "HH:MM", "end": "HH:MM", "timezone": "Asia/Shanghai"}

    # 执行配置
    config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    prompt_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 状态
    status: Mapped[str] = mapped_column(
        String(32), default="idle"
    )  # idle | running | error | disabled
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_result: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )  # {"status": "ok", "preview": "...", "duration_ms": 123}
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 下次执行时间
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)

    # 启用/禁用
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # 元数据
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("idx_heartbeat_session", "session_id"),
        Index("idx_heartbeat_next_run", "next_run_at", sqlite_where=enabled.is_(True)),
        Index("idx_heartbeat_status", "status"),
    )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "name": self.name,
            "task_type": self.task_type,
            "schedule_type": self.schedule_type,
            "interval_seconds": self.interval_seconds,
            "cron_expr": self.cron_expr,
            "active_hours": self.active_hours,
            "config": self.config,
            "prompt_template": self.prompt_template,
            "status": self.status,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_result": self.last_result,
            "last_error": self.last_error,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# 任务类型常量
class TaskType:
    HEALTH_CHECK = "HEALTH_CHECK"
    METRIC_COLLECT = "METRIC_COLLECT"
    SESSION_KEEPALIVE = "SESSION_KEEPALIVE"
    CUSTOM = "CUSTOM"


# 调度类型常量
class ScheduleType:
    INTERVAL = "interval"
    CRON = "cron"


# 状态常量
class TaskStatus:
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    DISABLED = "disabled"
