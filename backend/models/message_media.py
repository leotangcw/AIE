"""消息媒体关联模型"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.message import Message


def utc_now():
    """返回带时区的UTC时间"""
    return datetime.now(timezone.utc)


class MessageMedia(Base):
    """消息关联媒体表"""

    __tablename__ = "message_media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    media_type: Mapped[str] = mapped_column(String, nullable=False)  # image/audio/video/file
    src: Mapped[str] = mapped_column(String, nullable=False)          # /api/files/...
    name: Mapped[str] = mapped_column(String, nullable=True)
    alt: Mapped[str] = mapped_column(String, nullable=True)           # caption
    tool_name: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    message: Mapped["Message"] = relationship("Message", back_populates="media")

    __table_args__ = (Index("idx_message_media_msg", "message_id"),)
