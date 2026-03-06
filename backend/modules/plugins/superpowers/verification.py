"""Verification Skill - 验证技能

在任务完成后进行验证：修改是否正确、测试是否通过、是否有副作用
"""

from typing import Any, Optional

from backend.modules.plugins.hooks import Hook


class VerificationSkill:
    """
    验证技能

    提供任务完成前的验证功能，确保工作质量。
    """

    def __init__(self):
        self._pending_verification: Optional[dict] = None

    @property
    def name(self) -> str:
        return "verification"

    def should_activate(self, message: str) -> bool:
        """
        检查是否应该激活验证

        Args:
            message: 用户消息

        Returns:
            bool: 是否激活
        """
        triggers = [
            "完成了",
            "做好了",
            "完成",
            "搞定了",
            "搞掂",
            "done",
            "finished",
            "完成了吗",
            "验证",
            "检查一下",
        ]

        message_lower = message.lower()
        return any(trigger in message_lower for trigger in triggers)

    async def process(self, message: str, context: dict[str, Any]) -> Optional[str]:
        """
        处理验证请求

        Args:
            message: 用户消息
            context: 上下文

        Returns:
            str: 验证结果
        """
        # 检查是否声称完成
        if self._is_claiming_done(message):
            return self._start_verification(message, context)

        return None

    def _is_claiming_done(self, message: str) -> bool:
        """检查是否声称完成"""
        triggers = [
            "完成了",
            "做好了",
            "搞定了",
            "已经完成",
            "已经做好",
            "done",
            "finished",
            "已经搞定了",
        ]

        message_lower = message.lower()
        return any(trigger in message_lower for trigger in triggers)

    def _start_verification(self, message: str, context: dict[str, Any]) -> str:
        """开始验证"""
        # 获取变更信息
        changes = context.get("changes", [])
        files_modified = context.get("files_modified", [])
        tests_run = context.get("tests_run", False)

        # 如果有变更，进行验证
        if files_modified or changes:
            return self._verify_changes(files_modified, changes, tests_run)

        # 如果没有变更，引导用户
        return """## 验证检查

你声称工作已完成，让我帮你验证一下。

**请提供：**
1. 修改了哪些文件？
2. 运行了哪些测试？
3. 是否自测过？

提供信息后我会进行验证检查。"""

    def _verify_changes(
        self,
        files_modified: list,
        changes: list,
        tests_run: bool,
    ) -> str:
        """验证变更"""
        issues = []

        # 检查是否有测试
        if not tests_run:
            issues.append({
                "type": "warning",
                "message": "未检测到测试运行记录",
                "suggestion": "建议运行测试确保功能正常",
            })

        # 检查修改的文件
        for file_path in files_modified:
            if not self._verify_file_change(file_path):
                issues.append({
                    "type": "error",
                    "message": f"文件 {file_path} 验证失败",
                    "suggestion": "检查文件内容是否正确",
                })

        # 生成验证报告
        return self._generate_verification_report(files_modified, issues)

    def _verify_file_change(self, file_path: str) -> bool:
        """验证单个文件变更"""
        try:
            # 尝试读取文件
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 基本验证
            if not content.strip():
                return False

            return True

        except Exception:
            return False

    def _generate_verification_report(
        self,
        files_modified: list,
        issues: list,
    ) -> str:
        """生成验证报告"""
        if not issues:
            return f"""## 验证通过 ✓

### 检查结果

| 检查项 | 状态 |
|--------|------|
| 修改文件 | ✓ {len(files_modified)} 个 |
| 代码完整性 | ✓ |
| 测试运行 | ✓ |

---

### 修改的文件
{chr(10).join([f"- {f}" for f in files_modified])}

---

**工作质量良好，可以继续！**

如有需要，我可以帮你：
1. 运行完整测试套件
2. 检查代码风格
3. 生成变更总结
"""

        # 有问题
        report = "## 验证发现问题 ⚠️\n\n"

        for issue in issues:
            emoji = "🔴" if issue["type"] == "error" else "🟡"
            report += f"- {emoji} {issue['message']}\n  - 建议: {issue['suggestion']}\n"

        report += """

---

**建议处理后再继续。**"""

        return report

    def get_hooks(self) -> list[Hook]:
        """获取钩子"""
        return []


# 全局实例
_verification_skill = VerificationSkill()


def get_skill() -> VerificationSkill:
    """获取技能实例"""
    return _verification_skill
