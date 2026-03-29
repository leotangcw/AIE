"""SuperWorkers Plugin - 企业工作流插件

提供以下技能：
- using-superworkers: 入口发现
- task-knowledge-review: 任务前知识审查（核心工作流）
- execution-standards: 执行过程规范
- trace-recording: 操作轨迹记录（自动Hook）
- trace-analyzer: 分析近期轨迹（人工触发）
- skill-distiller: 从轨迹提炼技能（人工触发）
- skill-refiner: 优化已有技能（人工触发）
"""

from typing import Any

from backend.modules.plugins.base import Plugin
from backend.modules.plugins.hooks import Hook


class SuperWorkersPlugin(Plugin):
    """SuperWorkers 企业工作流插件"""

    name = "superworkers"
    version = "1.0.0"
    description = "企业工作流：知识检索、技能匹配、轨迹记录、经验进化"
    author = "AIE Team"
    enabled_by_default = False

    _skills: dict[str, Any] = {}

    def __init__(self, manager=None):
        super().__init__(manager)
        self._initialized = False

    async def on_load(self) -> None:
        """加载插件时初始化"""
        from .using_superworkers import UsingSuperWorkersSkill
        from .task_knowledge_review import TaskKnowledgeReviewSkill
        from .execution_standards import ExecutionStandardsSkill
        from .trace_recording import TraceRecordingSkill
        from .trace_analyzer import TraceAnalyzerSkill
        from .skill_distiller import SkillDistillerSkill
        from .skill_refiner import SkillRefinerSkill

        self._skills = {
            "using-superworkers": UsingSuperWorkersSkill(),
            "task-knowledge-review": TaskKnowledgeReviewSkill(),
            "execution-standards": ExecutionStandardsSkill(),
            "trace-recording": TraceRecordingSkill(),
            "trace-analyzer": TraceAnalyzerSkill(),
            "skill-distiller": SkillDistillerSkill(),
            "skill-refiner": SkillRefinerSkill(),
        }
        self._initialized = True
        print(f"[SuperWorkers] Loaded skills: {list(self._skills.keys())}")

    async def on_enable(self) -> None:
        """启用插件"""
        if not self._initialized:
            await self.on_load()

        # 注册轨迹清理定时任务
        try:
            from backend.modules.cron.service import get_cron_service
            cron_service = get_cron_service()
            if cron_service:
                # 每天凌晨3点清理过期轨迹（默认保留30天）
                cron_service.add_or_update_task(
                    task_id="superworkers:trace-cleanup",
                    name="清理过期操作轨迹",
                    cron_expr="0 3 * * *",
                    task_type="plugin",
                    action={
                        "plugin": "superworkers",
                        "action": "cleanup_traces",
                        "retain_days": 30,
                    },
                    enabled=True,
                )
                from loguru import logger
                logger.info("SuperWorkers: Registered trace cleanup cron task")
        except Exception as e:
            from loguru import logger
            logger.debug(f"SuperWorkers: Failed to register cleanup cron (non-critical): {e}")

        print("[SuperWorkers] Enabled")

    async def on_disable(self) -> None:
        """禁用插件"""
        print("[SuperWorkers] Disabled")

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
class _PluginClass(SuperWorkersPlugin):
    """插件包装类"""

    pass


# 导出插件实例供管理器使用
def _create_plugin(manager=None) -> SuperWorkersPlugin:
    return SuperWorkersPlugin(manager=manager)


__plugin__ = _create_plugin
