"""Heartbeat Pydantic Schemas"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ActiveHoursSchema(BaseModel):
    """active_hours 配置"""

    start: str = Field(default="08:00", description="开始时间 HH:MM")
    end: str = Field(default="22:00", description="结束时间 HH:MM")
    timezone: str = Field(default="Asia/Shanghai", description="时区")


class HeartbeatTaskCreate(BaseModel):
    """创建心跳任务请求"""

    session_id: str = Field(..., description="会话 ID")
    name: str = Field(..., description="任务名称")
    task_type: str = Field(..., description="任务类型: HEALTH_CHECK | METRIC_COLLECT | SESSION_KEEPALIVE | CUSTOM")
    schedule_type: str = Field(default="interval", description="调度类型: interval | cron")
    interval_seconds: Optional[float] = Field(None, description="间隔秒数（interval 模式）")
    cron_expr: Optional[str] = Field(None, description="Cron 表达式（cron 模式）")
    active_hours: Optional[ActiveHoursSchema] = Field(None, description="生效时间段")
    config: Optional[dict[str, Any]] = Field(None, description="任务配置")
    prompt_template: Optional[str] = Field(None, description="自定义任务 prompt 模板")
    enabled: bool = Field(default=True, description="是否启用")


class HeartbeatTaskUpdate(BaseModel):
    """更新心跳任务请求"""

    name: Optional[str] = Field(None, description="任务名称")
    schedule_type: Optional[str] = Field(None, description="调度类型: interval | cron")
    interval_seconds: Optional[float] = Field(None, description="间隔秒数")
    cron_expr: Optional[str] = Field(None, description="Cron 表达式")
    active_hours: Optional[ActiveHoursSchema] = Field(None, description="生效时间段")
    config: Optional[dict[str, Any]] = Field(None, description="任务配置")
    prompt_template: Optional[str] = Field(None, description="prompt 模板")
    enabled: Optional[bool] = Field(None, description="是否启用")


class HeartbeatTaskResponse(BaseModel):
    """心跳任务响应"""

    id: str
    session_id: str
    name: str
    task_type: str
    schedule_type: str
    interval_seconds: Optional[float]
    cron_expr: Optional[str]
    active_hours: Optional[dict[str, Any]]
    config: Optional[dict[str, Any]]
    prompt_template: Optional[str]
    status: str
    last_run_at: Optional[str]
    last_result: Optional[dict[str, Any]]
    last_error: Optional[str]
    next_run_at: Optional[str]
    enabled: bool
    created_at: Optional[str]
    updated_at: Optional[str]


class HeartbeatConfigUpdate(BaseModel):
    """心跳全局配置更新"""

    enabled: Optional[bool] = Field(None, description="是否启用")
    interval_seconds: Optional[float] = Field(None, description="默认间隔秒数")
    active_hours: Optional[ActiveHoursSchema] = Field(None, description="默认生效时间段")


class HeartbeatConfigResponse(BaseModel):
    """心跳全局配置响应"""

    enabled: bool
    interval_seconds: float
    active_hours: Optional[ActiveHoursSchema]


class HeartbeatMetricsResponse(BaseModel):
    """心跳指标响应"""

    context_length: int = Field(..., description="当前 context 长度")
    context_limit: int = Field(..., description="Context 长度限制")
    memory_size: int = Field(..., description="Memory 文件大小（字节）")
    queue_depth: int = Field(..., description="消息队列深度")
    session_idle_seconds: Optional[float] = Field(None, description="会话空闲秒数")
    timestamp: str = Field(..., description="采集时间")


class DeleteResponse(BaseModel):
    """删除响应"""

    success: bool
    message: str
