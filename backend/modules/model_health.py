"""模型健康状态追踪器"""

from datetime import datetime
from typing import Any
from loguru import logger


class ModelHealthTracker:
    """追踪主模型和子模型的调用健康状态"""

    def __init__(self):
        self.status: dict[str, dict[str, Any]] = {
            "main": {
                "healthy": True,
                "model_name": "",
                "last_success": None,
                "last_failure": None,
                "failures": 0,
            },
            "sub": {
                "healthy": True,
                "model_name": "",
                "last_success": None,
                "last_failure": None,
                "failures": 0,
            },
        }

    def configure(self, main_model: str, sub_model: str):
        """配置模型名称"""
        self.status["main"]["model_name"] = main_model
        self.status["sub"]["model_name"] = sub_model

    def report_success(self, model_role: str):
        """报告模型调用成功"""
        if model_role not in self.status:
            return
        prev_healthy = self.status[model_role]["healthy"]
        self.status[model_role]["healthy"] = True
        self.status[model_role]["last_success"] = datetime.utcnow().isoformat() + "Z"
        self.status[model_role]["failures"] = 0
        if not prev_healthy:
            logger.info(f"Model {model_role} recovered to healthy")
            self._schedule_broadcast()

    def report_failure(self, model_role: str):
        """报告模型调用失败"""
        if model_role not in self.status:
            return
        self.status[model_role]["failures"] += 1
        self.status[model_role]["last_failure"] = datetime.utcnow().isoformat() + "Z"
        if self.status[model_role]["failures"] >= 3:
            self.status[model_role]["healthy"] = False
            logger.warning(f"Model {model_role} marked as unhealthy (3+ consecutive failures)")
            self._schedule_broadcast()

    async def _schedule_broadcast(self):
        """通过WS广播模型状态变化"""
        try:
            from backend.ws.connection import connection_manager
            from backend.ws.task_notifications import ModelStatusMessage
            await connection_manager.broadcast(ModelStatusMessage(
                type="model_status",
                models=self.get_status(),
            ))
        except Exception as e:
            logger.debug(f"Failed to broadcast model status: {e}")

    def get_status(self) -> dict[str, dict[str, Any]]:
        """获取当前模型状态（用于API）"""
        return {
            k: {
                "healthy": v["healthy"],
                "model_name": v["model_name"],
                "last_success": v["last_success"],
                "last_failure": v["last_failure"],
                "consecutive_failures": v["failures"],
            }
            for k, v in self.status.items()
        }
