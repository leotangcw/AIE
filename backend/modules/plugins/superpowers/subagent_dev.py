"""Subagent-Driven Development Skill - 子代理驱动开发技能

通过为每个任务分发新的子代理来执行计划，包含两阶段审查：规格合规审查，然后代码质量审查。

核心原则：每个任务新子代理 + 两阶段审查 = 高质量、快速迭代
"""

from typing import Any, Optional

from backend.modules.plugins.hooks import Hook


class SubagentDevSkill:
    """
    子代理驱动开发技能

    执行计划时，为每个任务分发新的子代理，包含：
    1. 实现者子代理 - 执行任务
    2. 规格审查子代理 - 验证实现符合规格
    3. 代码质量审查子代理 - 验证代码质量
    """

    def __init__(self):
        self._session: Optional[dict] = None

    @property
    def name(self) -> str:
        return "subagent-driven-development"

    def should_activate(self, message: str) -> bool:
        """
        检查是否应该激活
        """
        triggers = [
            "子代理开发",
            "并行开发",
            "多任务执行",
            "批量实现",
            "subagent",
            "多个任务",
            "implement",
            "execute plan",
            "multiple tasks",
        ]

        message_lower = message.lower()
        return any(trigger in message_lower for trigger in triggers)

    async def process(self, message: str, context: dict[str, Any]) -> Optional[str]:
        """
        处理子代理开发请求

        流程：
        1. 读取计划，提取所有任务
        2. 为每个任务分发实现子代理
        3. 规格审查（第一阶段）
        4. 代码质量审查（第二阶段）
        5. 重复直到所有任务完成
        """
        if not self._session:
            return self._start_subagent_dev(message, context)
        else:
            return self._continue_subagent_dev(message, context)

    def _start_subagent_dev(self, message: str, context: dict[str, Any]) -> str:
        """开始子代理驱动开发"""
        self._session = {
            "task": message,
            "stage": "read_plan",  # read_plan -> implement -> spec_review -> quality_review -> next
            "tasks": [],
            "current_task_index": 0,
            "task_results": [],
        }

        return """## 子代理驱动开发

### 核心原则

每个任务新子代理 + 两阶段审查 = 高质量、快速迭代

### 流程

```
1. 读取计划，提取所有任务
2. 分发实现子代理（每个任务）
3. 规格审查子代理（第一阶段）
4. 代码质量审查子代理（第二阶段）
5. 标记任务完成
6. 重复直到所有任务完成
7. 最终代码审查
```

### 第一步：提取任务

请提供你的实现计划，描述：

1. **所有任务列表** - 列出需要完成的每个任务
2. **任务描述** - 每个任务的详细说明
3. **上下文** - 任务之间的依赖关系和上下文

### 或者

告诉我你有一个计划文件（路径），我会读取并提取任务。
"""

    def _continue_subagent_dev(self, message: str, context: dict[str, Any]) -> str:
        """继续子代理开发"""
        stage = self._session.get("stage", "read_plan")

        if stage == "read_plan":
            return self._parse_tasks(message)
        elif stage == "implement":
            return self._dispatch_implementer(message, context)
        elif stage == "spec_review":
            return self._spec_review(message, context)
        elif stage == "quality_review":
            return self._quality_review(message, context)
        elif stage == "next":
            return self._next_task(message, context)

        return "请继续子代理开发流程。"

    def _parse_tasks(self, message: str) -> str:
        """解析任务列表"""
        # 简单解析 - 按行或数字提取任务
        import re

        tasks = []
        lines = message.split("\n")

        current_task = ""
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检测任务开始（数字或项目符号）
            if re.match(r"^[\d\d*\-]\.?\s+", line) or re.match(r"^-\s+", line):
                if current_task:
                    tasks.append(current_task)
                # 提取任务描述
                current_task = re.sub(r"^[\d\*\-]+\.?\s+", "", line)
            elif current_task:
                current_task += " " + line

        if current_task:
            tasks.append(current_task)

        # 如果没有检测到任务，将整个消息作为单个任务
        if not tasks:
            tasks = [message]

        self._session["tasks"] = tasks
        self._session["stage"] = "implement"

        return self._show_tasks_summary(tasks)

    def _show_tasks_summary(self, tasks: list) -> str:
        """显示任务摘要"""
        summary = f"""## 任务列表

共发现 **{len(tasks)}** 个任务：

"""

        for i, task in enumerate(tasks, 1):
            summary += f"{i}. {task}\n"

        summary += """
---

### 下一步

对于每个任务，我将：
1. **分发实现子代理** - 执行任务
2. **规格审查** - 验证符合规格
3. **代码质量审查** - 验证代码质量
4. **标记完成** - 进入下一个任务

### 开始第一个任务

任务 1: **{tasks[0]}**

请确认开始实现，或者告诉我你想调整任务列表。
""".format(tasks=tasks)

        return summary

    def _dispatch_implementer(self, message: str, context: dict[str, Any]) -> str:
        """分发实现子代理"""
        tasks = self._session.get("tasks", [])
        current_index = self._session.get("current_task_index", 0)

        if current_index >= len(tasks):
            return "所有任务已完成！"

        current_task = tasks[current_index]
        self._session["stage"] = "spec_review"

        return f"""## 任务 {current_index + 1}：实现

### 任务
{current_task}

### 分发实现子代理

我将使用子代理来执行这个任务。子代理会：
1. 实现任务描述的功能
2. 编写测试
3. 运行测试确认通过
4. 自我审查

### 子代理提示词

```
你是一个实现专家。请完成以下任务：

{current_task}

要求：
- 先写测试，再写实现（测试驱动开发）
- 完成后运行测试确认
- 简要总结你做了什么
```

### 执行

请确认，我可以：
1. **直接执行** - 我使用内部子代理执行
2. **提供提示词** - 你提供更详细的实现指导

你想怎么做？
"""

    def _spec_review(self, message: str, context: dict[str, Any]) -> str:
        """规格审查"""
        self._session["stage"] = "quality_review"

        tasks = self._session.get("tasks", [])
        current_index = self._session.get("current_task_index", 0)
        current_task = tasks[current_index]

        return f"""## 任务 {current_index + 1}：规格审查（第一阶段）

### 审查内容

任务：{current_task}

### 审查清单

请验证：
- [ ] 实现满足任务描述的所有要求
- [ ] 没有添加规格之外的功能
- [ ] 测试覆盖了核心功能

### 审查者提示词

```
你是一个规格审查专家。请审查实现是否符合规格：

任务：{current_task}

检查：
1. 所有需求是否实现？
2. 是否有遗漏？
3. 是否有额外功能？
```

### 请审查

请提供审查结果：
- **通过** - 规格符合
- **有问题** - 列出具体问题
"""

    def _quality_review(self, message: str, context: dict[str, Any]) -> str:
        """代码质量审查"""
        self._session["stage"] = "next"

        tasks = self._session.get("tasks", [])
        current_index = self._session.get("current_task_index", 0)

        return f"""## 任务 {current_index + 1}：代码质量审查（第二阶段）

### 审查内容

### 审查清单

请验证：
- [ ] 代码质量良好
- [ ] 无明显问题
- [ ] 无安全风险

### 审查者提示词

```
你是一个代码质量审查专家。请审查代码质量：

检查：
1. 代码是否清晰易读？
2. 是否有明显问题？
3. 是否有安全风险？
4. 是否有性能问题？
```

### 请审查

请提供审查结果：
- **通过** - 代码质量良好
- **有问题** - 列出具体问题
"""

    def _next_task(self, message: str, context: dict[str, Any]) -> str:
        """进入下一个任务"""
        tasks = self._session.get("tasks", [])
        current_index = self._session.get("current_task_index", 0)

        # 记录当前任务结果
        self._session["task_results"].append({
            "task": tasks[current_index],
            "status": "completed",
        })

        # 移动到下一个任务
        current_index += 1

        if current_index >= len(tasks):
            # 所有任务完成
            return self._final_review(context)
        else:
            self._session["current_task_index"] = current_index
            self._session["stage"] = "implement"

            return f"""## 任务 {current_index} 完成 ✓

任务 {current_index} 已完成，进入下一个任务。

### 剩余任务

还剩 **{len(tasks) - current_index}** 个任务：

"""

    def _final_review(self, context: dict[str, Any]) -> str:
        """最终审查"""
        tasks = self._session.get("tasks", [])
        results = self._session.get("task_results", [])

        summary = """## 开发完成 ✓

### 完成摘要

共完成 **{total}** 个任务：

""".format(total=len(tasks))

        for i, result in enumerate(results, 1):
            summary += f"{i}. {result['task']} - {result['status']}\n"

        summary += """
### 下一步

1. **运行完整测试** - 确认所有测试通过
2. **代码审查** - 最终代码审查
3. **完成分支** - 使用 `finishing-a-development-branch` 技能

请选择下一步。
"""

        # 清理会话
        self._session = None

        return summary

    def get_hooks(self) -> list[Hook]:
        """获取钩子"""
        return []


# 全局实例
_subagent_dev_skill = SubagentDevSkill()


def get_skill() -> SubagentDevSkill:
    """获取技能实例"""
    return _subagent_dev_skill
