"""Debugging Skill - 调试技能

系统化调试：复现问题 → 收集证据 → 定位根因 → 验证修复
"""

import re
from typing import Any, Optional

from backend.modules.plugins.hooks import Hook


class DebuggingSkill:
    """
    系统化调试技能

    提供结构化的调试方法论，帮助定位和解决问题。
    """

    def __init__(self):
        self._active_session: Optional[dict] = None

    @property
    def name(self) -> str:
        return "debugging"

    def should_activate(self, message: str) -> bool:
        """
        检查是否应该激活调试模式

        Args:
            message: 用户消息

        Returns:
            bool: 是否激活
        """
        triggers = [
            "bug",
            "错误",
            "报错",
            "问题",
            "修复",
            "调试",
            "不工作",
            "失败",
            "exception",
            "traceback",
            "fix this",
            "not working",
        ]

        message_lower = message.lower()
        return any(trigger in message_lower for trigger in triggers)

    async def process(self, message: str, context: dict[str, Any]) -> Optional[str]:
        """
        处理调试请求

        Args:
            message: 用户消息
            context: 上下文

        Returns:
            str: 调试指导
        """
        # 检查是否有错误信息
        has_error = self._extract_error_info(message)

        if not self._active_session:
            return self._start_debugging(message, has_error)
        else:
            return self._continue_debugging(message)

    def _extract_error_info(self, message: str) -> dict[str, Any]:
        """提取错误信息"""
        error_info = {}

        # 提取错误类型
        error_types = ["ValueError", "TypeError", "AttributeError", "KeyError", "SyntaxError", "RuntimeError"]
        for err_type in error_types:
            if err_type in message:
                error_info["type"] = err_type
                break

        # 提取错误消息
        error_match = re.search(r"(?:Error|Exception):\s*(.+?)(?:\n|$)", message)
        if error_match:
            error_info["message"] = error_match.group(1)

        # 提取堆栈跟踪中的文件路径
        file_matches = re.findall(r'File "(.+?)"', message)
        if file_matches:
            error_info["files"] = file_matches

        # 提取行号
        line_matches = re.findall(r", line (\d+)", message)
        if line_matches:
            error_info["lines"] = [int(line) for line in line_matches]

        return error_info

    def _start_debugging(self, message: str, error_info: dict) -> str:
        """开始调试"""
        self._active_session = {
            "problem": message,
            "error_info": error_info,
            "evidence": [],
            "root_cause": None,
            "fix_attempts": [],
            "stage": "reproducing",
        }

        if error_info:
            # 有错误信息，进入分析阶段
            self._active_session["stage"] = "analyzing"
            return self._analyze_error(error_info)
        else:
            # 无错误信息，引导用户复现
            return self._guide_reproduction(message)

    def _guide_reproduction(self, problem: str) -> str:
        """引导用户复现问题"""
        return f"""## 系统化调试 - 复现问题

我理解你想要解决「{problem}」。

为了更好地帮助定位问题，请提供以下信息：

### 1. 问题表现
- 错误信息或异常（如有）
- 触发条件（什么操作会导致这个问题）
- 发生频率（每次必现还是偶发）

### 2. 环境信息
- 操作系统
- Python 版本
- 相关依赖版本

### 3. 尝试过的方案
- 已排除的可能原因
- 已尝试的修复方法

---

请尽可能详细地描述，我帮你分析根因。"""

    def _analyze_error(self, error_info: dict) -> str:
        """分析错误"""
        error_type = error_info.get("type", "未知错误")
        error_message = error_info.get("message", "无详细信息")
        files = error_info.get("files", [])
        lines = error_info.get("lines", [])

        file_info = ""
        if files and lines:
            file_details = list(zip(files[-2:], lines[-2:]))  # 取最后两个
            file_info = "\n".join([f"- `{f}`, 第 {l} 行" for f, l in file_details])

        analysis = self._get_error_analysis(error_type, error_message)

        self._active_session["stage"] = "hypothesizing"

        return f"""## 错误分析

### 错误类型
`{error_type}`

### 错误信息
```
{error_message}
```

### 代码位置
{file_info or "位置未知"}

### 初步分析
{analysis}

---

### 可能的根因

根据错误类型，我列出几个最可能的原因：

1. **主要原因**: {analysis.get("likely_cause", "需要更多信息")}
2. **次要原因**: {analysis.get("possible_cause", "可能是参数或状态问题")}

---

请问：
1. 这个错误是**首次出现**还是**之前就有**？
2. 你最近**修改了什么代码**？

确认后我会给出具体的修复建议。"""

    def _get_error_analysis(self, error_type: str, error_message: str) -> dict:
        """获取错误分析"""
        analyses = {
            "ValueError": {
                "likely_cause": "传入了无效的值或参数类型不匹配",
                "possible_cause": "函数参数验证逻辑有问题",
                "fix": "检查传入的参数值和类型是否正确",
            },
            "TypeError": {
                "likely_cause": "对不支持该操作的数据类型执行了操作",
                "possible_cause": "变量类型在运行时发生了变化",
                "fix": "检查变量的实际类型",
            },
            "AttributeError": {
                "likely_cause": "对象没有该属性或方法",
                "possible_cause": "对象初始化或导入有问题",
                "fix": "检查对象的类定义和导入",
            },
            "KeyError": {
                "likely_cause": "字典键不存在",
                "possible_cause": "数据结构初始化不完整",
                "fix": "使用 .get() 方法或先检查键是否存在",
            },
            "SyntaxError": {
                "likely_cause": "代码语法错误",
                "possible_cause": "括号、引号不匹配",
                "fix": "检查对应行的语法",
            },
            "RuntimeError": {
                "likely_cause": "运行时逻辑错误",
                "possible_cause": "条件判断或流程控制问题",
                "fix": "添加更多日志来定位问题",
            },
        }

        return analyses.get(error_type, {
            "likely_cause": "需要更多信息",
            "possible_cause": "可能是多种原因",
            "fix": "请提供更多上下文",
        })

    def _continue_debugging(self, message: str) -> str:
        """继续调试"""
        stage = self._active_session.get("stage", "reproducing")

        # 记录用户输入
        self._active_session["evidence"].append(message)

        if stage == "hypothesizing":
            # 用户确认了一些信息，进入修复建议
            return self._suggest_fix()

        elif stage == "fixing":
            # 验证修复
            return self._verify_fix(message)

        return "请提供更多关于问题的信息，以便我进一步分析。"

    def _suggest_fix(self) -> str:
        """建议修复方案"""
        error_type = self._active_session.get("error_info", {}).get("type", "")
        analysis = self._get_error_analysis(error_type, "")

        self._active_session["stage"] = "fixing"

        return f"""## 修复建议

### 推荐修复

根据分析，建议按以下步骤修复：

```python
# 1. 添加错误处理
try:
    # 可能出错的代码
    pass
except {error_type} as e:
    # 记录错误日志
    print(f"Error: {{e}}")
    # 优雅处理
    raise

# 2. 添加验证
def validate_input(data):
    if not data:
        raise ValueError("数据不能为空")
    return data
```

### 验证步骤

修复后请：
1. 运行测试确认问题已解决
2. 检查是否有副作用
3. 确认边界情况已处理

---

请尝试修复，然后告诉我结果。如果还有问题，继续分析。"""

    def _verify_fix(self, message: str) -> str:
        """验证修复"""
        # 检查用户是否确认修复成功
        if any(word in message.lower() for word in ["好了", "解决了", "成功", "fixed", "works"]):
            self._active_session = None
            return """## 调试完成

太好了，问题已经解决！

### 总结
- 问题类型: {}
- 根因: {}
- 修复方法: {}

如果以后遇到其他问题，随时可以找我调试。

---

是否需要我帮你把这次调试的经验记录下来？""".format(
                self._active_session.get("error_info", {}).get("type", "未知"),
                self._active_session.get("root_cause", "已修复"),
                "添加了错误处理和验证",
            )

        return "请尝试修复后告诉我结果，或者描述还有哪些问题。"

    def get_hooks(self) -> list[Hook]:
        """获取钩子"""
        return []


# 全局实例
_debugging_skill = DebuggingSkill()


def get_skill() -> DebuggingSkill:
    """获取技能实例"""
    return _debugging_skill
