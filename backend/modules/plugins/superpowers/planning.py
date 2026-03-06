"""Planning Skill - 任务规划技能

将设计文档转换为可执行的任务计划。
"""

from typing import Any, Optional

from backend.modules.plugins.hooks import Hook


class PlanningSkill:
    """
    任务规划技能

    帮助将设计转换为详细的实施计划。
    """

    def __init__(self):
        self._active_session: Optional[dict] = None

    @property
    def name(self) -> str:
        return "planning"

    def should_activate(self, message: str) -> bool:
        """
        检查是否应该激活规划

        Args:
            message: 用户消息

        Returns:
            bool: 是否激活
        """
        triggers = [
            "计划",
            "规划",
            "实施计划",
            "怎么实现",
            "实施步骤",
            "task list",
            "todo",
            "任务拆分",
        ]

        message_lower = message.lower()
        return any(trigger in message_lower for trigger in triggers)

    async def process(self, message: str, context: dict[str, Any]) -> Optional[str]:
        """
        处理规划请求

        Args:
            message: 用户消息
            context: 上下文

        Returns:
            str: 规划结果
        """
        if not self._active_session:
            return self._start_planning(message)
        else:
            return self._continue_planning(message)

    def _start_planning(self, message: str) -> str:
        """开始规划"""
        # 尝试提取设计内容
        design = message

        # 如果有之前的设计文档，使用它
        if len(message) < 200:
            # 可能是简短的请求，需要更多信息
            self._active_session = {
                "topic": message,
                "stage": "gathering",
            }

            return f"""## 任务规划

好的，让我们为「{message}」制定实施计划。

为了制定详细计划，请告诉我：

1. **设计文档**在哪个文件？（或直接粘贴设计内容）
2. **优先级**：哪些功能优先？
3. **时间要求**：有截止日期吗？
4. **团队情况**：谁负责哪些部分？

提供后我会生成详细的实施计划。"""

        else:
            # 有足够信息，直接规划
            return self._create_plan(message)

    def _continue_planning(self, message: str) -> str:
        """继续规划"""
        stage = self._active_session.get("stage", "gathering")

        if stage == "gathering":
            # 记录设计内容，进入创建阶段
            self._active_session["design"] = message
            self._active_session["stage"] = "creating"

            return self._create_plan(message)

        return ""

    def _create_plan(self, design: str) -> str:
        """创建实施计划"""
        # 分析设计，提取任务
        tasks = self._analyze_design(design)

        # 生成计划
        plan = self._generate_plan(tasks)

        # 清理会话
        self._active_session = None

        return plan

    def _analyze_design(self, design: str) -> list[dict]:
        """分析设计，提取任务"""
        tasks = []

        # 简单分析，提取可能的模块
        keywords = {
            "前端": ["frontend", "界面", "页面", "组件", "vue", "react"],
            "后端": ["backend", "api", "接口", "服务", "fastapi", "flask"],
            "数据库": ["database", "数据", "存储", "sql", "model"],
            "测试": ["test", "测试", "单元测试", "集成测试"],
            "部署": ["deploy", "部署", "docker", "ci", "cd"],
        }

        for category, patterns in keywords.items():
            if any(p in design.lower() for p in patterns):
                tasks.append({
                    "category": category,
                    "description": f"实现 {category} 功能",
                    "priority": "high" if category in ["后端", "前端"] else "medium",
                })

        # 默认任务
        if not tasks:
            tasks = [
                {"category": "后端", "description": "实现核心 API", "priority": "high"},
                {"category": "前端", "description": "实现用户界面", "priority": "high"},
                {"category": "测试", "description": "编写测试用例", "priority": "medium"},
                {"category": "部署", "description": "配置部署流程", "priority": "low"},
            ]

        return tasks

    def _generate_plan(self, tasks: list[dict]) -> str:
        """生成实施计划"""
        # 按优先级排序
        priority_order = {"high": 0, "medium": 1, "low": 2}
        tasks.sort(key=lambda x: priority_order.get(x["priority"], 3))

        # 分组
        by_priority = {"high": [], "medium": [], "low": []}
        for task in tasks:
            by_priority[task["priority"]].append(task)

        plan = """## 实施计划

### 任务概览

| 优先级 | 任务数 |
|--------|--------|
| 高 | {} |
| 中 | {} |
| 低 | {} |

---

### 详细计划

#### 🔴 高优先级

""".format(
            len(by_priority["high"]),
            len(by_priority["medium"]),
            len(by_priority["low"]),
        )

        for i, task in enumerate(by_priority["high"], 1):
            plan += f"{i}. **{task['category']}**: {task['description']}\n"

        plan += "\n#### 🟡 中优先级\n\n"
        for i, task in enumerate(by_priority["medium"], 1):
            plan += f"{i}. **{task['category']}**: {task['description']}\n"

        if by_priority["low"]:
            plan += "\n#### 🟢 低优先级\n\n"
            for i, task in enumerate(by_priority["low"], 1):
                plan += f"{i}. **{task['category']}**: {task['description']}\n"

        plan += """

---

### 实施建议

1. **分阶段交付**: 先完成高优先级任务，形成可用的最小版本
2. **每日站会**: 同步进度，及时调整计划
3. **Code Review**: 重要功能需要代码审查
4. **持续测试**: 每个任务完成后运行相关测试

---

是否需要我帮你开始执行第一个任务？
"""

        return plan

    def get_hooks(self) -> list[Hook]:
        """获取钩子"""
        return []


# 全局实例
_planning_skill = PlanningSkill()


def get_skill() -> PlanningSkill:
    """获取技能实例"""
    return _planning_skill
