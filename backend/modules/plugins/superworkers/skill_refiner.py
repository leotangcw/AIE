"""Skill Refiner Skill - 优化已有技能

人工触发的技能，根据用户反馈优化已有的技能。
触发方式: "优化一下xxx技能" / "不要这样做" / "修改技能"
"""

from typing import Any, Optional
from datetime import datetime

from loguru import logger
from backend.modules.plugins.hooks import Hook


class SkillRefinerSkill:
    """
    技能优化技能

    根据用户反馈修改已有技能：
- 优化候选技能（从 _candidates 目录）
- 修改正式技能（从正式 skills 目录）
- 基于失败轨迹识别技能缺陷
    """

    @property
    def name(self) -> str:
        return "skill-refiner"

    def should_activate(self, message: str) -> bool:
        """人工触发"""
        triggers = [
            "优化技能", "修改技能", "更新技能", "改进技能",
            "不要这样做", "这个技能不对", "技能有问题",
            "完善技能", "refine skill",
        ]
        message_lower = message.lower()
        return any(t in message_lower for t in triggers)

    async def process(self, message: str, context: dict[str, Any]) -> Optional[str]:
        """优化技能"""
        # 解析用户意图
        action = self._parse_action(message)

        if action == "list_candidates":
            return self._list_candidate_skills()
        elif action == "promote":
            return self._promote_skill(message)
        elif action == "list_skills":
            return self._list_available_skills()
        else:
            return self._get_refiner_guide()

    def _parse_action(self, message: str) -> str:
        """解析用户意图"""
        if any(t in message for t in ["候选", "candidate", "待审核"]):
            return "list_candidates"
        if any(t in message for t in ["发布", "通过", "approve", "确认发布"]):
            return "promote"
        if any(t in message for t in ["有哪些技能", "列出技能", "技能列表"]):
            return "list_skills"
        return "guide"

    def _get_refiner_guide(self) -> str:
        """获取技能优化指引"""
        return """## 技能优化指南

你可以对技能进行以下操作：

### 1. 查看候选技能
说 "查看候选技能" 可以看到所有待审核的自动提炼技能。

### 2. 发布候选技能
说 "发布技能 xxx" 可以将候选技能移动到正式目录。

### 3. 优化已有技能
直接描述你想要的修改，例如：
- "优化 sales-report 技能，增加数据验证步骤"
- "修改 morning_briefing 技能，去掉汇率部分"

### 4. 基于反馈改进
当操作失败时，你可以说：
- "不要这样做" → 分析最近失败轨迹，生成改进建议
- "这个技能有问题" → 列出可能的问题并建议修改方向

### 候选技能管理流程

```
自动提炼 → _candidates/ 目录 → 人工审核 → 移至正式目录 → 生效
```

### 注意事项

- 正式技能修改会立即生效
- 候选技能修改不会影响 Agent 行为
- 建议先在候选技能中测试，确认后再发布"""

    def _list_candidate_skills(self) -> str:
        """列出所有候选技能"""
        from backend.utils.paths import SKILLS_DIR
        candidates_dir = SKILLS_DIR / "_candidates"

        if not candidates_dir.exists():
            return "没有候选技能。使用 `skill-distiller` 从轨迹中提炼新技能。"

        candidates = []
        for skill_dir in sorted(candidates_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                content = skill_file.read_text(encoding="utf-8")
                # 提取标题和描述
                title = skill_dir.name
                description = ""
                for line in content.split("\n"):
                    if line.startswith("description:"):
                        description = line.split(":", 1)[1].strip().strip('"')
                    elif line.startswith("title:"):
                        title = line.split(":", 1)[1].strip().strip('"')

                candidates.append({
                    "name": skill_dir.name,
                    "title": title,
                    "description": description[:100],
                    "path": str(skill_file.relative_to(SKILLS_DIR)),
                })

        if not candidates:
            return "没有候选技能。使用 `skill-distiller` 从轨迹中提炼新技能。"

        result = f"## 候选技能列表 ({len(candidates)} 个)\n\n"
        for c in candidates:
            result += f"### {c['title']}\n"
            result += f"- **路径**: `{c['path']}`\n"
            result += f"- **描述**: {c['description']}\n"
            result += f"- **操作**: 说 \"发布技能 {c['name']}\" 来发布\n\n"

        return result

    def _promote_skill(self, message: str) -> str:
        """发布候选技能"""
        from backend.utils.paths import SKILLS_DIR
        import shutil

        candidates_dir = SKILLS_DIR / "_candidates"
        if not candidates_dir.exists():
            return "没有候选技能目录。"

        # 查找要发布的技能
        target_name = None
        for skill_dir in candidates_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            if skill_dir.name in message or any(
                part in message for part in skill_dir.name.split("-")
            ):
                target_name = skill_dir.name
                break

        if not target_name:
            # 列出可用的候选
            available = [d.name for d in candidates_dir.iterdir() if d.is_dir()]
            if available:
                return f"未找到匹配的候选技能。可用的候选技能:\n" + "\n".join(f"- {a}" for a in available)
            return "没有候选技能可发布。"

        source_dir = candidates_dir / target_name
        target_dir = SKILLS_DIR / target_name

        if target_dir.exists():
            return f"正式目录中已存在同名技能 `{target_name}`。请先删除或重命名。"

        try:
            shutil.copytree(str(source_dir), str(target_dir))
            # 从 candidates 中删除
            shutil.rmtree(str(source_dir))

            return f"""## 技能已发布

**{target_name}** 已从候选目录移动到正式技能目录。

- **路径**: `workspace/skills/{target_name}/SKILL.md`
- **状态**: 已生效

该技能现在可以被 Agent 自动发现和使用了。"""
        except Exception as e:
            return f"发布失败: {e}"

    def _list_available_skills(self) -> str:
        """列出所有可用技能"""
        from backend.utils.paths import SKILLS_DIR

        skills = []
        for skill_dir in sorted(SKILLS_DIR.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
                continue
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                content = skill_file.read_text(encoding="utf-8")
                title = skill_dir.name
                description = ""
                for line in content.split("\n"):
                    if line.startswith("title:"):
                        title = line.split(":", 1)[1].strip().strip('"')
                    elif line.startswith("description:"):
                        description = line.split(":", 1)[1].strip().strip('"')

                skills.append({"name": skill_dir.name, "title": title, "description": description[:80]})

        if not skills:
            return "没有找到任何技能。"

        result = f"## 可用技能列表 ({len(skills)} 个)\n\n"
        for s in skills:
            result += f"- **{s['title']}**: {s['description']}\n"

        return result

    def get_hooks(self) -> list[Hook]:
        """不注册自动 Hook"""
        return []
