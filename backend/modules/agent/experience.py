"""AIE 经验学习系统 - 自动学习、积累Skills"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from loguru import logger

from backend.utils.paths import MEMORY_DIR, SKILLS_DIR


class WorkFeedback:
    """工作反馈 - 用于学习"""

    def __init__(
        self,
        task_description: str,          # 任务描述
        user_feedback: str,              # 用户反馈 (修改意见/评价)
        original_output: str,            # 原始输出
        final_output: str,              # 最终输出 (用户修改后)
        context: dict[str, Any] = None, # 额外上下文
    ):
        self.id = str(uuid.uuid4())
        self.task_description = task_description
        self.user_feedback = user_feedback
        self.original_output = original_output
        self.final_output = final_output
        self.context = context or {}
        self.created_at = datetime.now().isoformat()


class LearnedSkill:
    """学习到的技能"""

    def __init__(
        self,
        name: str,
        description: str,
        trigger_conditions: list[str],     # 触发条件
        action_steps: list[str],          # 操作步骤
        examples: list[dict] = None,     # 示例
        confidence: float = 0.0,          # 置信度 0-1
        source: str = "auto",             # 来源: auto/manual
        skill_id: str = None,
    ):
        self.id = skill_id or str(uuid.uuid4())
        self.name = name
        self.description = description
        self.trigger_conditions = trigger_conditions
        self.action_steps = action_steps
        self.examples = examples or []
        self.confidence = confidence
        self.source = source
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.usage_count = 0

    def to_markdown(self) -> str:
        """转换为 Markdown 格式"""
        md = f"""---
title: {self.name}
description: {self.description}
tags: [auto-learned, experience]
confidence: {self.confidence}
source: {self.source}
created: {self.created_at}
---

# {self.name}

{self.description}

## 触发条件
"""
        for cond in self.trigger_conditions:
            md += f"- {cond}\n"

        md += "\n## 操作步骤\n"
        for i, step in enumerate(self.action_steps, 1):
            md += f"{i}. {step}\n"

        if self.examples:
            md += "\n## 示例\n"
            for ex in self.examples:
                md += f"- 输入: {ex.get('input', '')}\n"
                md += f"  输出: {ex.get('output', '')}\n"

        md += f"\n---\n*置信度: {self.confidence:.0%} | 使用次数: {self.usage_count}*"
        return md

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "trigger_conditions": self.trigger_conditions,
            "action_steps": self.action_steps,
            "examples": self.examples,
            "confidence": self.confidence,
            "source": self.source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "usage_count": self.usage_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LearnedSkill":
        """从字典创建"""
        skill = cls(
            name=data["name"],
            description=data["description"],
            trigger_conditions=data.get("trigger_conditions", []),
            action_steps=data.get("action_steps", []),
            examples=data.get("examples", []),
            confidence=data.get("confidence", 0.0),
            source=data.get("source", "auto"),
            skill_id=data.get("id"),
        )
        skill.created_at = data.get("created_at", skill.created_at)
        skill.updated_at = data.get("updated_at", skill.updated_at)
        skill.usage_count = data.get("usage_count", 0)
        return skill


class ExperienceEngine:
    """经验学习引擎"""

    def __init__(self, storage_dir: Path = None):
        self.storage_dir = storage_dir or MEMORY_DIR / "experience"
        self.skills_dir = storage_dir or SKILLS_DIR / "learned"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)

        self.feedback_store = self.storage_dir / "feedbacks"
        self.skills_store = self.storage_dir / "skills"
        self.feedback_store.mkdir(parents=True, exist_ok=True)
        self.skills_store.mkdir(parents=True, exist_ok=True)

        self._learned_skills: dict[str, LearnedSkill] = {}
        self._load_skills()

    def _load_skills(self):
        """加载已学习的技能"""
        for file in self.skills_store.glob("*.json"):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                skill = LearnedSkill.from_dict(data)
                self._learned_skills[skill.id] = skill
            except Exception as e:
                logger.warning(f"Failed to load skill from {file}: {e}")
        logger.info(f"Loaded {len(self._learned_skills)} learned skills")

    def learn_from_feedback(self, feedback: WorkFeedback) -> Optional[LearnedSkill]:
        """从用户反馈中学习"""
        logger.info(f"Learning from feedback: {feedback.task_description[:50]}...")

        # 保存反馈
        feedback_file = self.feedback_store / f"{feedback.id}.json"
        feedback_file.write_text(
            json.dumps({
                "task_description": feedback.task_description,
                "user_feedback": feedback.user_feedback,
                "original_output": feedback.original_output,
                "final_output": feedback.final_output,
                "context": feedback.context,
                "created_at": feedback.created_at,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        # 使用 LLM 分析反馈并生成技能
        skill = self._analyze_and_generate_skill(feedback)
        if skill:
            self._save_skill(skill)
            logger.info(f"Learned new skill: {skill.name}")

        return skill

    def _analyze_and_generate_skill(self, feedback: WorkFeedback) -> Optional[LearnedSkill]:
        """分析反馈并生成技能 - 简化版，实际应该调用 LLM"""
        # 简化实现：基于反馈生成基本技能
        # 实际生产中应该调用 LLM 来分析

        # 提取关键信息
        task = feedback.task_description
        feedback_text = feedback.user_feedback
        final = feedback.final_output

        # 生成技能名称
        skill_name = self._extract_skill_name(task, feedback_text)

        # 生成触发条件
        triggers = self._extract_triggers(task)

        # 生成操作步骤
        steps = self._extract_steps(feedback_text, final)

        if not skill_name or not triggers:
            return None

        skill = LearnedSkill(
            name=skill_name,
            description=f"从反馈中学习: {task[:100]}",
            trigger_conditions=triggers,
            action_steps=steps,
            examples=[{
                "input": task,
                "output": final,
                "feedback": feedback_text
            }],
            confidence=0.6,  # 初始置信度
            source="auto",
        )

        return skill

    def _extract_skill_name(self, task: str, feedback: str) -> str:
        """提取技能名称"""
        # 简化实现
        if len(task) > 30:
            return f"技能-{task[:20]}"
        return f"技能-{task}"

    def _extract_triggers(self, task: str) -> list[str]:
        """提取触发条件"""
        triggers = []
        # 简化: 任务描述作为触发条件
        if task:
            triggers.append(task)
        return triggers[:3]  # 最多3个

    def _extract_steps(self, feedback: str, output: str) -> list[str]:
        """提取操作步骤"""
        steps = []
        # 简化: 基于输出生成步骤
        if output:
            steps.append(f"生成输出: {output[:100]}")
        if feedback:
            steps.append(f"根据反馈调整: {feedback[:100]}")
        return steps[:5]  # 最多5步

    def _save_skill(self, skill: LearnedSkill):
        """保存技能"""
        self._learned_skills[skill.id] = skill

        # 保存 JSON
        skill_file = self.skills_store / f"{skill.id}.json"
        skill_file.write_text(
            json.dumps(skill.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        # 保存 Markdown
        md_file = self.skills_dir / f"{skill.id}.md"
        md_file.write_text(skill.to_markdown(), encoding="utf-8")

    def get_skill(self, skill_id: str) -> Optional[LearnedSkill]:
        """获取技能"""
        return self._learned_skills.get(skill_id)

    def get_all_skills(self) -> list[LearnedSkill]:
        """获取所有技能"""
        return list(self._learned_skills.values())

    def get_skills_by_confidence(self, min_confidence: float = 0.0) -> list[LearnedSkill]:
        """按置信度获取技能"""
        return [s for s in self._learned_skills.values() if s.confidence >= min_confidence]

    def apply_skill(self, skill_id: str) -> bool:
        """应用技能 - 增加使用次数"""
        skill = self._learned_skills.get(skill_id)
        if skill:
            skill.usage_count += 1
            skill.updated_at = datetime.now().isoformat()
            self._save_skill(skill)
            return True
        return False

    def update_confidence(self, skill_id: str, delta: float):
        """更新技能置信度"""
        skill = self._learned_skills.get(skill_id)
        if skill:
            skill.confidence = max(0.0, min(1.0, skill.confidence + delta))
            skill.updated_at = datetime.now().isoformat()
            self._save_skill(skill)

    def export_skills_for_exchange(self) -> list[dict]:
        """导出技能用于交换 (脱敏)"""
        exported = []
        for skill in self._learned_skills.values():
            exported.append({
                "name": skill.name,
                "description": skill.description,
                "trigger_conditions": skill.trigger_conditions,
                "action_steps": skill.action_steps,
                "confidence": skill.confidence,
            })
        return exported


# 全局实例
_experience_engine: Optional[ExperienceEngine] = None


def get_experience_engine() -> ExperienceEngine:
    """获取经验引擎实例"""
    global _experience_engine
    if _experience_engine is None:
        _experience_engine = ExperienceEngine()
    return _experience_engine
