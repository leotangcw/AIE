# AIE - AI Employee

> 企业级 AI 办公助手框架 — 轻量、可扩展、面向国内办公生态

AIE 是一个基于开源生态构建的企业级 AI 智能助手框架，通过整合多个优秀开源项目的能力，逐步发展为一个功能完善的 AI 办公解决方案。

## 核心能力

- **多 Agent 协作** — Pipeline / Graph / Council 三种工作流编排模式，支持团队化多角色协作
- **智能对话** — ReAct 推理循环，支持多模型切换（主模型/子模型）
- **分层记忆** — L0/L1/L2 三级记忆体系 + 向量语义搜索，基于 MCP 协议
- **知识图谱 RAG** — 图结构化知识表示，多模式检索（local/global/hybrid/naive/mix）
- **多渠道接入** — 飞书、钉钉、企业微信、Telegram、Web 等
- **定时任务** — 精确到秒的定时调度，支持心跳主动唤醒
- **企业级消息队列** — 优先级队列、消息去重、死信处理、消费确认
- **技能系统** — 可热加载的技能插件，支持 always 自动激活与按需加载
- **子代理系统** — 独立任务分发、并发控制、心跳监控、自动重试

## 技术栈

| 层级 | 技术选型 |
|------|----------|
| 后端 | Python 3.10+ / FastAPI / SQLAlchemy / Pydantic / LiteLLM |
| 前端 | Vue 3 / TypeScript / Pinia / Vite |
| 实时通信 | WebSocket (流式响应 + 事件推送) |
| 数据存储 | SQLite (开发) / PostgreSQL (生产) |
| 嵌入模型 | BAAI/bge-m3 (本地) / API 回退 |
| LLM | 支持所有 LiteLLM 兼容模型（通义千问、DeepSeek、OpenAI 等） |

## 项目结构

```
AIE/
├── backend/                    # Python 后端
│   ├── api/                    # REST API 路由
│   ├── core/                   # 核心组件 (ModelRegistry, Infrastructure)
│   ├── models/                 # SQLAlchemy 数据模型
│   ├── modules/
│   │   ├── agent/             # Agent 核心 (循环、上下文、工作流、子代理)
│   │   ├── channels/          # 消息渠道适配器
│   │   ├── tools/             # 工具系统 (文件、Shell、Web、多媒体...)
│   │   ├── skills/            # 技能加载器
│   │   ├── graph_rag/         # 知识图谱 RAG (LightRAG)
│   │   ├── memory_mcp_server/ # 分层记忆服务 (MCP 协议)
│   │   ├── providers/         # 多模型提供商注册与路由
│   │   ├── config/            # 配置管理 (Schema + Loader)
│   │   ├── cron/              # 定时任务调度器
│   │   └── messaging/         # 企业级消息队列
│   ├── infrastructure/         # 基础设施 (VectorStore, FileDB)
│   └── ws/                    # WebSocket 连接管理与事件路由
├── frontend/                   # Vue 3 前端
│   └── src/
│       ├── api/               # API 客户端
│       ├── components/        # 通用组件 (ToolCallCard, ModelStatusLights...)
│       ├── modules/           # 业务模块 (chat, teams, heartbeat, settings...)
│       ├── store/             # Pinia 状态管理
│       └── i18n/              # 国际化 (zh-CN / en-US)
├── skills/                     # 技能插件目录
├── config/                     # 运行配置文件
└── docs/                       # 文档
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
cd frontend && npm install
```

### 2. 配置

复制环境配置模板并填入 API Key：

```bash
cp .env.example .env
```

主要配置项：
- `AIE_MODEL_PROVIDER` — 模型提供商 (qwen_bailian / openai / deepseek 等)
- `AIE_MODEL_API_KEY` — 模型 API Key
- `AIE_MODEL_NAME` — 模型名称
- `AIE_PASSWORD` — 访问密码（远程访问必填）

### 3. 启动

```bash
# 后端 (默认端口 8000)
python start_aie.py

# 前端开发服务器
cd frontend && npm run dev

# 或使用一体化启动脚本
python start_desktop.py
```

打开浏览器访问 `http://localhost:5173` 即可使用。

## 团队协作

AIE 支持创建多角色 Agent 团队，通过 `@团队名` 在对话中触发：

- **Pipeline 模式** — 顺序执行，前序输出传递给后序（适合调研+撰写流程）
- **Graph 模式** — 依赖 DAG 自动并行调度（适合并行专家分析）
- **Council 模式** — 多视角评审 + 交叉讨论 + 综合结论（适合决策分析）

## 致谢与参考项目

AIE 站在众多优秀开源项目的肩膀上，以下是主要参考项目和致敬：

### [CountBot](https://github.com/nicepkg/countbot) — 核心基础框架

> AIE Phase 1 的主要代码来源，提供了完整的 Agent 核心架构。

CountBot 是一个轻量级、可扩展的 AI Agent 框架，为中文用户和国内 LLM 优化。AIE 直接继承了其核心架构设计，包括：

- **Agent 核心循环** — ReAct 推理、工具调用、流式响应
- **消息渠道系统** — 飞书、钉钉、QQ、Telegram、微信等多渠道适配
- **工具系统** — 文件操作、Shell 执行、Web 搜索/抓取等 13+ 内置工具
- **记忆系统** — 向量化语义搜索 + 关键词混合检索
- **定时任务** — 精确调度器 + 心跳主动唤醒机制
- **企业级消息队列** — 优先级、去重、死信处理、消费确认
- **认证中间件** — 零配置渐进式安全模型（本地直通 / 远程认证）
- **前端架构** — Vue 3 + TypeScript + Pinia 的完整交互方案

**License**: MIT License — Copyright (c) 2026 CountBot

---

### [OpenViking](https://github.com/volcengine/OpenViking) — 分层记忆设计

> AIE 分层记忆系统的设计灵感来源。

OpenViking 是字节跳动 Volcengine 开源的 AI Agent "Context Database"，提出了 **L0/L1/L2 三级上下文加载范式**。AIE 的记忆系统参考了这一设计理念：

- L0 (Abstract) — 全局抽象层，快速召回
- L1 (Overview) — 主题概览层，平衡精度与效率
- L2 (Detail) — 详细内容层，精确匹配
- URI 层级组织 (`viking://` 协议方案)
- 目录递归检索策略

**License**: Apache License 2.0 — Copyright Volcengine/ByteDance

---

### [Memory-MCP-Server](https://github.com/nicepkg/Memory-MCP-Server) — MCP 记忆服务

> AIE 分层记忆系统的具体实现参考。

Memory-MCP-Server 是一个基于 MCP (Model Context Protocol) 的轻量级记忆模块，实现了 OpenViking 的分层记忆系统。AIE 的 `memory_mcp_server` 模块直接集成了其核心能力：

- 基于 SQLite + sentence-transformers 的本地语义搜索
- MCP JSON-RPC 2.0 协议接口
- 多维度重排序（相关性、热度、时效性、类型匹配）
- 意图分析驱动的查询理解

**License**: MIT License

---

### [LightRAG](https://github.com/HKUDS/LightRAG) — 知识图谱 RAG

> AIE GraphRAG 模块的集成基础。

LightRAG 是一个基于图结构的 RAG 框架，从文档中提取实体和关系构建知识图谱，支持多模态检索。AIE 通过 `graph_rag` 模块集成了其知识图谱能力：

- 实体/关系提取与知识图谱构建
- 多模式检索 (local / global / hybrid / naive / mix)
- 向量化存储与索引
- 文档分块与处理流水线

**License**: MIT License — Copyright (c) 2025 LightRAG Team

---

### [openclaw](https://github.com/nicepkg/openclaw) — 企业级特性参考

> AIE Phase 3 企业级特性的架构参考。

OpenClaw 是一个个人 AI 助手网关控制平面，支持 25+ 消息渠道和语音交互。AIE 在企业级功能方向上参考了其设计理念：

- 多 Agent 协作模式
- 工作流自动化
- 企业级安全与权限管理
- 技能生态系统

**License**: Apache License 2.0

---

### [JiuwenClaw](https://github.com/nicepkg/jiuwenclaw) — 技能演进参考

> AIE 技能系统的演进思路参考。

JiuwenClaw 是一个 Python 智能体，支持华为云 MaaS 和小艺平台集成。AIE 参考了其技能自主演化、上下文压缩卸载、浏览器自动化等设计思路。

**License**: Apache License 2.0

---

## 开源协议

本项目采用 [MIT License](LICENSE) 开源。

由于 AIE 参考和集成了多个开源项目，在此对原始项目的开发者表示感谢。各参考项目的协议要求已在上方致谢部分说明。AIE 中源自这些项目的代码模块已遵循其原始协议要求进行了适配和改造。

## License

MIT License

Copyright (c) 2026 leotangcw

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
