"""Execution Standards Skill - 执行过程规范

定义 Agent 在执行企业任务过程中应遵循的规范。
"""

from typing import Any, Optional

from backend.modules.plugins.hooks import Hook


class ExecutionStandardsSkill:
    """
    执行过程规范技能

    指导 Agent 在使用知识执行任务时的最佳实践。
    """

    @property
    def name(self) -> str:
        return "execution-standards"

    def should_activate(self, message: str) -> bool:
        """不自动激活，由 using-superworkers 指向"""
        return False

    async def process(self, message: str, context: dict[str, Any]) -> Optional[str]:
        """返回执行规范指引"""
        return self._get_standards_guide()

    def _get_standards_guide(self) -> str:
        """获取执行规范指引"""
        return """## 执行过程规范

在使用企业知识和技能执行任务时，遵循以下规范：

### 知识引用规范

1. **标注来源**: 使用企业知识时，简要标注知识来源
   - 正确: "根据销售手册第三章的规定..."
   - 正确: "参考知识库中的Q1数据分析报告..."
   - 避免: 直接使用知识内容而不提及来源

2. **区分事实与推测**:
   - 从知识库获取的信息标注为"根据企业知识..."
   - 基于模型自身知识的标注为"根据一般了解..."
   - 不确定的标注为"可能..."

3. **知识时效性**: 注意知识的时效性，优先使用最新的资料

### 错误处理规范

1. **知识不足时**:
   - 先尝试用不同关键词重新检索
   - 如果仍然找不到，明确告知用户"未在知识库中找到相关内容"
   - 可以建议用户补充相关知识源

2. **执行失败时**:
   - 记录失败原因
   - 尝试替代方案
   - 向用户说明情况和建议

3. **遇到矛盾信息时**:
   - 如果检索到的多条知识相互矛盾
   - 向用户说明存在矛盾，列出不同来源的观点
   - 建议用户确认哪条信息更准确

### 结果验证规范

1. **数据准确性**: 涉及数字、日期、名称等关键信息时，尽量通过工具验证
2. **逻辑一致性**: 检查输出内容是否与参考资料一致
3. **完整性**: 确认是否回答了用户的完整问题

### 操作轨迹说明

- 你的所有操作（工具调用、知识检索、执行过程）会被系统自动记录
- 这些记录用于后续的经验提炼和技能优化
- 你不需要手动记录，正常工作即可

### 与用户的交互规范

1. **主动汇报知识使用情况**: 如果检索到了重要的参考资料，简要告知用户
2. **知识缺失提醒**: 如果某个环节缺少相关知识，提醒用户可能需要补充
3. **过程透明**: 对于复杂的企业任务，简要说明你的执行思路"""

    def get_hooks(self) -> list[Hook]:
        """不注册自动 Hook"""
        return []
