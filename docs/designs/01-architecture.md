# 总体架构设计

**版本**: v1.0
**更新日期**: 2026-03-08

---

## 1. 系统概述

AIE (AI Employee) 是一个企业级 AI 办公助手系统，采用前后端分离架构，支持多渠道消息接入和智能化 AI 对话。

### 1.1 核心定位
- AI 辅助办公场景
- 轻量级、可扩展
- 专注国内办公生态（飞书、钉钉、企业微信等）

### 1.2 技术栈

| 层级 | 技术选型 |
|------|---------|
| **后端语言** | Python 3.11+ |
| **Web 框架** | FastAPI + Uvicorn |
| **AI 处理** | LiteLLM (多模型支持) |
| **数据库** | SQLite (开发) / PostgreSQL (生产) |
| **ORM** | SQLAlchemy + Alembic |
| **配置管理** | Pydantic Settings |
| **实时通信** | WebSocket |
| **前端框架** | Vue 3 + TypeScript + Vite |
| **状态管理** | Pinia |
| **国际化** | Vue I18n |

---

## 2. 系统架构图

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            AIE 系统架构                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐              │
│  │   Web UI     │    │  飞书/钉钉   │    │   微信/QQ    │              │
│  │  (Vue3+TS)   │    │   渠道接入   │    │   渠道接入   │              │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘              │
│         │                   │                    │                       │
│         └───────────────────┼────────────────────┘                       │
│                             │                                            │
│                    ┌────────▼────────┐                                   │
│                    │  Channel Manager │                                   │
│                    │   渠道管理器     │                                   │
│                    └────────┬────────┘                                   │
│                             │                                            │
│                    ┌────────▼────────┐                                   │
│                    │  Message Queue   │                                   │
│                    │   企业消息队列   │                                   │
│                    └────────┬────────┘                                   │
│                             │                                            │
│         ┌───────────────────┼───────────────────┐                       │
│         │                   │                   │                        │
│  ┌──────▼──────┐   ┌────────▼───────┐   ┌──────▼──────┐                │
│  │ WebSocket   │   │ ChannelMessage │   │ Cron jobs   │                │
│  │   端点      │   │    Handler     │   │  定时任务   │                │
│  └──────┬──────┘   └────────┬───────┘   └──────┬──────┘                │
│         │                   │                   │                        │
│         └───────────────────┼───────────────────┘                       │
│                             │                                            │
│                    ┌────────▼────────┐                                   │
│                    │    AgentLoop    │                                   │
│                    │   AI 处理核心   │                                   │
│                    └────────┬────────┘                                   │
│                             │                                            │
│         ┌───────────────────┼───────────────────┐                       │
│         │                   │                   │                        │
│  ┌──────▼──────┐   ┌────────▼───────┐   ┌──────▼──────┐                │
│  │  Providers  │   │ Tool Registry  │   │   Memory    │                │
│  │  模型提供商  │   │   工具注册表   │   │   记忆存储  │                │
│  └─────────────┘   └────────┬───────┘   └─────────────┘                │
│                             │                                            │
│              ┌──────────────┼──────────────┐                            │
│              │              │              │                             │
│       ┌──────▼──────┐ ┌─────▼─────┐ ┌─────▼─────┐                      │
│       │ Filesystem  │ │   Shell   │ │    Web    │                      │
│       │   Tools     │ │   Tools   │ │   Tools   │                      │
│       └─────────────┘ └───────────┘ └───────────┘                      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 请求处理流程

```
用户消息 → 渠道适配器 → 消息队列 → 限流检查 → ChannelMessageHandler
                                              │
                                              ▼
                                         AgentLoop
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    │                         │                         │
                    ▼                         ▼                         ▼
            Context Builder            Tool Execution            Memory Store
                    │                         │                         │
                    ▼                         ▼                         ▼
            构建消息上下文            执行工具/记录审计          存储/检索记忆
                    │                         │                         │
                    └─────────────────────────┼─────────────────────────┘
                                              │
                                              ▼
                                        流式响应
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    │                         │                         │
                    ▼                         ▼                         ▼
              WebSocket                  渠道回复                   审计日志
             (Web UI 实时)            (飞书/钉钉等)
```

---

## 3. 核心模块设计

### 3.1 Agent 模块

**文件**: `backend/modules/agent/`

#### 核心组件

| 组件 | 文件 | 描述 |
|------|------|------|
| AgentLoop | `loop.py` | AI 处理主循环，负责消息处理、LLM 调用、工具执行 |
| ContextBuilder | `context.py` | 构建消息上下文，管理对话历史 |
| MemoryStore | `memory.py` | 长期记忆存储和检索 |
| SkillsLoader | `skills.py` | 技能加载和管理 |
| SubagentManager | `subagent.py` | 子 Agent 管理（多 Agent 协作） |

#### AgentLoop 工作流程

```
1. 接收用户消息
2. 通过 ContextBuilder 构建消息上下文（包含记忆、技能、规则）
3. 调用 LLM Provider 获取响应
4. 如果 LLM 返回工具调用:
   - 执行工具
   - 记录工具调用审计日志
   - 将工具结果添加到上下文
   - 继续下一轮迭代
5. 如果没有工具调用，返回最终响应
6. 保存到会话历史
```

### 3.2 Providers 模块

**文件**: `backend/modules/providers/`

#### 核心组件

| 组件 | 文件 | 描述 |
|------|------|------|
| LiteLLMProvider | `litellm_provider.py` | 基于 LiteLLM 的模型提供商，支持多种 LLM |
| LocalProvider | `local_provider.py` | 本地模型支持（Ollama 等） |
| Registry | `registry.py` | Provider 注册和发现 |
| ToolParser | `tool_parser.py` | 工具调用解析 |

#### 支持的模型提供商

- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude 系列)
- 本地部署 (Ollama, vLLM)
- 其他兼容 OpenAI API 的提供商

### 3.3 Tools 模块

**文件**: `backend/modules/tools/`

#### 核心组件

| 组件 | 文件 | 描述 |
|------|------|------|
| ToolRegistry | `registry.py` | 工具注册表，管理所有工具的注册和执行 |
| Filesystem Tools | `filesystem.py` | 文件读写、目录列表、文件编辑 |
| Shell Tools | `shell.py` | Shell 命令执行（带安全检查） |
| Web Tools | `web.py` | Web 搜索、网页抓取 |
| Memory Tool | `memory_tool.py` | 记忆管理工具 |
| Image Uploader | `image_uploader.py` | 图片上传（支持 OSS） |
| File Audit Logger | `file_audit_logger.py` | 工具调用审计日志 |

#### 安全特性

- **工作空间限制**: 文件操作限制在指定工作空间内
- **危险命令检测**: 自动阻止危险 Shell 命令（rm -rf, format 等）
- **超时控制**: Shell 命令执行超时限制
- **输出截断**: 长输出自动截断
- **审计日志**: 所有工具调用记录到文件

### 3.4 Channels 模块

**文件**: `backend/modules/channels/`

#### 核心组件

| 组件 | 文件 | 描述 |
|------|------|------|
| ChannelManager | `manager.py` | 渠道管理器，管理所有渠道的启动和停止 |
| ChannelMessageHandler | `handler.py` | 消息处理器，统一处理来自各渠道的消息 |
| FeishuAdapter | `feishu.py` | 飞书适配器 |
| DingTalkAdapter | `dingtalk.py` | 钉钉适配器 |
| QQAdapter | `qq.py` | QQ 适配器 |
| TelegramAdapter | `telegram.py` | Telegram 适配器 |

#### 渠道消息处理流程

```
1. 渠道接收到消息
2. 转换为统一的 ChannelMessage 格式
3. 发送到 EnterpriseMessageQueue
4. 限流器检查（防止频率过高）
5. ChannelMessageHandler 处理
6. AgentLoop 生成响应
7. 通过原渠道发送回复
```

### 3.5 Cron 模块

**文件**: `backend/modules/cron/`

#### 核心组件

| 组件 | 文件 | 描述 |
|------|------|------|
| CronScheduler | `scheduler.py` | Cron 调度器，解析 cron 表达式并触发任务 |
| CronExecutor | `executor.py` | Cron 执行器，执行定时任务 |
| CronService | `service.py` | Cron 服务，提供数据库操作接口 |

#### 定时任务类型

- **心跳任务**: 定期问候用户
- **研究任务**: 定期研究和总结
- **自定义任务**: 用户配置的定时提醒

### 3.6 Messaging 模块

**文件**: `backend/modules/messaging/`

#### 核心组件

| 组件 | 文件 | 描述 |
|------|------|------|
| EnterpriseMessageQueue | `enterprise_queue.py` | 企业级消息队列，支持去重 |
| RateLimiter | `rate_limiter.py` | 限流器，防止消息频率过高 |

### 3.7 WebSocket 模块

**文件**: `backend/ws/`

#### 核心组件

| 组件 | 文件 | 描述 |
|------|------|------|
| Connection Handler | `connection.py` | WebSocket 连接处理 |
| Events | `events.py` | WebSocket 事件定义 |
| Streaming | `streaming.py` | 流式响应处理 |
| Tool Notifications | `tool_notifications.py` | 工具执行通知 |
| Task Notifications | `task_notifications.py` | 任务进度通知 |

---

## 4. 数据设计

### 4.1 数据库模型

**文件**: `backend/models/`

| 模型 | 文件 | 描述 |
|------|------|------|
| Session | `session.py` | 会话记录 |
| Message | `message.py` | 消息记录 |
| CronJob | `cron_job.py` | 定时任务 |
| Task | `task.py` | 后台任务 |
| Personality | `personality.py` | AI 性格配置 |
| Setting | `setting.py` | 系统设置 |
| ToolConversation | `tool_conversation.py` | 工具调用对话记录 |

### 4.2 数据库连接

**文件**: `backend/database.py`

```python
# 数据库配置
DATABASE_URL = "sqlite+aiosqlite:///data/aie.db"
SYNC_DATABASE_URL = "sqlite:///data/aie.db"

# 异步会话工厂
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession)

# 同步会话工厂
SessionLocal = sessionmaker(sync_engine)
```

---

## 5. 配置系统

### 5.1 配置文件

**主配置文件**: `config/config.yaml`

### 5.2 环境变量

**示例文件**: `.env.example`

```bash
# 模型配置
MODEL_PROVIDER=openai
MODEL_NAME=gpt-4

# API 密钥
OPENAI_API_KEY=your-api-key

# 服务器配置
HOST=0.0.0.0
PORT=8000
```

### 5.3 配置加载

**文件**: `backend/modules/config/loader.py`

配置加载顺序:
1. 默认值
2. config.yaml 配置文件
3. 环境变量
4. 命令行参数

---

## 6. 安全设计

### 6.1 认证中间件

**文件**: `backend/modules/auth/middleware.py`

- 本地访问免认证
- 远程访问需要 Token 认证
- 支持会话管理

### 6.2 命令沙箱

- 危险命令检测
- 工作空间限制
- 超时控制

### 6.3 审计日志

**文件**: `backend/modules/tools/file_audit_logger.py`

记录内容:
- 工具调用开始/结束
- 工具参数
- 执行结果
- 耗时统计

---

## 7. 部署架构

### 7.1 开发环境

```
单进程模式:
┌─────────────────────┐
│   FastAPI Server    │
│   + Frontend        │
│   + Channels        │
│   + Cron            │
└─────────────────────┘
         │
         ▼
    SQLite DB
```

### 7.2 生产环境

```
多进程/容器模式:
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  API Server  │  │ Channel Pods │  │  Cron Worker │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └─────────────────┼─────────────────┘
                         │
       ┌─────────────────┼─────────────────┐
       │                 │                 │
       ▼                 ▼                 ▼
┌────────────┐  ┌────────────┐  ┌────────────┐
│ PostgreSQL │  │   Redis    │  │    NFS     │
└────────────┘  └────────────┘  └────────────┘
```

---

## 8. 性能优化

### 8.1 异步处理
- 所有 I/O 操作使用异步
- 支持并发工具执行

### 8.2 缓存策略
- 记忆缓存
- 配置缓存

### 8.3 连接池
- 数据库连接池
- HTTP 连接池

---

## 9. 监控与日志

### 9.1 日志系统

使用 Loguru 进行日志管理:
- INFO: 正常操作
- WARNING: 潜在问题
- ERROR: 错误情况
- DEBUG: 调试信息

### 9.2 监控指标
- 请求响应时间
- 工具执行成功率
- 渠道连接状态
- 队列积压情况
