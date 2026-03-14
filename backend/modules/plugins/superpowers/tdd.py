"""Test-Driven Development (TDD) Skill - 测试驱动开发技能

先写测试，看它失败，写最少的代码让它通过。

核心原则：如果没有看到测试失败，你就不知道它是否测试了正确的东西。
"""

from typing import Any, Optional

from backend.modules.plugins.hooks import Hook


class TDDSkill:
    """
    测试驱动开发技能

    红-绿-重构循环：
    1. RED - 写一个失败的测试
    2. GREEN - 写最少的代码让测试通过
    3. REFACTOR - 重构改进代码
    """

    def __init__(self):
        self._active_tdd_session: Optional[dict] = None

    @property
    def name(self) -> str:
        return "test-driven-development"

    def should_activate(self, message: str) -> bool:
        """
        检查是否应该激活 TDD 模式
        """
        triggers = [
            "实现功能",
            "添加功能",
            "开发新功能",
            "修复 bug",
            "修改行为",
            "重构",
            "implement",
            "feature",
            "bug fix",
            "refactor",
            "tdd",
            "测试驱动",
        ]

        message_lower = message.lower()
        return any(trigger in message_lower for trigger in triggers)

    async def process(self, message: str, context: dict[str, Any]) -> Optional[str]:
        """
        处理 TDD 请求
        """
        if not self._active_tdd_session:
            return self._start_tdd_session(message)
        else:
            return self._continue_tdd_session(message, context)

    def _start_tdd_session(self, message: str) -> str:
        """开始 TDD 会话"""
        self._active_tdd_session = {
            "task": message,
            "stage": "red",  # red -> green -> refactor
            "test_written": False,
            "test_failed": False,
            "code_written": False,
            "tests_pass": False,
        }

        return """## 测试驱动开发 (TDD)

### 铁律
```
没有失败的测试就不能写生产代码
```

### 红-绿-重构循环

```
RED → GREEN → REFACTOR → RED → ...
```

---

### 第一步：RED - 写失败的测试

在写任何实现代码之前，先写一个测试来描述期望的行为。

**测试要求：**
- 一个行为（"and" 在名字里？拆分开）
- 清晰的名字描述行为
- 使用真实代码（除非不可避免才用 mock）

**Python 示例：**

```python
import pytest

def test_user_email_validation_rejects_empty():
    # Test: empty email should be rejected
    from app.models import User

    with pytest.raises(ValueError, match="Email is required"):
        User(email="")
```

---

### 第二步：验证 RED - 看到测试失败

**必须执行！不要跳过。**

```bash
pytest tests/test_user.py::test_user_email_validation_rejects_empty -v
```

确认：
- 测试失败（不是报错）
- 失败原因符合预期
- 失败是因为功能缺失（不是拼写错误）

**测试通过了？** 你在测试现有行为。修复测试。

---

### 第三步：GREEN - 写最少的代码

写最简单的代码让测试通过。

**不要：**
- 添加额外功能
- 重构其他代码
- "改进"超过测试范围

**Python 示例：**

```python
class User:
    def __init__(self, email: str):
        if not email or not email.strip():
            raise ValueError("Email is required")
        self.email = email
```

---

### 第四步：验证 GREEN - 看到测试通过

**必须执行！**

```bash
pytest tests/test_user.py::test_user_email_validation_rejects_empty -v
```

确认：
- 测试通过
- 其他测试仍然通过
- 输出干净（无错误、无警告）

---

### 第五步：REFACTOR - 重构改进

只有在 green 之后：
- 移除重复
- 改进名字
- 提取辅助函数

保持测试绿色。不要添加行为。

---

### 验证清单

完成工作前检查：

- [ ] 每个新函数/方法都有测试
- [ ] 在实现前看到每个测试失败
- [ ] 每个测试失败原因符合预期
- [ ] 写了最少的代码让每个测试通过
- [ ] 所有测试通过
- [ ] 输出干净
- [ ] 使用真实代码
- [ ] 覆盖边界情况和错误

---

### 这个任务

**任务：** {task}

请告诉我：
1. 你要实现的具体功能或修复的 bug 是什么？
2. 有哪些边界情况需要考虑？

回答后，我帮你开始 TDD 循环。
""".format(task=message)

    def _continue_tdd_session(self, message: str, context: dict[str, Any]) -> str:
        """继续 TDD 会话"""
        stage = self._active_tdd_session.get("stage", "red")

        if stage == "red":
            # 记录测试已写，进入验证阶段
            self._active_tdd_session["test_written"] = True
            self._active_tdd_session["test_description"] = message
            self._active_tdd_session["stage"] = "verify_red"

            return """## RED 阶段 - 测试已写

你描述的测试：
```
{message}
```

### 下一步：验证 RED

请运行测试命令并提供输出：

**Python/pytest:**
```bash
pytest tests/ -v  # 或特定测试文件
```

或者告诉我你使用的测试命令。

**我需要看到：**
- 测试失败（FAILED）
- 失败原因符合预期

只有看到测试失败，才能进入 GREEN 阶段写实现代码。
""".format(message=message)

        elif stage == "verify_red":
            # 用户提供了测试输出
            if self._analyze_test_output(message):
                self._active_tdd_session["test_failed"] = True
                self._active_tdd_session["stage"] = "green"

                return """## RED 验证通过 ✓

测试正确失败。现在可以写实现代码了。

### GREEN 阶段

根据你描述的测试，最少的实现代码应该是：

```python
# 在这里写最少的代码让测试通过
# 不要添加额外功能
# 不要"改进"
```

请写出实现代码，然后运行测试验证。
"""
            else:
                return """## 测试输出分析

我没有检测到测试失败。请确认：

1. 测试确实运行了吗？
2. 输出中是否有 FAILED？
3. 失败原因是功能缺失还是其他问题？

请提供完整的测试输出。
"""

        elif stage == "green":
            # 记录实现代码已写
            self._active_tdd_session["code_written"] = True
            self._active_tdd_session["stage"] = "verify_green"

            return """## GREEN 阶段 - 代码已写

你写的实现代码：
```
{code}
```

### 下一步：验证 GREEN

请运行测试命令：

```bash
pytest tests/ -v
```

**我需要看到：**
- 测试通过（PASSED）
- 没有新的测试失败

只有所有测试通过，才能进入 REFACTOR 或标记完成。
""".format(code=message[:500])

        elif stage == "verify_green":
            # 分析测试结果
            if self._analyze_test_output(message):
                self._active_tdd_session["tests_pass"] = True

                # 询问是否需要重构
                self._active_tdd_session["stage"] = "refactor_decision"

                return """## GREEN 验证通过 ✓

所有测试通过！

### 下一步？

1. **REFACTOR** - 需要重构改进代码吗？
2. **继续下一个** - 有更多功能要实现？
3. **完成** - 这个任务完成了？

请选择或描述下一步。
"""
            else:
                return """## 测试输出分析

测试没有全部通过。请：
1. 修复失败的测试
2. 提供完整的测试输出

只有所有测试通过才能继续。
"""

        elif stage == "refactor_decision":
            if any(word in message.lower() for word in ["重构", "refactor", "改进", "improve"]):
                self._active_tdd_session["stage"] = "refactor"
                return """## REFACTOR 阶段

请描述你想如何重构代码：
1. 移除什么重复？
2. 改进哪些名字？
3. 提取什么辅助函数？

重构后记得运行测试确认仍然通过。
"""
            elif any(word in message.lower() for word in ["完成", "done", "继续", "next"]):
                self._active_tdd_session = None
                return """## TDD 会话完成 ✓

恭喜！你已经完成了测试驱动开发循环。

### 总结
- 写了失败的测试 ✓
- 看到测试失败 ✓
- 写最少的代码让测试通过 ✓
- 验证测试通过 ✓

如有更多任务，继续使用 TDD 流程。
"""
            else:
                return "请告诉我下一步：重构、继续下一个任务、还是完成？"

        elif stage == "refactor":
            self._active_tdd_session["stage"] = "refactor_verify"
            return """## REFACTOR - 重构后验证

重构完成后，请运行测试确认：

```bash
pytest tests/ -v
```

所有测试仍然通过才能完成。
"""

        elif stage == "refactor_verify":
            if self._analyze_test_output(message):
                self._active_tdd_session = None
                return """## REFACTOR 完成 ✓

重构后测试仍然通过。

TDD 循环完成！如需继续其他任务，请告诉我。
"""
            else:
                return "重构后测试失败了，请修复并重新验证。"

        return "请继续 TDD 流程。"

    def _analyze_test_output(self, output: str) -> bool:
        """分析测试输出"""
        output_lower = output.lower()

        # 检查是否有 FAILED
        if "failed" in output_lower:
            # 提取失败数量
            import re
            match = re.search(r"(\d+)\s+failed", output_lower)
            if match:
                failed_count = int(match.group(1))
                return failed_count == 0

        # 检查是否全部通过
        if "passed" in output_lower:
            import re
            match = re.search(r"(\d+)\s+passed", output_lower)
            if match:
                passed_count = int(match.group(1))
                return passed_count > 0

        # 检查是否有错误
        if "error" in output_lower:
            return False

        # 没有明确的失败信息，假设通过
        return True

    def get_hooks(self) -> list[Hook]:
        """获取钩子"""
        return []


# 全局实例
_tdd_skill = TDDSkill()


def get_skill() -> TDDSkill:
    """获取技能实例"""
    return _tdd_skill
