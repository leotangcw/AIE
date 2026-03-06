"""Brainstorming Skill - 头脑风暴技能"""

import re
from typing import Any, Optional

from backend.modules.plugins.hooks import Hook


class BrainstormingSkill:
    """
    头脑风暴技能

    帮助用户将想法转化为完整的设计方案。
    通过提问来理解需求，提出多种方案供选择。
    """

    def __init__(self):
        self._active_session: Optional[dict] = None

    @property
    def name(self) -> str:
        return "brainstorming"

    def should_activate(self, message: str) -> bool:
        """
        检查是否应该激活头脑风暴

        Args:
            message: 用户消息

        Returns:
            bool: 是否激活
        """
        # 触发关键词
        triggers = [
            "头脑风暴",
            "帮我分析",
            "讨论一下",
            "如何设计",
            "方案选择",
            "应该怎么做",
            "最佳方案",
            "帮我看看",
            "给点建议",
        ]

        message_lower = message.lower()
        return any(trigger in message_lower for trigger in triggers)

    async def process(self, message: str, context: dict[str, Any]) -> Optional[str]:
        """
        处理头脑风暴

        Args:
            message: 用户消息
            context: 上下文

        Returns:
            str: 响应内容
        """
        # 检查是否是第一次触发
        if not self._active_session:
            return self._start_brainstorming(message)
        else:
            return self._continue_brainstorming(message)

    def _start_brainstorming(self, message: str) -> str:
        """开始头脑风暴"""
        self._active_session = {
            "topic": message,
            "questions": [],
            "approaches": [],
            "stage": "understanding",
        }

        return f"""## 头脑风暴会话开始

好的，让我们来讨论一下「{message}」。

为了更好地理解你的需求，我想先问你几个问题：

**请告诉我：**
1. 这个功能的**目标用户**是谁？
2. 需要解决什么**核心问题**？
3. 有哪些**约束条件**（如技术限制、时间要求等）？
4. 你认为成功的标准是什么？

请逐一回答，我们可以一步步完善这个设计。"""

    def _continue_brainstorming(self, message: str) -> str:
        """继续头脑风暴"""
        stage = self._active_session.get("stage", "understanding")

        if stage == "understanding":
            # 记录回答，进入方案阶段
            self._active_session["user_input"] = message
            self._active_session["stage"] = "exploring"

            return """明白了。让我基于这些信息，分析一下可能的方案：

## 方案分析

针对你的需求，我提出 **3 种不同方案**：

### 方案 A：简单直接
- 优点：实现快、风险低、易维护
- 缺点：功能有限、扩展性一般
- 适合：MVP或时间紧迫的场景

### 方案 B：平衡方案
- 优点：功能与复杂度平衡、可扩展
- 缺点：需要一定设计时间
- 适合：大多数企业应用

### 方案 C：完整方案
- 优点：功能全面、可扩展性强
- 缺点：复杂度高、开发周期长
- 适合：长期项目或有复杂需求

---

**请问：**
1. 你倾向于哪个方案？
2. 或者你想综合多个方案的优点？
3. 有什么需要我深入分析的？"""

        elif stage == "exploring":
            # 记录方案选择，进入设计阶段
            approach = self._analyze_approach(message)
            self._active_session["selected"] = approach
            self._active_session["stage"] = "designing"

            return f"""好的，你选择了**方案 {approach}**。

让我帮你完善这个方案的具体设计：

---

### {self._get_approach_name(approach)} 详细设计

请告诉我：
1. 你希望这个功能包含哪些**核心功能**？
2. 有什么特别的**交互要求**吗？
3. 需要和哪些**现有系统**集成？

回答后我会生成一份设计文档草稿。"""

        elif stage == "designing":
            # 生成设计文档
            self._active_session["design_input"] = message
            self._active_session["stage"] = "completed"

            topic = self._active_session.get("topic", "")
            design = self._generate_design(topic, message)

            # 清理会话
            self._active_session = None

            return design

        return ""

    def _analyze_approach(self, message: str) -> str:
        """分析用户选择的方案"""
        message_lower = message.lower()

        if "a" in message_lower or "简单" in message_lower or "mvp" in message_lower:
            return "A"
        elif "c" in message_lower or "完整" in message_lower or "全面" in message_lower:
            return "C"
        else:
            return "B"

    def _get_approach_name(self, approach: str) -> str:
        """获取方案名称"""
        names = {
            "A": "简单直接",
            "B": "平衡方案",
            "C": "完整方案",
        }
        return names.get(approach, "平衡方案")

    def _generate_design(self, topic: str, features: str) -> str:
        """生成设计文档"""
        return f"""## 设计文档

### 主题
{topic}

### 核心功能
{features}

### 技术建议

| 模块 | 建议 |
|------|------|
| 前端 | 使用 Vue 3 + TypeScript |
| 后端 | FastAPI + SQLAlchemy |
| 数据库 | PostgreSQL/SQLite |
| 部署 | Docker |

### 风险与缓解

1. **时间风险**: 采用敏捷开发，分阶段交付
2. **技术风险**: 先做技术验证(POC)
3. **需求变更**: 保持设计灵活性

---

设计文档已生成。是否需要我帮你制定具体的实施计划？
"""

    def get_hooks(self) -> list[Hook]:
        """获取钩子"""
        # 暂时不注册自动触发钩子，需要用户明确调用
        return []


# 全局实例
_brainstorming_skill = BrainstormingSkill()


def get_skill() -> BrainstormingSkill:
    """获取技能实例"""
    return _brainstorming_skill
