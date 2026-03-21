"""任务看板模型 - 持久化任务项"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class TaskScope(Enum):
    """任务范围 - 区分系统级和会话级"""
    SYSTEM = "system"    # 系统级周期任务 (Cron)
    SESSION = "session"  # 会话级任务 (用户上下文)


class TaskType(Enum):
    """任务来源类型"""
    MANUAL = "manual"    # 手动创建
    WORKFLOW = "workflow"  # 工作流创建
    SUBAGENT = "subagent"  # 子代理创建
    CRON = "cron"       # Cron定时任务


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"    # 待开始
    RUNNING = "running"    # 进行中
    DONE = "done"          # 已完成
    FAILED = "failed"      # 异常
    CANCELLED = "cancelled"  # 已取消


class TaskItem(Base):
    """任务项 - 核心模型"""
    __tablename__ = "task_items"

    # 基础信息
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=True, default="")

    # 任务范围 (核心区分)
    task_scope: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TaskScope.SESSION.value
    )
    session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # 任务类型
    task_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TaskType.MANUAL.value
    )
    parent_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # 周期任务 (仅SYSTEM级别)
    cron_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    cron_expression: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_run_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 状态与进度
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TaskStatus.PENDING.value
    )
    progress: Mapped[int] = mapped_column(Integer, default=0)

    # 时间追踪
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    estimated_duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actual_duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 错误处理
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)

    # 元数据
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # 索引
    __table_args__ = (
        Index("idx_task_scope_status", "task_scope", "status"),
        Index("idx_task_session", "session_id", "status"),
        Index("idx_task_cron", "cron_id"),
        Index("idx_task_parent", "parent_id"),
        Index("idx_task_next_run", "next_run_at"),
    )

    @staticmethod
    def _utc_to_iso(dt: Optional[datetime]) -> Optional[str]:
        """将 UTC datetime 转换为带 Z 后缀的 ISO 字符串，供前端正确解析为 UTC 时间"""
        if not dt:
            return None
        return dt.isoformat() + "Z"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "task_scope": self.task_scope,
            "session_id": self.session_id,
            "task_type": self.task_type,
            "parent_id": self.parent_id,
            "cron_id": self.cron_id,
            "cron_expression": self.cron_expression,
            "next_run_at": self._utc_to_iso(self.next_run_at),
            "last_run_status": self.last_run_status,
            "last_run_at": self._utc_to_iso(self.last_run_at),
            "status": self.status,
            "progress": self.progress,
            "started_at": self._utc_to_iso(self.started_at),
            "completed_at": self._utc_to_iso(self.completed_at),
            "estimated_duration": self.estimated_duration,
            "actual_duration": self.actual_duration,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "created_at": self._utc_to_iso(self.created_at),
            "updated_at": self._utc_to_iso(self.updated_at),
        }

    @property
    def is_system(self) -> bool:
        """是否为系统级任务"""
        return self.task_scope == TaskScope.SYSTEM.value

    @property
    def is_session(self) -> bool:
        """是否为会话级任务"""
        return self.task_scope == TaskScope.SESSION.value

    @property
    def is_parent(self) -> bool:
        """是否为父任务"""
        return self.parent_id is None

    @property
    def has_subtasks(self) -> bool:
        """是否有子任务 (在查询时由外层填充)"""
        return hasattr(self, '_sub_tasks') and self._sub_tasks

    @property
    def status_display(self) -> str:
        """状态显示文本"""
        status_map = {
            "pending": "待开始",
            "running": "进行中",
            "done": "已完成",
            "failed": "异常",
            "cancelled": "已取消",
        }
        return status_map.get(self.status, self.status)

    @property
    def task_type_display(self) -> str:
        """任务类型显示文本"""
        type_map = {
            "manual": "手动任务",
            "workflow": "工作流",
            "subagent": "子代理",
            "cron": "定时任务",
        }
        return type_map.get(self.task_type, self.task_type)
