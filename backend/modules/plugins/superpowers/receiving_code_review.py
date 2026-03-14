"""Receiving Code Review Skill - 接收代码审查反馈技能

在收到代码审查反馈时使用，特别是当反馈不清晰或技术上有问题时。
要求技术严谨性验证，而不是表面同意或盲目实现。
"""

import re
from typing import Any, Optional

from backend.modules.plugins.hooks import Hook


class ReceivingCodeReviewSkill:
    """
    接收代码审查反馈技能

    核心原则：在实现之前验证。提问而不是假设。技术正确性高于社交舒适。
    """

    def __init__(self):
        self._active_review: Optional[dict] = None

    @property
    def name(self) -> str:
        return "receiving-code-review"

    def should_activate(self, message: str) -> bool:
        """
        检查是否应该激活接收代码审查模式
        """
        triggers = [
            "review",
            "审查意见",
            "反馈",
            "修改意见",
            "建议",
            "comment",
            "pr意见",
            "代码问题",
            "需要修改",
            "这个不对",
            "should fix",
            "please fix",
        ]

        message_lower = message.lower()
        return any(trigger in message_lower for trigger in triggers)

    async def process(self, message: str, context: dict[str, Any]) -> Optional[str]:
        """
        处理代码审查反馈
        """
        # 分析反馈内容
        return self._process_review_feedback(message, context)

    def _process_review_feedback(self, message: str, context: dict[str, Any]) -> str:
        """
        处理审查反馈的响应模式

        1. 阅读完整反馈，不要立即反应
        2. 理解：用自己话复述要求（或提问）
        3. 验证：检查代码库实际情况
        4. 评估：对这个代码库技术上是否合理？
        5. 响应：技术确认或合理反驳
        6. 实现：一次一个，逐个测试
        """
        # 检查是否有不清晰的反馈
        unclear_patterns = [
            "不清晰",
            "不清楚",
            "不太明白",
            "什么意思",
            "如何",
            "怎么",
            "为什么",
            "unclear",
            "not clear",
            "what do you mean",
        ]

        has_unclear = any(p in message.lower() for p in unclear_patterns)

        if has_unclear:
            return self._handle_unclear_feedback(message)

        # 检查是否是外部审查员反馈
        is_external = context.get("is_external_reviewer", False)

        if is_external:
            return self._handle_external_feedback(message, context)

        # 处理人类合作伙伴的反馈
        return self._handle_human_feedback(message, context)

    def _handle_unclear_feedback(self, message: str) -> str:
        """处理不清晰的反馈"""
        return """## ⚠️ 反馈不清晰

我注意到有些反馈不够清晰。在理解完整内容之前，我不应该盲目实现。

### 建议

请澄清以下内容后再继续：
1. 具体要修改什么？
2. 期望的结果是什么？
3. 有什么技术约束？

### 为什么需要澄清？

因为：
- 项目之间可能有依赖关系
- 部分理解 = 错误实现
- 错误的实现会浪费时间返工

### 示例

```
人类: "修复 1-6"
我理解了 1,2,3,6。但对 4,5 不清楚。

❌ 错误：立即实现 1,2,3,6，之后再问 4,5
✅ 正确："我理解 1,2,3,6。在理解 4 和 5 之前无法继续"
```

请提供更多细节，我会继续处理。"""

    def _handle_external_feedback(self, message: str, context: dict[str, Any]) -> str:
        """处理外部审查员反馈"""
        return """## 📋 外部审查反馈

收到外部审查员的反馈。在实现之前，我需要：

### 验证清单

- [ ] 技术上对这个代码库是否正确？
- [ ] 是否会破坏现有功能？
- [ ] 理解当前实现的原因了吗？
- [ ] 是否适用于所有平台/版本？
- [ ] 审查员是否了解完整上下文？

### 如果建议看起来有问题

**应该反驳的情况：**
- 建议破坏现有功能
- 审查员缺乏完整上下文
- 违反 YAGNI（未使用的功能）
- 对这个技术栈不正确
- 存在遗留/兼容原因
- 与人类的架构决策冲突

### 正确的回应方式

```
✅ "我检查了...实际上是这样...需要确认..."
✅ "这个建议会破坏 XXX 功能，是否继续？"
✅ "grep 代码库发现这个端点没有被调用，删除（YAGNI）？"
```

### 禁止的回应

```
❌ "你说得完全对！"
❌ "好建议！"
❌ "谢谢反馈！"
❌ "我马上实现"
```

**记住：先验证，再实现。技术严谨性始终优先。**"""

    def _handle_human_feedback(self, message: str, context: dict[str, Any]) -> str:
        """处理人类合作伙伴的反馈"""
        return """## 📝 收到审查反馈

好的，我收到了审查反馈。

### 我的处理方式

1. **阅读完整反馈** - 不会立即反应
2. **理解要求** - 用自己的话复述
3. **验证** - 检查代码库实际情况
4. **评估** - 技术上是否合理
5. **响应** - 技术确认或合理反驳
6. **实现** - 一次一个，逐个测试

### 如果有问题

- **不清晰的反馈**：我会先提问
- **技术上有问题**：我会用技术理由反驳
- **建议正确**：直接修复，用代码说话

### 正确示例

```
✅ "已修复。修改了 XXX"
✅ "好发现 - 具体问题在 XXX 处已修复"
❌ "你说得完全对！"
❌ "谢谢！"
```

**感谢的话不用说。代码本身就是最好的回应。**

---

请告诉我审查反馈的具体内容，我会逐一处理。"""

    def get_hooks(self) -> list[Hook]:
        """获取钩子"""
        return []


# 全局实例
_receiving_code_review_skill = ReceivingCodeReviewSkill()


def get_skill() -> ReceivingCodeReviewSkill:
    """获取技能实例"""
    return _receiving_code_review_skill
