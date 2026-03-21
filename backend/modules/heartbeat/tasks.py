"""Heartbeat 任务类型实现"""

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from backend.modules.heartbeat.models import TaskType


@dataclass
class HeartbeatResult:
    """心跳任务执行结果"""

    status: str  # ok | ok-empty | skipped | failed
    response: Optional[str] = None
    preview: Optional[str] = None
    metrics: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    reason: Optional[str] = None


# HEARTBEAT_OK 标识
HEARTBEAT_OK = "HEARTBEAT_OK"


class HealthCheckTask:
    """健康检查任务 - 读取 HEARTBEAT.md 并执行任务"""

    HEARTBEAT_FILE = "HEARTBEAT.md"

    async def execute(
        self,
        workspace: Path,
        agent_loop=None,
        session_id: str = None,
    ) -> HeartbeatResult:
        """
        执行健康检查任务

        1. 如果 HEARTBEAT.md 不存在，跳过
        2. 如果文件为空或只有注释，回复 HEARTBEAT_OK
        3. 否则执行文件中的任务
        """
        hb_file = workspace / self.HEARTBEAT_FILE

        if not hb_file.exists():
            return HeartbeatResult(
                status="skipped",
                reason="no_heartbeat_file",
                response="HEARTBEAT_OK",
            )

        try:
            content = hb_file.read_text(encoding="utf-8").strip()
        except Exception as e:
            return HeartbeatResult(
                status="failed",
                error=f"Failed to read HEARTBEAT.md: {e}",
            )

        # 判断内容是否为空（只有注释或空白）
        if self._is_empty_content(content):
            return HeartbeatResult(
                status="ok-empty",
                response=HEARTBEAT_OK,
            )

        # 如果有 agent_loop，执行任务
        if agent_loop is not None and session_id:
            try:
                response = await agent_loop.process_message(
                    message=content,
                    session_id=session_id,
                )

                if not response or self._is_heartbeat_ok(response):
                    return HeartbeatResult(
                        status="ok-empty",
                        response=HEARTBEAT_OK,
                    )

                return HeartbeatResult(
                    status="ok",
                    response=response,
                    preview=response[:200] if len(response) > 200 else response,
                )
            except Exception as e:
                logger.error(f"HealthCheck task execution failed: {e}")
                return HeartbeatResult(
                    status="failed",
                    error=str(e),
                )
        else:
            # 无 agent_loop，返回任务内容供调度器处理
            return HeartbeatResult(
                status="ok",
                response=content,
                preview=content[:200] if len(content) > 200 else content,
            )

    def _is_empty_content(self, content: str) -> bool:
        """判断内容是否为空（只有注释或空白）"""
        if not content:
            return True

        for line in content.split("\n"):
            stripped = line.strip()
            # 跳过空行
            if not stripped:
                continue
            # 跳过注释行 (# 开头)
            if stripped.startswith("#"):
                continue
            # 跳过 markdown ATX 标题 (## 开头)
            if stripped.startswith("##"):
                continue
            return False

        return True

    def _is_heartbeat_ok(self, response: str) -> bool:
        """判断响应是否为 HEARTBEAT_OK"""
        if not response:
            return True
        upper = response.strip().upper()
        return (
            upper == HEARTBEAT_OK
            or upper.startswith(HEARTBEAT_OK)
            or HEARTBEAT_OK in upper
        )


class MetricCollectTask:
    """指标采集任务 - 收集 context_length, memory_size, queue_depth 等"""

    async def execute(
        self,
        workspace: Path,
        context_length: int = 0,
        queue_stats: dict = None,
    ) -> HeartbeatResult:
        """执行指标采集"""
        try:
            # 采集 memory 信息
            memory_size = 0
            memory_file = workspace / "memory" / "memory.md"
            if memory_file.exists():
                content = memory_file.read_text(encoding="utf-8")
                memory_size = len(content)

            # 采集 queue 信息
            queue_depth = 0
            if queue_stats:
                queue_depth = queue_stats.get("inbound_size", 0) or queue_stats.get(
                    "pending_count", 0
                )

            metrics = {
                "context_length": context_length,
                "context_limit": 200000,  # 默认限制
                "memory_size": memory_size,
                "queue_depth": queue_depth,
                "timestamp": time.time(),
            }

            preview = (
                f"ctx:{metrics['context_length']} "
                f"mem:{metrics['memory_size']}B "
                f"q:{metrics['queue_depth']}"
            )

            return HeartbeatResult(
                status="ok",
                response=f"Metrics: {preview}",
                preview=preview,
                metrics=metrics,
            )
        except Exception as e:
            logger.error(f"MetricCollect task failed: {e}")
            return HeartbeatResult(
                status="failed",
                error=str(e),
            )


class SessionKeepaliveTask:
    """会话保活任务 - 轻量 ping"""

    async def execute(self) -> HeartbeatResult:
        """执行会话保活"""
        return HeartbeatResult(
            status="ok-empty",
            response="SESSION_ALIVE",
        )


class CustomTask:
    """自定义任务 - 用户定义的 periodic prompt 执行"""

    async def execute(
        self,
        prompt_template: str,
        workspace: Path,
        agent_loop=None,
        session_id: str = None,
    ) -> HeartbeatResult:
        """执行自定义任务"""
        if not prompt_template:
            return HeartbeatResult(
                status="failed",
                error="No prompt template",
            )

        if agent_loop is not None and session_id:
            try:
                response = await agent_loop.process_message(
                    message=prompt_template,
                    session_id=session_id,
                )
                return HeartbeatResult(
                    status="ok",
                    response=response,
                    preview=response[:200] if len(response) > 200 else response,
                )
            except Exception as e:
                logger.error(f"Custom task execution failed: {e}")
                return HeartbeatResult(
                    status="failed",
                    error=str(e),
                )
        else:
            return HeartbeatResult(
                status="ok",
                response=prompt_template,
                preview=prompt_template[:200] if len(prompt_template) > 200 else prompt_template,
            )


# 任务处理函数映射
TASK_HANDLERS = {
    TaskType.HEALTH_CHECK: HealthCheckTask,
    TaskType.METRIC_COLLECT: MetricCollectTask,
    TaskType.SESSION_KEEPALIVE: SessionKeepaliveTask,
    TaskType.CUSTOM: CustomTask,
}


def get_task_handler(task_type: str):
    """获取任务处理器"""
    handler_class = TASK_HANDLERS.get(task_type)
    if handler_class:
        return handler_class()
    return None
