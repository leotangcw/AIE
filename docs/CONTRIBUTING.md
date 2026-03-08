# AIE CI/CD 和贡献规范

> 本文档汇总了 AIE 项目的 CI/CD 配置、贡献规范和开发流程。

---

## 📋 快速开始

### 新贡献者

1. 阅读 [贡献指南](../CONTRIBUTING.md)
2. 设置开发环境
3. 查看 [好上手的 Issue](https://github.com/countbot-ai/AIE/issues?q=is%3Aopen+is%3Aissue+label%3A%22good+first+issue%22)

### 本地测试

```bash
# Linux/macOS
./scripts/run_tests.sh

# Windows
scripts\run_tests.bat
```

---

## 🏗️ 架构概览

### CI/CD Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                     GitHub Actions                           │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Commit    │  │   Python    │  │   Security  │         │
│  │    Lint     │  │    Test     │  │    Scan     │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Frontend   │  │    Docs     │  │   Claude    │         │
│  │   Lint      │  │  Validate   │  │   Code      │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   Dev         │    │   Staging     │    │  Production   │
│   Deploy      │    │   Deploy      │    │   Release     │
└───────────────┘    └───────────────┘    └───────────────┘
```

### 工作流文件

| 文件 | 说明 | 触发条件 |
|------|------|---------|
| [ci.yml](../.github/workflows/ci.yml) | 主 CI 流程 | push/PR |
| [release.yml](../.github/workflows/release.yml) | 发布流程 | tag 推送 |
| [claude-code.yml](../.github/workflows/claude-code.yml) | Claude Code 辅助 | PR/手动 |
| [dependencies.yml](../.github/workflows/dependencies.yml) | 依赖检查 | 每周/手动 |
| [pr-labeler.yml](../.github/workflows/pr-labeler.yml) | PR 自动标签 | PR 创建 |

---

## 📁 目录结构

```
.github/
├── workflows/
│   ├── ci.yml              # 主 CI 流程
│   ├── release.yml         # 发布流程
│   ├── claude-code.yml     # Claude Code 辅助
│   ├── dependencies.yml    # 依赖检查
│   └── pr-labeler.yml      # PR 自动标签
├── ISSUE_TEMPLATE/
│   ├── bug_report.md       # Bug 报告模板
│   └── feature_request.md  # 功能请求模板
├── labeler.yml             # 标签规则
├── PULL_REQUEST_TEMPLATE.md # PR 模板
└── link-check-config.json  # 链接检查配置

scripts/
├── run_tests.sh            # 本地测试脚本 (Unix)
└── run_tests.bat           # 本地测试脚本 (Windows)

docs/
├── CONTRIBUTING.md         # 贡献指南
├── MODULE_DEVELOPMENT_GUIDE.md  # 模块开发指南
├── TESTING_GUIDE.md        # 测试指南
├── ci-testing.md           # CI 测试说明
└── MODULE_DESIGN_INDEX.md  # 模块设计索引
```

---

## ✅ 开发检查清单

### 提交前

- [ ] 代码通过本地测试 (`./scripts/run_tests.sh`)
- [ ] 代码格式化 (black/isort)
- [ ] 代码风格检查通过 (flake8)
- [ ] 添加/更新测试
- [ ] 更新文档 (如适用)
- [ ] Commit 信息符合规范

### 创建 PR 时

- [ ] 填写 PR 模板
- [ ] 关联相关 Issue
- [ ] 选择正确的变更类型
- [ ] 标记受影响的模块
- [ ] 等待 CI 通过
- [ ] 回应审查意见

### 合并要求

- [ ] CI 全部通过
- [ ] 至少 1 人审查通过
- [ ] 无未解决的评论
- [ ] 分支已更新到最新

---

## 🔧 工具配置

### Pre-commit Hooks

```bash
# 安装 pre-commit
pip install pre-commit

# 安装 hooks
pre-commit install

# 手动运行所有 hooks
pre-commit run --all-files
```

### VS Code 设置

项目包含推荐的 VS Code 配置 (`.vscode/settings.json`)：

- 保存时自动格式化
- 自动排序导入
- Flake8/Black/isort 集成

推荐安装扩展：
- Python
- Pylance
- Black Formatter
- isort

---

## 📊 代码质量要求

### 测试覆盖率

| 模块 | 最低覆盖率 |
|------|-----------|
| 核心模块 | 80% |
| API 层 | 70% |
| 工具函数 | 90% |
| UI 组件 | 60% |

### 代码风格

- **Python**: Black + isort + flake8
- **TypeScript**: ESLint + Prettier
- **行长度**: 100 字符
- **复杂度**: 圈复杂度 ≤ 12

---

## 🚀 发布流程

### 版本号规范

遵循 [Semantic Versioning](https://semver.org/)：

```
MAJOR.MINOR.PATCH

v0.1.0  # 初始版本
v0.1.1  # Bug 修复
v0.2.0  # 新功能
v1.0.0  # 正式版
```

### 发布步骤

1. 更新版本号
2. 更新 CHANGELOG
3. 提交并打标签
4. 推送到 GitHub (自动触发发布流程)

```bash
# 创建版本标签
git tag -a v0.2.0 -m "Release v0.2.0"
git push origin v0.2.0
```

---

## 🤖 Claude Code 集成

### 使用场景

1. **代码生成**: "为 tools 模块添加文件读取功能"
2. **代码审查**: "审查这个 PR 的代码质量"
3. **测试生成**: "为 agent/loop.py 生成单元测试"
4. **文档生成**: "为 memory 模块生成 API 文档"

### 最佳实践

```bash
# 明确任务
claude "修复 memory_search 函数在关键词为空时的异常"

# 指定范围
claude "优化 backend/modules/memory.py 的搜索算法"

# 说明期望
claude "为 MemoryStore 类编写测试，覆盖 append 和 search 方法"
```

---

## 📖 相关文档

| 文档 | 说明 |
|------|------|
| [贡献指南](../CONTRIBUTING.md) | 如何贡献代码 |
| [模块开发指南](./MODULE_DEVELOPMENT_GUIDE.md) | 模块开发规范 |
| [测试指南](./TESTING_GUIDE.md) | 编写和运行测试 |
| [CI 测试说明](./ci-testing.md) | CI 配置和故障排除 |

---

## ❓ 需要帮助？

- 📖 查看 [FAQ](./faq.md)
- 💬 在 [Discussions](https://github.com/countbot-ai/AIE/discussions) 提问
- 🐛 报告 [Issues](https://github.com/countbot-ai/AIE/issues)
- 📧 联系维护者

---

## 📜 许可证

MIT License - 详见 [LICENSE](../LICENSE)
