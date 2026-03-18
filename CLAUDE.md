# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# AIE - AI 办公助手

## 项目概述

**AIE (AI Employee)** 是一个企业级 AI 办公助手，基于开源项目开发，逐步整合优秀功能，最终目标是成为一个功能完善的 AI 办公解决方案。

### 核心定位
- AI 辅助办公场景
- 轻量级、可扩展
- 专注国内办公生态（飞书、钉钉、企业微信等）

### 开发策略
1. **以开源项目为基础** - 继承其轻量、简洁的设计
2. **逐步整合** - 吸收 OpenClaw 等项目的优秀功能
3. **专注办公** - 针对办公场景进行优化

---

## 技术栈

### 后端
- **Python 3.11+**
- FastAPI + Uvicorn
- SQLAlchemy + Alembic
- Pydantic + Pydantic Settings
- LiteLLM (多模型支持)
- WebSocket (实时通信)

### 前端
- Vue 3 + TypeScript
- Vite
- Pinia
- Vue I18n

### 数据存储
- SQLite (开发/轻量部署)
- PostgreSQL (生产环境)

---

## 目录结构

```
AIE/
├── backend/                    # Python 后端
│   ├── api/                    # API 路由
│   ├── modules/                # 核心模块
│   │   ├── agent/             # Agent 核心
│   │   ├── channels/          # 消息渠道
│   │   ├── providers/         # 大模型提供商
│   │   ├── tools/             # 工具集
│   │   ├── cron/              # 定时任务
│   │   └── messaging/         # 消息队列
│   ├── models/                # 数据模型
│   ├── ws/                    # WebSocket
│   └── app.py                 # 应用入口
├── frontend/                   # Vue3 前端
│   ├── src/
│   │   ├── api/               # API 客户端
│   │   ├── components/        # 通用组件
│   │   ├── modules/          # 业务模块
│   │   │   ├── chat/         # 聊天
│   │   │   ├── memory/       # 记忆
│   │   │   ├── scheduler/    # 调度
│   │   │   └── settings/     # 设置
│   │   └── composables/      # 组合式 API
│   └── dist/                 # 构建产物
├── docs/                      # 文档
├── scripts/                   # 脚本
├── memory/                    # 记忆存储
├── resources/                 # 资源文件
└── config/                    # 配置文件
```

---

## 核心架构

### Application Structure
The application follows a modular architecture with the main components:

- **Backend (FastAPI)**: Main server application with API endpoints
- **WebSocket**: Real-time communication for chat functionality
- **Channel Manager**: Handles integration with various messaging platforms (QQ, DingTalk, Feishu, Telegram)
- **Agent Loop**: Core AI processing loop that handles conversations
- **Memory Store**: Persistent storage for conversation history and context
- **Tool Registry**: Extensible tool system for AI actions
- **Cron System**: Scheduled task execution

### Component Flow
1. Requests come through API routes or WebSocket connections
2. Authentication middleware validates access
3. ChannelMessageHandler processes incoming messages
4. AgentLoop with LiteLLMProvider processes AI interactions
5. Tool registry enables AI to execute various functions
6. Results are delivered back via appropriate channels

### Configuration System
- Centralized configuration loader using Pydantic Settings
- Environment-based configuration with .env support
- Dynamic reloading of configuration changes

---

## Development Commands

### Running the Application
```bash
# Start in development mode
python start_dev.py

# Start in production mode (opens browser automatically)
python start_app.py

# Start desktop app
python start_desktop.py

# For AIE-specific startup
python start_aie.py
```

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file from example
cp .env.example .env
# Then edit .env with your configuration
```

### Database Management
```bash
# Initialize database
# Database initialization happens automatically on startup

# Run migrations (if using alembic)
alembic upgrade head
```

---

## Key Files and Their Roles

- `backend/app.py`: Main FastAPI application with lifecycle management
- `start_app.py`: Production startup script with browser auto-open
- `start_dev.py`: Development mode with hot reloading
- `backend/api/*.py`: Individual API route definitions
- `backend/modules/agent/loop.py`: Core AI processing loop
- `backend/modules/providers/litellm_provider.py`: LLM provider abstraction
- `backend/modules/tools/setup.py`: Tool registration system
- `backend/ws/connection.py`: WebSocket connection handling

---

## Features

### Phase 1: 基础功能 (基于 CountBot)
- [x] 智能对话
- [x] 记忆系统
- [x] 多渠道支持 (飞书、钉钉、微信、Web)
- [x] 定时任务
- [x] 消息队列

### Phase 2: 办公增强
- [ ] 日程管理集成
- [ ] 文档处理
- [ ] 会议纪要
- [ ] 任务提醒

### Phase 3: 企业功能 (整合 OpenClaw)
- [ ] 多 Agent 协作
- [ ] 工作流自动化
- [ ] 企业级安全
- [ ] 权限管理

### Phase 4: 高级功能
- [ ] 语音交互
- [ ] Canvas 可视化
- [ ] 移动端支持

---

## 开发规范

### 代码风格
- Python: 遵循 PEP 8，使用 Black 格式化
- TypeScript/Vue: 使用 ESLint + Prettier
- 注释: 中文注释为主

### Git 提交规范
```
feat: 新功能
fix: 修复
refactor: 重构
docs: 文档
chore: 构建/工具
```

### 命名规范
- Python: snake_case
- Vue/TypeScript: PascalCase / camelCase

---

## Security Features

- Remote authentication middleware
- Command execution sandboxing
- Dangerous command blocking
- Audit logging capability
- Rate limiting
- Message deduplication