"""Using Git Worktrees Skill - Git 工作树技能

在开始需要与当前工作空间隔离的功能开发时使用 - 创建具有智能目录选择和安全验证的隔离 Git 工作树。
"""

from typing import Any, Optional

from backend.modules.plugins.hooks import Hook


class GitWorktreeSkill:
    """
    Git 工作树技能

    核心原则：系统化的目录选择 + 安全验证 = 可靠的隔离。

    Git 工作树创建共享同一仓库的隔离工作空间，允许同时处理多个分支而无需切换。
    """

    def __init__(self):
        self._session: Optional[dict] = None

    @property
    def name(self) -> str:
        return "using-git-worktrees"

    def should_activate(self, message: str) -> bool:
        """
        检查是否应该激活
        """
        triggers = [
            "隔离工作空间",
            "新分支",
            "功能分支",
            "创建分支",
            "worktree",
            "工作树",
            "隔离开发",
            "feature branch",
            "isolated workspace",
            "new branch",
        ]

        message_lower = message.lower()
        return any(trigger in message_lower for trigger in triggers)

    async def process(self, message: str, context: dict[str, Any]) -> Optional[str]:
        """
        处理工作树请求

        流程：
        1. 检测目录选择
        2. 安全验证
        3. 创建工作树
        4. 运行项目设置
        5. 验证干净的基线
        """
        if not self._session:
            return self._start_worktree_setup(message, context)
        else:
            return self._continue_worktree_setup(message, context)

    def _start_worktree_setup(self, message: str, context: dict[str, Any]) -> str:
        """开始工作树设置"""
        self._session = {
            "task": message,
            "stage": "detect_directory",  # detect_directory -> verify_ignore -> create -> setup -> verify
            "directory": None,
            "feature_name": self._extract_feature_name(message),
        }

        return self._detect_directory(context)

    def _extract_feature_name(self, message: str) -> str:
        """提取功能名称"""
        import re
        # 尝试提取功能名称
        patterns = [
            r"功能[:\s]+(.+?)(?:\s|$)",
            r"feature[:\s]+(.+?)(?:\s|$)",
            r"开发[:\s]+(.+?)(?:\s|$)",
            r"实现[:\s]+(.+?)(?:\s|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, message.lower())
            if match:
                return match.group(1).strip()

        # 默认名称
        return "feature"

    def _detect_directory(self, context: dict[str, Any]) -> str:
        """检测目录选择"""
        self._session["stage"] = "verify_ignore"

        return """## Git Worktree 设置

### 步骤 1：检测目录

我需要确定工作树应该创建在哪里。

**请选择：**

1. **项目本地** `.worktrees/` (隐藏目录)
2. **全局位置** `~/.config/aie/worktrees/<项目名>/`

或者告诉我你偏好的目录位置。

### 同时

请告诉我这个功能/分支的名称，例如：`auth`、`api-v2`、`fix-login-bug`
"""

    def _continue_worktree_setup(self, message: str, context: dict[str, Any]) -> str:
        """继续工作树设置"""
        stage = self._session.get("stage", "detect_directory")

        if stage == "detect_directory":
            return self._handle_directory_selection(message)
        elif stage == "verify_ignore":
            return self._verify_ignore(message)
        elif stage == "create":
            return self._create_worktree(message)
        elif stage == "setup":
            return self._run_project_setup(message)
        elif stage == "verify":
            return self._verify_clean_baseline(message)

        return "请继续工作树设置流程。"

    def _handle_directory_selection(self, message: str) -> str:
        """处理目录选择"""
        message_lower = message.lower()

        # 解析选择
        if "1" in message_lower or "本地" in message_lower or ".worktrees" in message_lower:
            directory = ".worktrees"
        elif "2" in message_lower or "全局" in message_lower or "global" in message_lower:
            directory = "~/.config/aie/worktrees"
        else:
            # 用户指定了目录
            directory = message.strip()

        self._session["directory"] = directory
        self._session["stage"] = "verify_ignore"

        # 提取功能名称
        if "分支" in message:
            parts = message.split("分支")
            if len(parts) > 1:
                self._session["feature_name"] = parts[1].strip().split()[0]

        return self._verify_ignore("")

    def _verify_ignore(self, message: str) -> str:
        """验证忽略配置"""
        directory = self._session.get("directory", ".worktrees")

        # 对于项目本地目录，需要验证 .gitignore
        if directory.startswith("."):
            return f"""## 步骤 2：安全验证

### 检查忽略配置

对于项目本地的 `{directory}/` 目录，需要验证它已被 .gitignore 忽略。

### 请运行

```bash
git check-ignore -q {directory}
```

### 结果

- **已忽略**：继续创建工作树
- **未忽略**：需要先添加到 .gitignore

请运行命令并告诉我结果，或者让我帮你检查。
"""
        else:
            # 全局目录不需要验证
            self._session["stage"] = "create"
            return self._create_worktree("")

    def _create_worktree(self, message: str) -> str:
        """创建工作树"""
        directory = self._session.get("directory", ".worktrees")
        feature_name = self._session.get("feature_name", "feature")
        branch_name = f"feature/{feature_name}"

        self._session["branch_name"] = branch_name
        self._session["stage"] = "setup"

        # 确定完整路径
        if directory.startswith("."):
            worktree_path = f"{directory}/{feature_name}"
        else:
            worktree_path = f"{directory}/{feature_name}"

        return f"""## 步骤 3：创建工作树

### 命令

```bash
# 确定项目名称
project=$(basename "$(git rev-parse --show-toplevel)")

# 创建工作树和新分支
git worktree add {worktree_path} -b {branch_name}

# 进入工作树
cd {worktree_path}
```

### 或者让我帮你

请告诉我：
1. 你的项目名称（或者让我自动检测）
2. 分支名称（默认：`{branch_name}`）

我会帮你生成和执行命令。
"""

    def _run_project_setup(self, message: str) -> str:
        """运行项目设置"""
        self._session["stage"] = "verify"

        return """## 步骤 4：运行项目设置

### 自动检测和运行

根据项目类型自动安装依赖：

**Node.js:**
```bash
npm install
```

**Python:**
```bash
pip install -r requirements.txt
# 或
poetry install
```

**Rust:**
```bash
cargo build
```

**Go:**
```bash
go mod download
```

### 请运行

请在新的工作树中运行项目设置命令，然后告诉我结果。
"""

    def _verify_clean_baseline(self, message: str) -> str:
        """验证干净的基线"""
        return """## 步骤 5：验证基线

### 运行测试

确保工作树从干净的基线开始：

```bash
# 项目测试命令
npm test
pytest
cargo test
go test ./...
```

### 请运行

请运行测试并告诉我：
- 测试数量
- 通过/失败数量

只有测试通过才能确认工作树基线干净。
"""

    def get_hooks(self) -> list[Hook]:
        """获取钩子"""
        return []


# 全局实例
_git_worktree_skill = GitWorktreeSkill()


def get_skill() -> GitWorktreeSkill:
    """获取技能实例"""
    return _git_worktree_skill
