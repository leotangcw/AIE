"""Using SuperWorkers Skill - 入口发现技能

让 Agent 发现 SuperWorkers 企业工作流体系。
类似 Superpowers 的 using-superpowers，作为入口引导 Agent 使用企业工作流。
"""

from typing import Any, Optional

from backend.modules.plugins.hooks import Hook


class UsingSuperWorkersSkill:
    """
    SuperWorkers 入口技能

    当 Agent 面临企业办公场景时激活，引导 Agent 进入 SuperWorkers 工作体系，
    使用知识检索、技能匹配、轨迹记录等企业工作流能力。
    """

    def __init__(self):
        self._active = False

    @property
    def name(self) -> str:
        return "using-superworkers"

    def should_activate(self, message: str) -> bool:
        """
        检查是否应该激活 SuperWorkers

        在以下场景激活：
        - 企业内部知识查询
        - 专业知识需求
        - 办公任务处理
        - 需要参考已有经验
        - 数据分析/报表/文档等企业常见任务
        """
        triggers = [
            # 企业知识相关
            "知识库", "企业知识", "内部文档", "wiki", "知识检索",
            "参考资料", "查找资料", "有没有相关的",
            # 技能相关
            "有没有技能", "怎么做", "操作流程", "SOP", "操作指导",
            # 企业任务相关
            "销售数据", "客户信息", "业务数据", "报表", "统计",
            "写报告", "写文档", "写方案", "整理数据", "汇总",
            # 经验相关
            "上次怎么做的", "之前的经验", "历史记录", "操作记录",
            # 显式触发
            "superworkers", "企业模式", "工作流",
        ]

        message_lower = message.lower()
        return any(trigger in message_lower for trigger in triggers)

    async def process(self, message: str, context: dict[str, Any]) -> Optional[str]:
        """
        激活 SuperWorkers 工作体系

        返回 SuperWorkers 的技能介绍和使用指引。
        """
        if not self._active:
            self._active = True
            return self._introduce_superworkers(message)
        return None

    def _introduce_superworkers(self, message: str) -> str:
        """介绍 SuperWorkers 工作体系"""
        return """## SuperWorkers 企业工作流已激活

你现在处于企业工作模式。SuperWorkers 提供了一套完整的企业工作流规范，帮助你更高效地完成企业任务。

### 可用工作流技能

**核心工作流** (企业任务时建议遵循):
1. **task-knowledge-review** - 任务前知识审查
   - 在执行企业任务前，先检查本地技能、检索企业知识，整理参考资料
   - 使用: 加载此技能了解完整的知识检索流程

**执行规范**:
2. **execution-standards** - 执行过程规范
   - 知识引用、错误处理、结果验证等执行规范
   - 使用: 加载此技能了解执行过程中的最佳实践

**经验进化** (人工触发):
3. **trace-analyzer** - 分析近期操作轨迹
   - 触发: "分析一下最近的轨迹" / "看看最近做得怎么样"
4. **skill-distiller** - 从轨迹提炼新技能
   - 触发: "把这个经验整理成技能" / "总结最佳实践"
5. **skill-refiner** - 优化已有技能
   - 触发: "优化一下xxx技能" / "不要这样做"

### 推荐工作流程

当你接到企业任务时，建议按以下步骤工作：

```
1. 分析任务 → 理解目标和涉及的领域
2. 查本地技能 → read_file 查看是否有匹配的本地技能
3. 查企业知识 → 使用 knowledge_retrieve 工具检索相关企业知识
4. 整理参考 → 将找到的技能和知识整理成参考材料
5. 执行任务 → 基于参考资料完成任务
6. 自动记录 → 操作轨迹会自动记录，无需手动操作
```

### 可用工具

- `knowledge_retrieve` - 检索企业知识库
- `knowledge_query_db` - 自然语言查询数据库
- `knowledge_web_search` - 搜索网络信息
- `list_skills` - 查看所有可用技能
- `read_file` - 读取技能完整内容

---

你可以直接开始工作，SuperWorkers 会在后台自动记录你的操作轨迹。
如果需要深入使用某项能力，可以加载对应的技能获取详细指引。"""

    def get_hooks(self) -> list[Hook]:
        """入口技能不注册自动 Hook，由 Agent 自主发现"""
        return []


# 全局实例
_using_superworkers_skill = UsingSuperWorkersSkill()


def get_skill() -> UsingSuperWorkersSkill:
    """获取技能实例"""
    return _using_superworkers_skill
