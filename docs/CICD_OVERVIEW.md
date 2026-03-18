# AIE CI/CD 和 Docker 部署总览

> 一站式 CI/CD 流程和 Docker 部署指南

---

## 📁 目录结构

```
AIE/
├── .github/workflows/          # GitHub Actions CI/CD 工作流
│   ├── ci.yml                  # 主 CI 流程
│   ├── release.yml             # 发布流程
│   ├── claude-code.yml         # Claude Code 辅助
│   ├── dependencies.yml        # 依赖检查
│   └── pr-labeler.yml          # PR 自动标签
│
├── docker/                     # Docker 配置和脚本
│   ├── docker-compose.yml      # 主 Docker Compose 配置
│   ├── docker-compose.models.yml  # 模型部署配置
│   ├── Dockerfile.backend      # 后端镜像
│   ├── Dockerfile.ci           # CI 测试镜像
│   ├── Dockerfile.frontend.dev # 前端开发镜像
│   ├── Dockerfile.frontend.prod# 前端生产镜像
│   ├── nginx.conf              # Nginx 配置
│   ├── docker-start.sh         # 一键启动脚本 (Linux)
│   ├── docker-start.bat        # 一键启动脚本 (Windows)
│   ├── deploy-model.sh         # 模型部署脚本
│   ├── README.md               # Docker 快速开始
│   └── MODEL_DEPLOY.md         # 模型部署指南
│
├── scripts/                    # 工具脚本
│   ├── run_tests.sh            # 本地测试脚本 (Linux)
│   └── run_tests.bat           # 本地测试脚本 (Windows)
│
├── docs/                       # 文档
│   ├── CONTRIBUTING.md         # 贡献指南
│   ├── MODULE_DEVELOPMENT_GUIDE.md  # 模块开发指南
│   ├── TESTING_GUIDE.md        # 测试指南
│   └── ci-testing.md           # CI 测试说明
│
├── .flake8                     # Flake8 配置
├── .pre-commit-config.yaml     # Pre-commit Hooks 配置
├── CONTRIBUTING.md             # 贡献指南
└── .env.docker.example         # Docker 环境变量示例
```

---

## 🚀 快速开始

### 1. 本地开发

```bash
# 克隆项目
git clone <repository-url>
cd AIE

# 安装依赖
pip install -r requirements.txt
cd frontend && npm install

# 运行本地测试
./scripts/run_tests.sh  # Linux/macOS
scripts\run_tests.bat   # Windows
```

### 2. Docker 开发

```bash
# 配置环境变量
cp docker/.env.docker.example .env.docker

# 一键启动开发环境
cd docker
./docker-start.sh -p dev  # Linux/macOS
docker-start.bat -p dev   # Windows
```

访问：
- 前端：http://localhost:3000
- 后端：http://localhost:8000
- API 文档：http://localhost:8000/docs

### 3. 部署本地模型

```bash
cd docker

# 部署 Ollama 模型
./deploy-model.sh -p ollama -m qwen2.5:7b

# 查看状态
./deploy-model.sh -a status
```

---

## 🔧 CI/CD 流程

### GitHub Actions 工作流

| 工作流 | 说明 | 触发条件 |
|--------|------|---------|
| CI | 代码质量检查、测试 | push/PR |
| Release | 构建和发布 | tag 推送 |
| Claude Code | AI 辅助开发 | PR/手动 |
| Dependencies | 依赖更新检查 | 每周 |
| PR Labeler | 自动标签 | PR 创建 |

### 本地 CI 检查

```bash
# 运行完整 CI 流程
docker-compose --profile ci up ci-test

# 或使用本地脚本
./scripts/run_tests.sh
```

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

## 🐳 Docker 环境

### 服务组件

```
┌─────────────────────────────────────────────┐
│              docker-compose                  │
├─────────────────────────────────────────────┤
│  ┌───────────┐  ┌───────────┐  ┌─────────┐ │
│  │  Frontend │  │  Backend  │  │  Nginx  │ │
│  │  (Node)   │  │ (Python)  │  │ (Prod)  │ │
│  └─────┬─────┘  └─────┬─────┘  └────┬────┘ │
│        │              │              │      │
│  ┌─────▼──────────────▼──────────────▼────┐ │
│  │           aie-network                  │ │
│  └─────┬──────────────┬──────────────┬────┘ │
│        │              │              │      │
│  ┌─────▼─────┐  ┌─────▼─────┐  ┌────▼────┐ │
│  │ Postgres  │  │   Redis   │  │  CI     │ │
│  │           │  │           │  │  Test   │ │
│  └───────────┘  └───────────┘  └─────────┘ │
└─────────────────────────────────────────────┘
```

### 环境配置

| 环境 | 命令 | 说明 |
|------|------|------|
| 开发 | `./docker-start.sh -p dev` | 热重载、调试模式 |
| CI | `./docker-start.sh -p ci` | 运行测试 |
| 生产 | `./docker-start.sh -p prod` | 优化构建 |
| 模型 | `./deploy-model.sh` | 部署本地模型 |

---

## 🤖 模型部署

### 支持的提供商

| 提供商 | 说明 | 命令 |
|--------|------|------|
| Ollama | 轻量级本地模型 | `./deploy-model.sh -p ollama` |
| LocalAI | OpenAI 兼容 API | `./deploy-model.sh -p localai` |
| FastChat | 多模型服务 | `./deploy-model.sh -p fastchat` |

### 推荐模型

- **qwen2.5:7b** - 通义千问，中文支持好
- **llama3.2:3b** - Llama 轻量版
- **codellama:7b** - 代码专用

---

## 📖 文档导航

| 文档 | 说明 |
|------|------|
| [贡献指南](./CONTRIBUTING.md) | 如何贡献代码 |
| [模块开发指南](./MODULE_DEVELOPMENT_GUIDE.md) | 模块开发规范 |
| [测试指南](./TESTING_GUIDE.md) | 编写和运行测试 |
| [Docker 快速开始](../docker/README.md) | Docker 部署 |
| [模型部署](../docker/MODEL_DEPLOY.md) | 本地模型部署 |

---

## ❓ 需要帮助？

- 📖 查看 [FAQ](./faq.md)
- 🐛 报告 [Issues](https://github.com/countbot-ai/AIE/issues)
- 💬 参与 [Discussions](https://github.com/countbot-ai/AIE/discussions)

---

## 📜 许可证

MIT License - 详见 [LICENSE](../LICENSE)
