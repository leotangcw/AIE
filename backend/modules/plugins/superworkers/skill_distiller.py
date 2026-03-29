"""Skill Distiller Skill - 从轨迹提炼新技能

人工触发的技能，从成功/失败的轨迹中提炼新的技能。
触发方式: "把这个经验整理成技能" / "总结最佳实践" / "提炼新技能"
"""

from typing import Any, Optional

from loguru import logger
from backend.modules.plugins.hooks import Hook


class SkillDistillerSkill:
    """
    技能提炼技能

    从 Agent 的操作轨迹中识别可复用的模式，提炼为新的候选技能。
    新技能存入 _candidates/ 目录，需要人工审核后才发布。
    """

    def __init__(self):
        self._trace_recording = None

    @property
    def name(self) -> str:
        return "skill-distiller"

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
            "整理成技能", "总结成技能", "提炼技能", "提炼新技能",
            "最佳实践", "总结经验", "经验整理", "生成技能",
        ]
        message_lower = message.lower()
        return any(t in message_lower for t in triggers)

    async def process(self, message: str, context: dict[str, Any]) -> Optional[str]:
        """从轨迹中提炼技能"""
        recording = self._get_trace_recording()
        if not recording:
            return "轨迹记录系统未启用。请确认 SuperWorkers 插件已启用。"

        # 获取最近的轨迹（默认分析近7天）
        recent_traces = recording.get_recent_traces(limit=20, task_type=None)

        # 如果用户指定了任务类型，按类型过滤
        task_type = self._parse_task_type(message)
        if task_type:
            recent_traces = recording.get_recent_traces(limit=20, task_type=task_type)

        if not recent_traces:
            return "没有找到足够的轨迹数据来提炼技能。需要至少几条操作记录。"

        # 获取完整轨迹详情进行分析
        detailed_traces = []
        for trace_summary in recent_traces[:10]:
            detail = recording.get_trace_detail(trace_summary["trace_id"])
            if detail:
                detailed_traces.append(detail)

        if not detailed_traces:
            return "轨迹详情不可用。请确认轨迹文件存在。"

        # 生成候选技能
        return self._generate_candidate_skill(detailed_traces, message)

    def _parse_task_type(self, message: str) -> Optional[str]:
        """解析用户指定的任务类型"""
        task_keywords = {
            "knowledge_query": ["知识", "检索", "查询"],
            "content_creation": ["写", "文档", "报告", "方案"],
            "web_search": ["搜索", "查询"],
            "coding": ["代码", "编程"],
        }
        for tt, keywords in task_keywords.items():
            for kw in keywords:
                if kw in message:
                    return tt
        return None

    def _generate_candidate_skill(self, traces: list[dict], user_message: str) -> str:
        """生成候选技能"""
        # 提取共同模式
        common_tools = self._extract_common_tools(traces)
        common_patterns = self._extract_patterns(traces)

        if not common_tools and not common_patterns:
            return """分析完成，但没有发现明显的可复用模式。

可能的原因：
- 轨迹数量不足以发现模式（建议至少积累5条以上相似任务）
- 任务类型差异太大，难以提炼通用技能
- 任务过于简单，不需要专门的技能

建议继续使用，积累更多轨迹后再尝试提炼。"""

        # 生成 SKILL.md 内容
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        skill_name = f"{date_str}-auto-distilled"
        task_types = set()
        for t in traces:
            tt = t.get("metadata", {}).get("task_type", "general")
            task_types.add(tt)
        task_type_desc = "、".join(task_types) if task_types else "通用"

        skill_md = f"""---
title: 自动提炼技能 ({task_type_desc})
description: 基于轨迹分析自动提炼的技能，覆盖 {task_type_desc} 类任务
tags: [auto-learned, candidate]
confidence: 0.6
source: auto
created: {date_str}
status: candidate
---

# 自动提炼技能 ({task_type_desc})

> 此技能由轨迹分析自动生成，状态为**候选**，需要人工审核后才可发布。

## 触发条件
- 涉及 {task_type_desc} 类任务时

## 常用工具
"""

        for tool, count in common_tools[:10]:
            skill_md += f"- `{tool}` (使用频率: {count})\n"

        if common_patterns:
            skill_md += "\n## 操作模式\n"
            for pattern in common_patterns[:5]:
                skill_md += f"1. {pattern}\n"

        skill_md += "\n## 统计依据\n"
        skill_md += f"- 分析轨迹数: {len(traces)}\n"
        skill_md += f"- 成功轨迹: {sum(1 for t in traces if t.get('output', {}).get('outcome') == 'success')}\n"

        # 保存到 candidates 目录
        from backend.utils.paths import SKILLS_DIR
        candidates_dir = SKILLS_DIR / "_candidates" / skill_name
        candidates_dir.mkdir(parents=True, exist_ok=True)

        skill_file = candidates_dir / "SKILL.md"
        skill_file.write_text(skill_md, encoding="utf-8")

        patterns_text = ""
        if common_patterns:
            patterns_text = "\n### 常见操作模式\n"
            for pattern in common_patterns[:5]:
                patterns_text += f"- {pattern}\n"

        return f"""## 候选技能已生成

从 {len(traces)} 条轨迹中提炼了候选技能。

### 提炼结果

**技能文件**: `workspace/skills/_candidates/{skill_name}/SKILL.md`
**覆盖任务类型**: {task_type_desc}
**常用工具**: {', '.join(f'`{t}`' for t, c in common_tools[:5])}
{patterns_text}
### 下一步

1. 审核生成的技能文件
2. 确认无误后，使用 `skill-refiner` 进一步完善
3. 确认可以发布后，将技能从 `_candidates/` 移到正式目录

> 注意: 候选技能不会自动加载到 Agent 的工作流中，只有移动到正式目录才会生效。"""

    def _extract_common_tools(self, traces: list[dict]) -> list[tuple[str, int]]:
        """提取常用工具"""
        tool_counts: dict[str, int] = {}
        for trace in traces:
            for tc in trace.get("execution", {}).get("tool_calls", []):
                tool_name = tc.get("tool", "unknown")
                tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

        # 排序返回
        return sorted(tool_counts.items(), key=lambda x: -x[1])

    def _extract_patterns(self, traces: list[dict]) -> list[str]:
        """提取常见操作模式"""
        patterns = []

        for trace in traces:
            tool_calls = trace.get("execution", {}).get("tool_calls", [])
            if not tool_calls:
                continue

            # 提取工具调用序列
            tool_sequence = [tc.get("tool", "?") for tc in tool_calls if tc.get("success")]
            if len(tool_sequence) >= 2:
                patterns.append(" → ".join(tool_sequence))

        # 统计最常见的模式
        pattern_counts: dict[str, int] = {}
        for p in patterns:
            pattern_counts[p] = pattern_counts.get(p, 0) + 1

        # 返回出现次数最多的模式
        sorted_patterns = sorted(pattern_counts.items(), key=lambda x: -x[1])
        return [p for p, c in sorted_patterns if c >= 2]

    def get_hooks(self) -> list[Hook]:
        """不注册自动 Hook"""
        return []
