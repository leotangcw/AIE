"""Superpowers Plugin - 开发流程插件

提供以下技能：
- 头脑风暴 (brainstorming)
- 任务规划 (planning)
- 调试 (debugging)
- 代码审查 (code_review)
- 验证 (verification)
"""

from typing import Any

from backend.modules.plugins.base import Plugin
from backend.modules.plugins.hooks import Hook, EVENTS


class SuperpowersPlugin(Plugin):
    """Superpowers 开发流程插件"""

    name = "superpowers"
    version = "1.0.0"
    description = "开发流程工具：头脑风暴、计划、调试、审查、验证等"
    author = "AIE Team"
    enabled_by_default = False  # 默认关闭，可手动开启

    # 技能实例
    _skills: dict[str, Any] = {}

    def __init__(self, manager=None):
        super().__init__(manager)
        self._initialized = False

    async def on_load(self) -> None:
        """加载插件时初始化"""
        # 延迟导入技能模块，避免循环依赖
        from .brainstorming import BrainstormingSkill
        from .planning import PlanningSkill
        from .debugging import DebuggingSkill
        from .code_review import CodeReviewSkill
        from .verification import VerificationSkill

        # 初始化各个技能
        self._skills = {
            "brainstorming": BrainstormingSkill(),
            "planning": PlanningSkill(),
            "debugging": DebuggingSkill(),
            "code_review": CodeReviewSkill(),
            "verification": VerificationSkill(),
        }

        self._initialized = True
        print(f"[Superpowers] Loaded skills: {list(self._skills.keys())}")

    async def on_enable(self) -> None:
        """启用插件"""
        if not self._initialized:
            await self.on_load()
        print(f"[Superpowers] Enabled with {len(self._skills)} skills")

    async def on_disable(self) -> None:
        """禁用插件"""
        print("[Superpowers] Disabled")

    def get_hooks(self) -> list[Hook]:
        """获取插件提供的钩子"""
        hooks = []

        # 注册各技能的钩子
        for skill_name, skill in self._skills.items():
            if hasattr(skill, "get_hooks"):
                skill_hooks = skill.get_hooks()
                hooks.extend(skill_hooks)

        return hooks

    def get_tools(self) -> list[Any]:
        """获取插件提供的工具"""
        tools = []

        # 收集所有技能的工具
        for skill_name, skill in self._skills.items():
            if hasattr(skill, "get_tools"):
                skill_tools = skill.get_tools()
                tools.extend(skill_tools)

        return tools


# 插件实例
class _PluginClass(SuperpowersPlugin):
    """插件包装类"""

    pass


# 导出插件实例供管理器使用
def _create_plugin(manager=None) -> SuperpowersPlugin:
    return SuperpowersPlugin(manager=manager)


__plugin__ = _create_plugin
