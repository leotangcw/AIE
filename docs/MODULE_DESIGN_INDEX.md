# AIE 模块设计文档索引

**版本**: v1.0
**更新日期**: 2026-03-08
**状态**: 文档整理完成

---

## 文档目录

### 1. 总体架构设计
- [总体架构设计](./designs/01-architecture.md) - 系统整体架构、组件关系、数据流

### 2. 后端核心模块

| 文档 | 文件 | 说明 |
|------|------|------|
| Agent 模块 | [02-agent-module.md](./designs/02-agent-module.md) | Agent 循环、上下文构建 |
| Providers 模块 | [03-providers-module.md](./designs/03-providers-module.md) | LLM 提供商抽象 |
| Tools 模块 | [04-tools-module.md](./designs/04-tools-module.md) | 工具系统、注册表 |
| 记忆系统 | [06-memory-system.md](./designs/06-memory-system.md) | 记忆存储、搜索、总结 |
| 技能系统 | [07-skills-system.md](./designs/07-skills-system.md) | 可插拔技能插件 |

### 3. 后端支撑模块

| 文档 | 文件 | 说明 |
|------|------|------|
| 支撑模块合集 | [05-support-modules.md](./designs/05-support-modules.md) | Channels, Cron, Messaging, WebSocket, Auth |

### 4. 前端模块设计
- [前端架构](./designs/10-frontend-architecture.md) - Vue3 + TypeScript 架构

### 5. 数据设计
- [数据库设计](./designs/14-database-design.md) - 数据模型、表结构、关系

### 6. 进度与 TODO
- [项目进度追踪](./PROJECT_PROGRESS.md) - 各模块开发状态、TODO 清单

---

## 快速链接

| 模块 | 文件路径 | 状态 |
|------|---------|------|
| Agent Loop | `backend/modules/agent/loop.py` | ✅ 完成 |
| Context Builder | `backend/modules/agent/context.py` | ✅ 完成 |
| Memory Store | `backend/modules/agent/memory.py` | ✅ 完成 |
| LiteLLM Provider | `backend/modules/providers/litellm_provider.py` | ✅ 完成 |
| Tool Registry | `backend/modules/tools/registry.py` | ✅ 完成 |
| Filesystem Tools | `backend/modules/tools/filesystem.py` | ✅ 完成 |
| Shell Tools | `backend/modules/tools/shell.py` | ✅ 完成 |
| Channel Handler | `backend/modules/channels/handler.py` | ✅ 完成 |
| Cron Scheduler | `backend/modules/cron/scheduler.py` | ✅ 完成 |
| WebSocket | `backend/ws/connection.py` | ✅ 完成 |

---

## 模块依赖关系图

```
┌─────────────────────────────────────────────────────────────────┐
│                          FastAPI App                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ API Routes  │  │  WebSocket  │  │  Frontend   │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                      │
│  ┌──────▼────────────────▼────────────────▼──────┐              │
│  │            ChannelMessageHandler              │              │
│  └────────────────────┬─────────────────────────┘              │
│                       │                                         │
│  ┌────────────────────▼─────────────────────────┐              │
│  │               AgentLoop                       │              │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐ │              │
│  │  │ Context   │  │  Memory   │  │  Skills   │ │              │
│  │  │ Builder   │  │  Store    │  │  Loader   │ │              │
│  │  └───────────┘  └───────────┘  └───────────┘ │              │
│  └────────────────────┬─────────────────────────┘              │
│                       │                                         │
│         ┌─────────────┼─────────────┐                          │
│         │             │             │                          │
│  ┌──────▼──────┐ ┌────▼─────┐ ┌────▼──────┐                   │
│  │  Providers  │ │  Tools   │ │ Subagent  │                   │
│  │  (LLM)      │ │ Registry │ │ Manager   │                   │
│  └─────────────┘ └──────────┘ └───────────┘                   │
└─────────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
  ┌──────▼──────┐     ┌──────▼──────┐     ┌──────▼──────┐
  │   Channels  │     │    Cron     │     │  Messaging  │
  │  (Feishu/   │     │  Scheduler  │     │   (Queue/   │
  │  DingTalk)  │     │  Executor   │     │  RateLimit) │
  └─────────────┘     └─────────────┘     └─────────────┘
```

---

## 文档清理说明

### 已删除的旧文档

以下旧文档已被删除，内容已整合到新设计文档中：

| 旧文档 | 整合到 | 状态 |
|--------|--------|------|
| `agent-loop.md` | `02-agent-module.md` | ✅ 已删除 |
| `tools.md` | `04-tools-module.md` | ✅ 已删除 |
| `channels.md` | `05-support-modules.md` | ✅ 已删除 |
| `providers.md` | `03-providers-module.md` | ✅ 已删除 |
| `websocket.md` | `05-support-modules.md` | ✅ 已删除 |
| `auth.md` | `05-support-modules.md` | ✅ 已删除 |
| `cron.md` | `05-support-modules.md` | ✅ 已删除 |
| `memory.md` | `06-memory-system.md` | ✅ 已删除 |
| `skills.md` | `07-skills-system.md` | ✅ 已删除 |
| `subagent.md` | `02-agent-module.md` | ✅ 已删除 |
| `tool-calls-display-fix.md` | - | ✅ 已删除 (临时文档) |
| `configuration.md` | `configuration-manual.md` | ✅ 已删除 (重复) |
| `plans/2026-03-02-aie-design.md` | `01-architecture.md` | ✅ 已删除 |

### 保留的文档

以下文档保留，因为它们包含独特的配置和指南内容：

| 文档 | 说明 |
|------|------|
| `configuration-manual.md` | 详细配置手册 |
| `quick-start-guide.md` | 快速入门指南 |
| `deployment.md` | 部署文档 |
| `api-reference.md` | API 参考 |
| `ci-testing.md` | CI/测试文档 |
| `channel-troubleshooting.md` | 渠道排错指南 |

---

## 文档维护说明

### 更新流程
1. 代码变更时同步更新对应模块文档
2. 重大架构变更时更新总体架构设计
3. 每周审查一次文档与代码的一致性

### 文档规范
- 使用中文编写
- 包含架构图/流程图
- 提供关键代码示例
- 说明接口定义
- 记录设计决策和权衡
