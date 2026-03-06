"""Code Review Skill - 代码审查技能

提供代码审查功能：静态分析、安全检查、规范建议
"""

import re
from typing import Any, Optional

from backend.modules.plugins.hooks import Hook


class CodeReviewSkill:
    """
    代码审查技能

    帮助审查代码并提供改进建议。
    """

    def __init__(self):
        self._pending_review: Optional[dict] = None

    @property
    def name(self) -> str:
        return "code_review"

    def should_activate(self, message: str) -> bool:
        """
        检查是否应该激活代码审查

        Args:
            message: 用户消息

        Returns:
            bool: 是否激活
        """
        triggers = [
            "审查",
            "review",
            "检查代码",
            "代码审查",
            "帮我看看代码",
            "代码有没有问题",
        ]

        message_lower = message.lower()
        return any(trigger in message_lower for trigger in triggers)

    async def process(self, message: str, context: dict[str, Any]) -> Optional[str]:
        """
        处理代码审查请求

        Args:
            message: 用户消息
            context: 上下文

        Returns:
            str: 审查结果
        """
        if not self._pending_review:
            return self._start_review(message, context)
        else:
            return self._process_review(message)

    def _start_review(self, message: str, context: dict) -> str:
        """开始代码审查"""
        # 尝试从上下文获取代码
        code = context.get("last_code") or context.get("code")

        if code:
            return self._perform_review(code, message)
        else:
            # 需要用户先提供代码
            self._pending_review = {"request": message}

            return """## 代码审查

好的，请提供需要审查的代码。

**你可以：**
1. 直接粘贴代码
2. 指定文件路径（如 `backend/app.py`）
3. 描述想让我检查的具体模块

提供后我会从以下方面进行审查：
- 代码正确性
- 安全风险
- 性能问题
- 代码规范
- 最佳实践
"""

    def _process_review(self, message: str) -> str:
        """处理用户提供的代码"""
        # 尝试提取代码
        code = self._extract_code(message)

        if code:
            self._pending_review = None
            return self._perform_review(code, message)
        else:
            return "请提供代码或文件路径以便审查。"

    def _extract_code(self, text: str) -> Optional[str]:
        """从文本中提取代码"""
        # 尝试提取代码块
        code_block_pattern = r"```(?:\w+)?\n(.*?)```"
        matches = re.findall(code_block_pattern, text, re.DOTALL)

        if matches:
            return matches[0]

        # 如果没有代码块，尝试读取文件
        file_pattern = r"(?:文件|path|文件路径)[:\s]+([^\s]+)"
        match = re.search(file_pattern, text)

        if match:
            file_path = match.group(1)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass

        return None

    def _perform_review(self, code: str, context: str = "") -> str:
        """执行代码审查"""
        issues = []

        # 1. 安全检查
        issues.extend(self._check_security(code))

        # 2. 性能检查
        issues.extend(self._check_performance(code))

        # 3. 规范检查
        issues.extend(self._check_style(code))

        # 4. 最佳实践
        issues.extend(self._check_best_practices(code))

        # 生成报告
        return self._generate_review_report(code, issues)

    def _check_security(self, code: str) -> list[dict]:
        """检查安全风险"""
        issues = []

        # 检查硬编码密码
        if re.search(r'password\s*=\s*["\']', code, re.IGNORECASE):
            issues.append({
                "severity": "high",
                "category": "安全",
                "issue": "硬编码密码",
                "suggestion": "使用环境变量或配置管理密码",
                "line": self._find_line(code, r'password\s*='),
            })

        # 检查 SQL 注入风险
        if re.search(r'execute\s*\(\s*["\'].*\%s', code) and "format" not in code.lower():
            issues.append({
                "severity": "high",
                "category": "安全",
                "issue": "SQL 注入风险",
                "suggestion": "使用参数化查询",
                "line": self._find_line(code, r'execute\s*\('),
            })

        # 检查 eval 使用
        if re.search(r'\beval\s*\(', code):
            issues.append({
                "severity": "high",
                "category": "安全",
                "issue": "使用 eval()",
                "suggestion": "避免使用 eval，考虑其他方案",
                "line": self._find_line(code, r'\beval\s*\('),
            })

        # 检查命令注入
        if re.search(r'os\.system\s*\(|subprocess\.call\s*\(', code):
            issues.append({
                "severity": "medium",
                "category": "安全",
                "issue": "可能的命令注入",
                "suggestion": "验证和清理所有用户输入",
                "line": self._find_line(code, r'(?:os\.system|subprocess\.call)\s*\('),
            })

        return issues

    def _check_performance(self, code: str) -> list[dict]:
        """检查性能问题"""
        issues = []

        # 检查循环中的字符串拼接
        if "for " in code and "+=" in code:
            issues.append({
                "severity": "medium",
                "category": "性能",
                "issue": "循环中字符串拼接",
                "suggestion": "使用 list + join() 或 f-string",
                "line": self._find_line(code, r'\+=.*"'),
            })

        # 检查未关闭的文件
        if "open(" in code and "with open" not in code:
            issues.append({
                "severity": "low",
                "category": "性能",
                "issue": "文件未使用 with 打开",
                "suggestion": "使用 with 语句确保文件关闭",
                "line": self._find_line(code, r'open\s*\('),
            })

        # 检查重复查询
        if code.count("SELECT") > 1 or code.count("query") > 2:
            issues.append({
                "severity": "medium",
                "category": "性能",
                "issue": "可能的重复数据库查询",
                "suggestion": "考虑合并查询或使用缓存",
                "line": None,
            })

        return issues

    def _check_style(self, code: str) -> list[dict]:
        """检查代码风格"""
        issues = []

        lines = code.split("\n")

        # 检查长行
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                issues.append({
                    "severity": "low",
                    "category": "风格",
                    "issue": f"行过长 ({len(line)} 字符)",
                    "suggestion": "将行长度控制在 120 以内",
                    "line": i,
                })
                break  # 只报告第一个

        # 检查行尾空格
        if any(line.rstrip() != line for line in lines):
            issues.append({
                "severity": "low",
                "category": "风格",
                "issue": "行尾有空格",
                "suggestion": "移除行尾空格",
                "line": None,
            })

        # 检查缺少文档字符串
        if "def " in code and '"""' not in code and "'''" not in code:
            issues.append({
                "severity": "low",
                "category": "风格",
                "issue": "函数缺少文档字符串",
                "suggestion": "添加 docstring 说明函数用途",
                "line": self._find_line(code, r'def\s+\w+'),
            })

        return issues

    def _check_best_practices(self, code: str) -> list[dict]:
        """检查最佳实践"""
        issues = []

        # 检查 bare except
        if re.search(r'except\s*:\s*$', code, re.MULTILINE):
            issues.append({
                "severity": "medium",
                "category": "最佳实践",
                "issue": "使用裸 except",
                "suggestion": "指定具体异常类型",
                "line": self._find_line(code, r'except\s*:\s*$'),
            })

        # 检查 print 调试
        if re.search(r'\bprint\s*\(', code):
            issues.append({
                "severity": "low",
                "category": "最佳实践",
                "issue": "使用 print 调试",
                "suggestion": "使用日志模块 (loguru)",
                "line": self._find_line(code, r'\bprint\s*\('),
            })

        # 检查 TODO
        if "TODO" in code or "FIXME" in code:
            issues.append({
                "severity": "low",
                "category": "最佳实践",
                "issue": "代码中有 TODO/FIXME",
                "suggestion": "确保 TODO 已被处理或记录在 issues 中",
                "line": None,
            })

        # 检查可变默认参数
        if re.search(r'def\s+\w+\s*\([^)]*=\s*\[\]', code):
            issues.append({
                "severity": "medium",
                "category": "最佳实践",
                "issue": "使用可变默认参数",
                "suggestion": "使用 None 作为默认值，在函数内创建新列表",
                "line": self._find_line(code, r'=\s*\[\]'),
            })

        return issues

    def _find_line(self, code: str, pattern: str) -> Optional[int]:
        """查找匹配行号"""
        match = re.search(pattern, code)
        if match:
            return code[:match.start()].count("\n") + 1
        return None

    def _generate_review_report(self, code: str, issues: list[dict]) -> str:
        """生成审查报告"""
        if not issues:
            return """## 代码审查完成 ✓

未发现明显问题！

### 总结
- 代码结构良好
- 未发现明显的安全风险
- 符合基本编码规范

---

如需进一步优化，可以考虑：
1. 添加更多单元测试
2. 增加代码注释
3. 提取重复代码为函数
"""

        # 按严重性排序
        severity_order = {"high": 0, "medium": 1, "low": 2}
        issues.sort(key=lambda x: severity_order.get(x["severity"], 3))

        # 统计
        stats = {
            "high": len([i for i in issues if i["severity"] == "high"]),
            "medium": len([i for i in issues if i["severity"] == "medium"]),
            "low": len([i for i in issues if i["severity"] == "low"]),
        }

        # 生成报告
        report = f"""## 代码审查报告

### 概要
| 严重 | 中等 | 建议 |
|------|------|------|
| {stats['high']} | {stats['medium']} | {stats['low']} |

---

### 发现的问题

"""

        for i, issue in enumerate(issues, 1):
            severity_emoji = {
                "high": "🔴",
                "medium": "🟡",
                "low": "🟢",
            }.get(issue["severity"], "⚪")

            line_info = f" (第 {issue['line']} 行)" if issue["line"] else ""

            report += f"""#### {i}. {severity_emoji} {issue['category']}: {issue['issue']}{line_info}

**问题**: {issue['issue']}
**建议**: {issue['suggestion']}

---

"""

        return report

    def get_hooks(self) -> list[Hook]:
        """获取钩子"""
        return []


# 全局实例
_code_review_skill = CodeReviewSkill()


def get_skill() -> CodeReviewSkill:
    """获取技能实例"""
    return _code_review_skill
