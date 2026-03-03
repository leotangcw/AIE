# AIE - AI 办公助手

## 项目概述

**AIE (AI Employ)** 是一个 AI 辅助办公助手，基于 CountBot 开发，逐步整合优秀功能，最终目标是成为一个功能完善的 AI 办公解决方案。

### 核心定位
- AI 辅助办公场景
- 轻量级、可扩展
- 专注国内办公生态（飞书、钉钉、企业微信等）

### 开发策略
1. **以 CountBot 为基础** - 继承其轻量、简洁的设计
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
└── CLAUDE.md                 # 本文件
```

---

## 功能规划

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

## 依赖说明

### 核心依赖
```
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
sqlalchemy>=2.0.36
pydantic>=2.10.0
litellm>=1.50.0
```

### 开发依赖
```
pytest>=8.0.0
pytest-asyncio>=0.23.0
black>=24.0.0
ruff>=0.3.0
```

---

## 参考资源

- CountBot: `/mnt/d/code/AIE_0302/refcode/CountBot/`
- OpenClaw: `/mnt/d/code/AIE_0302/refcode/openclaw/`

---

## 待办事项

- [ ] 初始化项目结构
- [ ] 配置开发环境
- [ ] 迁移 CountBot 基础代码
- [ ] 验证基本功能
