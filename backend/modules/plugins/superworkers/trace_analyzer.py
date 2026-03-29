"""Trace Analyzer Skill - 分析近期轨迹

人工触发的技能，帮助分析 Agent 最近的操作轨迹。
触发方式: "分析一下最近的轨迹" / "看看最近做得怎么样"
"""

from typing import Any, Optional
from datetime import datetime, timedelta

from loguru import logger
from backend.modules.plugins.hooks import Hook


class TraceAnalyzerSkill:
    """
    轨迹分析技能

    分析近期的操作轨迹，提供：
    - 整体成功率统计
    - 常见问题模式
    - 知识使用情况
    - 改进建议
    """

    def __init__(self):
        self._trace_recording = None

    @property
    def name(self) -> str:
        return "trace-analyzer"

    def _get_trace_recording(self):
        """懒加载 TraceRecordingSkill"""
        if self._trace_recording is None:
            try:
                from backend.modules.plugins import get_plugin_manager
                manager = get_plugin_manager()
                plugin = manager.get_plugin("superworkers")
                if plugin:
                    self._trace_recording = plugin._skills.get("trace-recording")
            except Exception as e:
                logger.debug(f"Failed to get trace recording skill: {e}")
        return self._trace_recording

    def should_activate(self, message: str) -> bool:
        """人工触发"""
        triggers = [
            "分析轨迹", "分析最近的", "看看最近",
            "最近做得怎么样", "操作记录", "工作回顾",
            "轨迹分析", "trace analysis",
        ]
        message_lower = message.lower()
        return any(t in message_lower for t in triggers)

    async def process(self, message: str, context: dict[str, Any]) -> Optional[str]:
        """分析近期轨迹"""
        recording = self._get_trace_recording()
        if not recording:
            return "轨迹记录系统未启用或未初始化。请确认 SuperWorkers 插件已启用。"

        # 解析用户要求的时间范围
        days = self._parse_days(message)

        # 获取统计信息
        stats = recording.get_trace_stats(days=days)
        recent_traces = recording.get_recent_traces(limit=20)

        if not stats or stats.get("total", 0) == 0:
            return f"近 {days} 天内没有操作轨迹记录。"

        return self._build_analysis(stats, recent_traces, days)

    def _parse_days(self, message: str) -> int:
        """解析用户要求的时间范围"""
        import re
        # 匹配 "近X天" / "最近X天" / "X天内"
        match = re.search(r'(?:近|最近)?(\d+)\s*天', message)
        if match:
            return int(match.group(1))
        return 30  # 默认30天

    def _build_analysis(self, stats: dict, traces: list[dict], days: int) -> str:
        """构建分析报告"""
        total = stats.get("total", 0)
        success_count = stats.get("success_count", 0)
        with_knowledge = stats.get("with_knowledge", 0)
        avg_duration = stats.get("avg_duration", 0)
        avg_tool_calls = stats.get("avg_tool_calls", 0)

        success_rate = (success_count / total * 100) if total > 0 else 0
        knowledge_rate = (with_knowledge / total * 100) if total > 0 else 0

        # 按任务类型分类
        task_type_counts = {}
        for t in traces:
            tt = t.get("task_type", "unknown")
            task_type_counts[tt] = task_type_counts.get(tt, 0) + 1

        # 构建报告
        report = f"""## 轨迹分析报告（近 {days} 天）

### 总体统计
| 指标 | 数值 |
|------|------|
| 总任务数 | {total} |
| 成功任务 | {success_count} |
| 成功率 | {success_rate:.1f}% |
| 使用知识检索 | {with_knowledge} 次 ({knowledge_rate:.1f}%) |
| 平均耗时 | {avg_duration/1000:.1f} 秒 |
| 平均工具调用 | {avg_tool_calls:.1f} 次 |

### 任务类型分布
"""
        for tt, count in sorted(task_type_counts.items(), key=lambda x: -x[1]):
            report += f"- **{tt}**: {count} 次\n"

        # 分析模式和问题
        report += "\n### 发现\n"

        if knowledge_rate < 30:
            report += "- **知识使用率偏低**: 大部分任务没有先检索企业知识，建议激活 SuperWorkers 工作流\n"

        if success_rate < 70:
            report += f"- **成功率偏低**: 当前成功率 {success_rate:.1f}%，建议分析失败原因\n"
        elif success_rate > 95:
            report += "- **运行稳定**: 成功率很高，继续保持\n"

        if avg_duration > 30000:
            report += f"- **响应较慢**: 平均耗时 {avg_duration/1000:.0f} 秒，可能需要优化\n"

        # 最近失败的任务
        failed = [t for t in traces if t.get("outcome") != "success"][:3]
        if failed:
            report += "\n### 最近的失败任务\n"
            for f in failed:
                report += f"- {f.get('started_at', '?')[:16]} | {f.get('task_type', '?')} | {f.get('trace_id', '?')[:8]}\n"
            report += "可以使用轨迹详情进一步分析失败原因。\n"

        report += """
### 建议
- 使用 `skill-distiller` 从成功轨迹中提炼新技能
- 使用 `skill-refiner` 优化已有技能
- 定期分析有助于发现改进方向
"""

        return report

    def get_hooks(self) -> list[Hook]:
        """不注册自动 Hook"""
        return []
