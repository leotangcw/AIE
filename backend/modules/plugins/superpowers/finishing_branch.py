"""Finishing a Development Branch Skill - 完成开发分支技能

当实现完成、所有测试通过后，决定如何整合工作 - 提供 merge、PR 或 cleanup 的结构化选项。
"""

from typing import Any, Optional

from backend.modules.plugins.hooks import Hook


class FinishingBranchSkill:
    """
    完成开发分支技能

    核心原则：验证测试 → 展示选项 → 执行选择 → 清理。
    """

    def __init__(self):
        self._session: Optional[dict] = None

    @property
    def name(self) -> str:
        return "finishing-a-development-branch"

    def should_activate(self, message: str) -> bool:
        """
        检查是否应该激活
        """
        triggers = [
            "完成了",
            "开发完成",
            "实现完成",
            "功能完成",
            "做完了",
            "完成了开发",
            "done developing",
            "feature complete",
            "implementation complete",
            "完成分支",
            "合并分支",
        ]

        message_lower = message.lower()
        return any(trigger in message_lower for trigger in triggers)

    async def process(self, message: str, context: dict[str, Any]) -> Optional[str]:
        """
        处理完成分支请求

        流程：
        1. 验证测试通过
        2. 确定基础分支
        3. 展示选项
        4. 执行选择
        5. 清理工作树
        """
        if not self._session:
            return self._start_finishing(message, context)
        else:
            return self._continue_finishing(message, context)

    def _start_finishing(self, message: str, context: dict[str, Any]) -> str:
        """开始完成分支流程"""
        self._session = {
            "task": message,
            "stage": "verify_tests",  # verify_tests -> determine_base -> present_options -> execute -> cleanup
            "tests_passed": None,
            "base_branch": None,
        }

        # 检查是否有测试结果
        test_results = context.get("test_results")

        if test_results:
            # 有测试结果，验证
            if test_results.get("failed", 1) == 0:
                self._session["tests_passed"] = True
                self._session["stage"] = "determine_base"
                return self._determine_base_branch(context)
            else:
                self._session["tests_passed"] = False
                return self._report_test_failure(test_results)
        else:
            # 没有测试结果，请求验证
            return self._request_test_verification(context)

    def _request_test_verification(self, context: dict[str, Any]) -> str:
        """请求测试验证"""
        return """## 验证测试

在展示选项之前，需要验证测试通过。

### 请运行

```bash
# 根据你的项目选择
pytest
npm test
cargo test
go test ./...
```

### 或者告诉我

1. 你的测试命令是什么？
2. 测试结果如何？

只有测试通过后才能继续完成分支流程。
"""

    def _report_test_failure(self, test_results: dict) -> str:
        """报告测试失败"""
        failed_count = test_results.get("failed", 0)
        failed_tests = test_results.get("failed_tests", [])

        report = f"""## 测试失败 ⚠️

测试失败 ({failed_count} failures)。

必须在测试通过后才能完成分支。

### 失败的测试

"""
        for test in failed_tests[:5]:  # 最多显示5个
            report += f"- {test}\n"

        report += """
---

**测试修复后请告诉我，然后继续完成分支流程。**
"""

        return report

    def _determine_base_branch(self, context: dict[str, Any]) -> str:
        """确定基础分支"""
        self._session["stage"] = "present_options"

        # 尝试检测基础分支
        # 这里需要 git 命令支持，简化处理
        base_branch = context.get("base_branch", "main")

        self._session["base_branch"] = base_branch

        return self._present_options(base_branch)

    def _present_options(self, base_branch: str) -> str:
        """展示选项"""
        return f"""## 实现完成

测试已验证通过。现在你想如何完成这个工作？

### 请选择

1. **本地合并** - 合并到 {base_branch} 分支
2. **推送并创建 PR** - 推送到远程并创建 Pull Request
3. **保持分支** - 保留分支，稍后处理
4. **丢弃** - 删除这个分支及其工作

---

请输入选项编号 (1-4)，或描述你的选择。
"""

    def _continue_finishing(self, message: str, context: dict[str, Any]) -> str:
        """继续完成分支流程"""
        stage = self._session.get("stage", "present_options")

        if stage == "present_options":
            return self._handle_option_selection(message, context)
        elif stage == "execute":
            return self._execute_choice(message, context)
        elif stage == "cleanup":
            return self._cleanup(message, context)

        return "请选择一个选项完成分支。"

    def _handle_option_selection(self, message: str, context: dict[str, Any]) -> str:
        """处理选项选择"""
        message_lower = message.lower()

        # 解析选择
        choice = None
        if "1" in message_lower or "本地合并" in message_lower or "merge" in message_lower:
            choice = 1
        elif "2" in message_lower or "pr" in message_lower or "pull request" in message_lower:
            choice = 2
        elif "3" in message_lower or "保持" in message_lower or "keep" in message_lower:
            choice = 3
        elif "4" in message_lower or "丢弃" in message_lower or "discard" in message_lower:
            choice = 4

        if choice is None:
            return "请输入选项编号 (1-4)，或描述你的选择。"

        base_branch = self._session.get("base_branch", "main")
        feature_branch = context.get("current_branch", "feature-branch")

        if choice == 1:
            # 本地合并
            return self._merge_locally(base_branch, feature_branch)
        elif choice == 2:
            # 创建 PR
            return self._create_pr(base_branch, feature_branch)
        elif choice == 3:
            # 保持分支
            return self._keep_branch(base_branch, feature_branch)
        elif choice == 4:
            # 丢弃
            return self._confirm_discard(base_branch, feature_branch)

        return "请选择一个选项。"

    def _merge_locally(self, base_branch: str, feature_branch: str) -> str:
        """本地合并"""
        self._session["choice"] = "merge"
        self._session["stage"] = "cleanup"

        return f"""## 选项 1：本地合并

### 步骤

```bash
# 切换到基础分支
git checkout {base_branch}

# 拉取最新
git pull

# 合并功能分支
git merge {feature_branch}

# 验证合并后的测试
pytest  # 或你的测试命令

# 如果测试通过，删除功能分支
git branch -d {feature_branch}
```

### 完成后

请执行上述命令，然后告诉我结果。

如果遇到冲突，请告诉我，我会帮你解决。
"""

    def _create_pr(self, base_branch: str, feature_branch: str) -> str:
        """创建 PR"""
        self._session["choice"] = "pr"
        self._session["stage"] = "cleanup"

        return f"""## 选项 2：推送并创建 PR

### 步骤

```bash
# 推送分支
git push -u origin {feature_branch}

# 创建 PR (需要 gh CLI)
gh pr create --title "<标题>" --body "$(cat <<'EOF'
## 总结
<2-3 行描述变更内容>

## 测试计划
- [ ] <验证步骤>
EOF
)"
```

### 或者

1. 告诉我 PR 标题和描述，我帮你生成命令
2. 你手动在 GitHub/GitLab 上创建 PR

创建 PR 后记得清理工作树（选项 3 之后）。
"""

    def _keep_branch(self, base_branch: str, feature_branch: str) -> str:
        """保持分支"""
        self._session["choice"] = "keep"
        self._session["stage"] = "done"

        return f"""## 选项 3：保持分支

### 状态

分支 `{feature_branch}` 已保留。
工作树保持不变。

### 记住

- 分支 `{feature_branch}` 保留在本地
- 你可以稍后手动合并或创建 PR
- 需要时告诉我，我会帮你完成

---

分支已保持。如需继续其他工作，请告诉我。
"""

    def _confirm_discard(self, base_branch: str, feature_branch: str, context: dict[str, Any] = None) -> str:
        """确认丢弃"""
        self._session["choice"] = "discard"
        self._session["stage"] = "confirm_discard"

        commit_count = "N"

        return f"""## 选项 4：丢弃 - 确认

⚠️ **这将永久删除：**

- 分支 `{feature_branch}`
- 所有提交
- 工作树（如有）

### 请确认

请输入 `discard` 确认删除。

```
Type 'discard' to confirm.
```

**此操作不可撤销！**
"""

    def _execute_choice(self, message: str, context: dict[str, Any]) -> str:
        """执行选择"""
        # 这里可以添加实际的 git 命令执行
        return "请执行上述命令，然后告诉我结果。"

    def _cleanup(self, message: str, context: dict[str, Any]) -> str:
        """清理工作树"""
        choice = self._session.get("choice")

        if choice in ["merge", "pr", "discard"]:
            return """## 清理工作树

### 检查工作树

```bash
git worktree list
```

### 如果在工作树中

```bash
git worktree remove <工作树路径>
```

### 完成后

告诉我工作树已清理，分支完成流程结束。
"""

        return "分支完成。"

    def get_hooks(self) -> list[Hook]:
        """获取钩子"""
        return []


# 全局实例
_finishing_branch_skill = FinishingBranchSkill()


def get_skill() -> FinishingBranchSkill:
    """获取技能实例"""
    return _finishing_branch_skill
