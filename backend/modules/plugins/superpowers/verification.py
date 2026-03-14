"""Verification Skill - 验证技能

在任务完成后进行验证：修改是否正确、测试是否通过、是否有副作用

核心原则：证据优先，声称完成前必须运行验证命令。
"""

import re
from typing import Any, Optional

from backend.modules.plugins.hooks import Hook


class VerificationSkill:
    """
    验证技能 - 证据优先原则

    声称工作完成但没有验证是欺骗，不是效率。
    铁律：没有新鲜验证证据就不能声称完成。
    """

    def __init__(self):
        self._pending_verification: Optional[dict] = None

    @property
    def name(self) -> str:
        return "verification"

    def should_activate(self, message: str) -> bool:
        """
        检查是否应该激活验证
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
            "应该没问题",
            "测试通过",
            "修复好了",
            "已经好了",
        ]

        message_lower = message.lower()
        return any(trigger in message_lower for trigger in triggers)

    async def process(self, message: str, context: dict[str, Any]) -> Optional[str]:
        """
        处理验证请求

        核心流程：
        1. IDENTIFY: 确定什么命令能证明这个声称
        2. RUN: 执行完整命令（新鲜的、完整的）
        3. READ: 完整输出，检查退出码，统计失败数
        4. VERIFY: 输出是否确认了声称？
           - 如果否：用证据说明实际状态
           - 如果是：用证据说明声称
        5. 只有这样才能做出声称
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
            "应该没问题",
            "修复好了",
        ]

        message_lower = message.lower()
        return any(trigger in message_lower for trigger in triggers)

    def _start_verification(self, message: str, context: dict[str, Any]) -> str:
        """
        开始验证 - 强调证据优先原则

        铁律：没有新鲜验证证据就不能声称完成
        """
        # 获取变更信息
        files_modified = context.get("files_modified", [])
        tests_run = context.get("tests_run", False)
        tool_calls = context.get("tool_calls", [])

        # 如果已经有验证证据，直接分析
        if self._has_verification_evidence(context):
            return self._analyze_verification_evidence(message, context)

        # 如果没有验证证据，引导用户提供
        return self._request_verification_evidence(message, files_modified, tool_calls)

    def _has_verification_evidence(self, context: dict[str, Any]) -> bool:
        """检查是否有验证证据"""
        # 检查是否有测试运行结果
        if context.get("test_results"):
            return True
        # 检查是否有构建结果
        if context.get("build_results"):
            return True
        # 检查是否有 linter 结果
        if context.get("lint_results"):
            return True
        return False

    def _analyze_verification_evidence(self, message: str, context: dict[str, Any]) -> str:
        """分析验证证据"""
        test_results = context.get("test_results")
        build_results = context.get("build_results")
        lint_results = context.get("lint_results")

        issues = []
        evidence_lines = []

        # 分析测试结果
        if test_results:
            if test_results.get("passed") and test_results.get("failed", 0) == 0:
                evidence_lines.append(f"✓ 测试通过: {test_results.get('passed')} passed")
            else:
                issues.append({
                    "type": "error",
                    "message": f"测试失败: {test_results.get('failed', 0)} failures",
                    "evidence": test_results.get("output", "")
                })

        # 分析构建结果
        if build_results:
            if build_results.get("success"):
                evidence_lines.append("✓ 构建成功")
            else:
                issues.append({
                    "type": "error",
                    "message": "构建失败",
                    "evidence": build_results.get("output", "")
                })

        # 分析 linter 结果
        if lint_results:
            if lint_results.get("errors", 0) == 0:
                evidence_lines.append(f"✓ Lint 通过: {lint_results.get('errors', 0)} errors")
            else:
                issues.append({
                    "type": "warning",
                    "message": f"Lint 警告: {lint_results.get('warnings', 0)} warnings",
                    "evidence": lint_results.get("output", "")
                })

        # 生成报告
        return self._generate_verification_report(message, evidence_lines, issues)

    def _request_verification_evidence(
        self,
        message: str,
        files_modified: list,
        tool_calls: list
    ) -> str:
        """
        请求验证证据 - 强调必须运行验证命令

        这是验证的核心铁律：声称完成必须伴随新鲜的验证证据
        """

        # 分析可能的验证命令
        verification_commands = self._suggest_verification_commands(files_modified, tool_calls)

        return f"""## 验证检查 - 证据优先

⚠️ **重要：声称完成需要验证证据**

你没有提供验证证据。根据验证技能的铁律：
> **没有新鲜验证证据就不能声称完成**

### 声称的内容
"{message}"

### 需要验证

{verification_commands}

### 为什么需要验证？

从历史经验中：
- 人类合作伙伴说"我不相信你" - 信任被破坏
- 未定义的函数被发货 - 会崩溃
- 缺失的需求被发货 - 功能不完整
- 虚假完成浪费时间 → 重定向 → 返工

### 正确示例

✅ 运行测试命令 → 看到 34/34 通过 → "所有测试通过"
❌ "应该通过了" / "看起来正确"

### 请执行

请运行上述验证命令，然后告诉我结果。
只有提供新鲜的验证证据后，才能声称工作完成。"""

    def _suggest_verification_commands(
        self,
        files_modified: list,
        tool_calls: list
    ) -> str:
        """建议验证命令"""
        commands = []

        # 根据文件类型建议命令
        has_python = any(f.endswith('.py') for f in files_modified)
        has_js = any(f.endswith('.js') or f.endswith('.ts') for f in files_modified)
        has_rust = any(f.endswith('.rs') for f in files_modified)
        has_go = any(f.endswith('.go') for f in files_modified)

        if has_python:
            commands.append("- `pytest` 或 `python -m pytest` - 运行 Python 测试")

        if has_js:
            commands.append("- `npm test` - 运行 JavaScript/TypeScript 测试")
            commands.append("- `npm run build` - 构建项目")

        if has_rust:
            commands.append("- `cargo test` - 运行 Rust 测试")
            commands.append("- `cargo build` - 构建项目")

        if has_go:
            commands.append("- `go test ./...` - 运行 Go 测试")
            commands.append("- `go build` - 构建项目")

        # 检查是否有测试运行
        has_test_run = any(
            'test' in str(tc).lower()
            for tc in tool_calls
        )

        if has_test_run:
            commands.append("- 看起来你已经运行过测试，请提供测试输出")

        if not commands:
            commands.append("- 请描述你已执行的验证步骤")

        return "\n".join(commands)

    def _generate_verification_report(
        self,
        message: str,
        evidence_lines: list,
        issues: list
    ) -> str:
        """生成验证报告"""

        if not issues and evidence_lines:
            # 完全通过
            report = """## 验证通过 ✓

### 证据

"""
            for line in evidence_lines:
                report += f"- {line}\n"

            report += f"""
### 声称
"{message}"

---
**验证确认：工作质量良好，可以继续！**

如需：
1. 运行完整测试套件 → 告诉我
2. 检查代码风格 → 告诉我
3. 生成变更总结 → 告诉我
"""
            return report

        # 有问题
        report = """## 验证发现问题 ⚠️

### 证据

"""
        for line in evidence_lines:
            report += f"- {line}\n"

        report += """
### 问题

"""
        for issue in issues:
            emoji = "🔴" if issue["type"] == "error" else "🟡"
            report += f"- {emoji} {issue['message']}\n"
            if "evidence" in issue and issue["evidence"]:
                evidence_text = issue["evidence"][:500]
                report += f"  ```\n  {evidence_text}\n  ```\n"

        report += """
---

**在问题解决之前，不能声称完成。**

请修复上述问题，然后重新验证。
"""

        return report

    def get_hooks(self) -> list[Hook]:
        """获取钩子"""
        return []


# 全局实例
_verification_skill = VerificationSkill()


def get_skill() -> VerificationSkill:
    """获取技能实例"""
    return _verification_skill
