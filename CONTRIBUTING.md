# AIE 贡献指南

> 本文档描述了如何为 AIE (AI Employee) 项目贡献代码。我们采用基于 **Claude Code** 的协作开发流程，确保代码质量和一致性。

---

## 📋 目录

- [开发环境设置](#开发环境设置)
- [项目结构](#项目结构)
- [开发流程](#开发流程)
- [代码规范](#代码规范)
- [提交规范](#提交规范)
- [Pull Request](#pull-request)
- [测试要求](#测试要求)
- [使用 Claude Code](#使用-claude-code)

---

## 🛠️ 开发环境设置

### 前置要求

- **Python**: 3.11+
- **Node.js**: 20+
- **Git**: 2.40+
- **Claude Code**: 最新CLI版本

### 克隆项目

```bash
git clone <repository-url>
cd AIE
```

### 安装依赖

```bash
# Python 后端
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 前端
cd frontend
npm install
```

### 配置 Claude Code

在项目根目录创建 `.claude/settings.local.json`：

```json
{
  "project_name": "AIE",
  "modules": ["backend", "frontend"],
  "language": "zh-CN"
}
```

---

## 📁 项目结构

```
AIE/
├── backend/              # Python 后端
│   ├── api/             # API 路由
│   ├── modules/         # 功能模块
│   │   ├── agent/      # Agent 核心模块
│   │   ├── channels/   # 消息渠道模块
│   │   ├── providers/  # LLM 提供商模块
│   │   ├── tools/      # 工具模块
│   │   └── ...
│   ├── models/         # 数据模型
│   └── tests/          # 后端测试
├── frontend/           # Vue3 前端
│   ├── src/
│   │   ├── modules/   # 功能模块
│   │   │   ├── chat/  # 聊天模块
│   │   │   ├── memory/# 记忆模块
│   │   │   └── ...
│   │   └── composables/
│   └── tests/         # 前端测试
├── docs/              # 项目文档
├── scripts/           # 工具脚本
└── .github/workflows/ # CI/CD 配置
```

---

## 🔄 开发流程

### 1. 创建功能分支

```bash
# 基于最新 dev 分支
git checkout dev
git pull origin dev

# 创建功能分支
git checkout -b feat/your-feature-name
```

### 2. 使用 Claude Code 开发

```bash
# 启动 Claude Code
claude

# 告诉 Claude Code 你的开发任务
# 例如："为 agent 模块添加新的工具函数"
```

### 3. 提交代码

```bash
# 查看变更
git status
git diff

# 提交（遵循提交规范）
git add .
git commit -m "feat(agent): 添加新功能"
```

### 4. 推送并创建 PR

```bash
git push origin feat/your-feature-name

# 在 GitHub 上创建 Pull Request
```

---

## 📏 代码规范

### Python 规范

```python
# ✅ 好的代码风格
def process_message(message: str, max_length: int = 1000) -> dict:
    """处理消息

    Args:
        message: 输入消息
        max_length: 最大长度限制

    Returns:
        处理后的结果字典
    """
    if len(message) > max_length:
        raise ValueError(f"Message too long: {len(message)} > {max_length}")

    return {"content": message.strip(), "length": len(message)}


# 使用类型注解
users: list[str] = []
user_count: int = len(users)
```

```python
# ❌ 避免的写法
def process_message(message, max_length=1000):  # 缺少类型注解
    if len(message) > max_length:
        raise ValueError("Message too long")  # 不清晰的错误信息
    return {"content": message.strip(), "length": len(message)}
```

### 代码风格检查

```bash
# 运行 flake8
flake8 backend/ --config=.flake8

# 运行 black 格式化
black backend/

# 运行 isort 排序导入
isort backend/

# 运行 mypy 类型检查
mypy backend/ --ignore-missing-imports
```

### Vue/TypeScript 规范

```typescript
// ✅ 好的代码风格
interface Message {
  id: string
  content: string
  timestamp: Date
}

const processMessage = (msg: Message): string => {
  return msg.content.trim()
}
```

```typescript
// ❌ 避免的写法
const processMessage = (msg) => {  // 缺少类型定义
  return msg.content.trim()
}
```

---

## 📝 提交规范

我们遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范。

### 提交格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type 类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(agent): 添加记忆搜索功能` |
| `fix` | Bug 修复 | `fix(memory): 修复搜索结果为空的问题` |
| `docs` | 文档更新 | `docs: 更新贡献指南` |
| `refactor` | 代码重构 | `refactor(tools): 重构工具注册表` |
| `test` | 测试相关 | `test(agent): 添加单元测试` |
| `chore` | 构建/配置 | `chore: 更新依赖版本` |
| `ci` | CI 配置 | `ci: 添加安全扫描` |
| `perf` | 性能优化 | `perf: 优化数据库查询` |
| `style` | 代码格式 | `style: 格式化代码` |

### Scope 范围

| 范围 | 说明 |
|------|------|
| `agent` | Agent 核心模块 |
| `memory` | 记忆系统 |
| `tools` | 工具系统 |
| `channels` | 消息渠道 |
| `providers` | LLM 提供商 |
| `frontend` | 前端代码 |
| `backend` | 后端代码 |
| `docs` | 文档 |
| `ci` | CI/CD |

### 提交示例

```bash
# 新功能
git commit -m "feat(agent): 添加工具调用审计日志"

# Bug 修复
git commit -m "fix(memory): 修复记忆搜索时中文分词错误

- 添加 jieba 分词支持
- 优化搜索匹配算法"

# 文档更新
git commit -m "docs: 更新 API 使用示例"
```

---

## 🧪 测试要求

### 运行测试

```bash
# 后端测试
pytest backend/tests/ -v --cov=backend

# 前端测试
cd frontend && npm test

# 完整测试
./scripts/run_tests.sh
```

### 测试覆盖率要求

| 模块类型 | 最低覆盖率 |
|----------|-----------|
| 核心模块 | 80% |
| API 层 | 70% |
| 工具函数 | 90% |
| UI 组件 | 60% |

### 编写测试

```python
# backend/tests/test_agent.py
import pytest
from backend.modules.agent import AgentLoop


class TestAgentLoop:
    """Agent 循环测试类"""

    @pytest.fixture
    def agent(self):
        """创建测试用 Agent 实例"""
        return AgentLoop(config={"model": "test-model"})

    def test_process_message(self, agent):
        """测试消息处理"""
        result = agent.process_message("Hello")
        assert result is not None
        assert "content" in result
```

---

## 🤖 使用 Claude Code

### 基本用法

```bash
# 初始化项目
claude init

# 执行开发任务
claude "为 tools 模块添加文件读取功能"

# 代码审查
claude "审查这个 PR 的代码质量"

# 生成测试
claude "为 agent/loop.py 生成单元测试"
```

### Claude Code 最佳实践

1. **明确任务描述**
   ```
   ❌ "修一下这个"
   ✅ "修复 memory_search 函数在关键词为空时的异常"
   ```

2. **指定文件范围**
   ```
   ❌ "优化代码"
   ✅ "优化 backend/modules/memory.py 的搜索算法"
   ```

3. **说明期望结果**
   ```
   ❌ "写个测试"
   ✅ "为 MemoryStore 类编写测试，覆盖 append 和 search 方法"
   ```

---

## 🔀 Pull Request

### PR 模板

创建 PR 时，请填写以下信息：

```markdown
## 变更描述
<!-- 描述此 PR 的目的和变更内容 -->

## 相关 Issue
<!-- 关联的 Issue 编号，如：Fixes #123 -->

## 测试清单
- [ ] 代码通过本地测试
- [ ] 添加/更新单元测试
- [ ] 文档已更新
- [ ] 代码通过 flake8/black/isort 检查

## 截图（如适用）
<!-- 添加 UI 变更的截图 -->

## 其他说明
<!-- 任何需要特别说明的内容 -->
```

### PR 审查流程

1. **自动化检查**：CI 工作流自动运行
2. **代码审查**：团队成员审查代码
3. **修改反馈**：根据审查意见修改
4. **合并**：审查通过后合并到目标分支

---

## 📦 模块独立开发

每个模块都是独立的，可以单独开发和测试：

```bash
# 只测试 agent 模块
pytest backend/tests/test_agent.py

# 只检查 tools 模块
flake8 backend/modules/tools/

# 只构建 frontend 模块
cd frontend && npm run build
```

---

## 🔗 相关文档

- [CI 测试指南](./ci-testing.md) - CI 配置和本地测试
- [API 参考](./api-reference.md) - API 端点文档
- [模块设计索引](./MODULE_DESIGN_INDEX.md) - 各模块设计文档
- [项目进度](./PROJECT_PROGRESS.md) - 当前开发状态

---

## ❓ 需要帮助？

- 查看 [常见问题解答](./docs/faq.md)
- 在 Issues 中提问
- 联系项目维护者

感谢你的贡献！🎉
