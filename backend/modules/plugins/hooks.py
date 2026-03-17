"""Hooks - 事件钩子系统"""

import asyncio
from typing import Any, Callable, Awaitable
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class Hook:
    """钩子定义"""

    event: str
    callback: Callable[..., Awaitable[Any]]
    description: str = ""
    priority: int = 0  # 优先级，数值越大越先执行


# 预定义事件列表
EVENTS = [
    "message_received",  # 收到消息
    "before_process",  # 处理前
    "after_process",  # 处理后
    "tool_called",  # 工具调用
    "tool_result",  # 工具结果
    "task_created",  # 任务创建
    "task_completed",  # 任务完成
    "task_failed",  # 任务失败
    "agent_claiming_done",  # Agent声称完成
    "response_ready",  # 响应准备好
]


class EventBus:
    """事件总线"""

    def __init__(self):
        self._hooks: dict[str, list[Hook]] = {event: [] for event in EVENTS}
        self._hooks["*"] = []  # 通配符钩子

    def register(self, hook: Hook) -> None:
        """
        注册钩子

        Args:
            hook: 钩子对象
        """
        if hook.event not in self._hooks:
            self._hooks[hook.event] = []

        # 按优先级排序
        self._hooks[hook.event].append(hook)
        self._hooks[hook.event].sort(key=lambda h: h.priority, reverse=True)

        logger.debug(f"Registered hook: {hook.event} -> {hook.callback.__name__}")

    def unregister(self, event: str, callback: Callable) -> bool:
        """
        注销钩子

        Args:
            event: 事件名称
            callback: 回调函数

        Returns:
            bool: 是否成功注销
        """
        if event not in self._hooks:
            return False

        original_len = len(self._hooks[event])
        self._hooks[event] = [h for h in self._hooks[event] if h.callback != callback]
        return len(self._hooks[event]) < original_len

    async def emit(
        self,
        event: str,
        context: dict[str, Any] = None,
        **kwargs: Any,
    ) -> list[Any]:
        """
        触发事件

        Args:
            event: 事件名称
            context: 上下文数据
            **kwargs: 额外的上下文数据

        Returns:
            list: 所有钩子的返回值
        """
        context = context or {}
        context.update(kwargs)

        results = []

        # 收集要执行的所有钩子
        hooks_to_run = []

        # 先执行通配符钩子
        if "*" in self._hooks:
            hooks_to_run.extend(self._hooks["*"])

        # 再执行特定事件钩子
        if event in self._hooks:
            hooks_to_run.extend(self._hooks[event])

        # 执行钩子
        for hook in hooks_to_run:
            try:
                result = await hook.callback(event, context)
                if result is not None:
                    results.append(result)
            except Exception as e:
                logger.error(f"Hook error in {hook.event}: {e}")

        return results

    def list_hooks(self, event: str = None) -> dict[str, list[str]]:
        """
        列出已注册的钩子

        Args:
            event: 事件名称过滤，如果为None则列出所有

        Returns:
            dict: 事件到钩子名称的映射
        """
        if event:
            return {
                event: [
                    f"{h.callback.__name__} (priority={h.priority})"
                    for h in self._hooks.get(event, [])
                ]
            }

        return {
            ev: [
                f"{h.callback.__name__} (priority={h.priority})"
                for h in hooks
            ]
            for ev, hooks in self._hooks.items()
            if hooks
        }


# 全局事件总线实例
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """获取全局事件总线实例"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def create_hook(
    event: str,
    description: str = "",
    priority: int = 0,
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """
    装饰器：创建钩子

    Args:
        event: 事件名称
        description: 描述
        priority: 优先级

    Returns:
        装饰器函数

    Example:
        @create_hook("message_received", "处理收到的消息")
        async def my_hook(event: str, context: dict):
            # 处理逻辑
            return modified_context
    """

    def decorator(
        func: Callable[..., Awaitable[Any]]
    ) -> Hook:
        return Hook(
            event=event,
            callback=func,
            description=description,
            priority=priority,
        )

    return decorator
