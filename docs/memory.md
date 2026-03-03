# 记忆系统 (Memory System)

> CountBot 的长期记忆子系统，提供基于文件的行式记忆存储、关键词搜索、LLM 驱动的对话自动总结，以及面向 Agent 的记忆工具。

## 目录

- [设计理念](#设计理念)
- [架构概览](#架构概览)
- [存储格式](#存储格式)
- [核心组件](#核心组件)
  - [MemoryStore](#memorystore)
  - [ConversationSummarizer](#conversationsummarizer)
  - [MessageAnalyzer](#messageanalyzer)
  - [Memory Tools](#memory-tools)
- [API 接口](#api-接口)
- [前端集成](#前端集成)
- [Agent 集成](#agent-集成)
- [会话总结流程](#会话总结流程)
- [配置参数](#配置参数)
- [测试](#测试)
- [设计决策](#设计决策)

## 设计理念

CountBot 的记忆系统遵循以下原则：

1. **简单透明** — 记忆以纯文本文件存储（`MEMORY.md`），用户可直接查看和编辑
2. **LLM 驱动** — 对话总结由 LLM 完成，不依赖自定义 NLP 管道（无 TF-IDF、无实体识别）
3. **行式结构** — 每行一条记忆，格式固定，便于追加、搜索和删除
4. **Agent 原生** — 记忆以工具形式暴露给 Agent，Agent 自主决定何时读写
5. **Provider 无关** — 不绑定特定 LLM 提供商，通过 `chat_stream` 统一接口调用

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                        Agent Loop                            │
│                                                              │
│  Agent 通过工具调用读写记忆:                                   │
│  ┌──────────────┐ ┌────────────────┐ ┌──────────────────┐   │
│  │ memory_write  │ │ memory_search  │ │  memory_read     │   │
│  └──────┬───────┘ └───────┬────────┘ └────────┬─────────┘   │
│         │                 │                    │             │
│         └─────────────────┼────────────────────┘             │
│                           │                                  │
│                    ┌──────┴──────┐                           │
│                    │ MemoryStore │ ← 核心存储引擎             │
│                    └──────┬──────┘                           │
│                           │                                  │
│                    ┌──────┴──────┐                           │
│                    │ MEMORY.md   │ ← 纯文本文件               │
│                    └─────────────┘                           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   会话总结流程                                │
│                                                              │
│  用户点击 🧠 按钮                                             │
│       │                                                      │
│       ▼                                                      │
│  SessionPanel.vue → POST /api/chat/sessions/{id}/summarize  │
│       │                                                      │
│       ▼                                                      │
│  MessageAnalyzer.format_messages_for_summary()               │
│  (过滤寒暄，格式化对话)                                       │
│       │                                                      │
│       ▼                                                      │
│  CONVERSATION_TO_MEMORY_PROMPT → LLM (chat_stream)          │
│  (LLM 生成一行总结)                                          │
│       │                                                      │
│       ▼                                                      │
│  MemoryStore.append_entry(source, summary)                   │
│  (追加到 MEMORY.md)                                          │
└─────────────────────────────────────────────────────────────┘
```

## 存储格式

记忆存储在工作空间的 `memory/MEMORY.md` 文件中，每行一条记忆，格式为：

```
日期|来源|内容事项1；事项2；事项3
```

### 字段说明

| 字段 | 格式 | 说明 |
|------|------|------|
| 日期 | `YYYY-MM-DD` | 记忆写入日期 |
| 来源 | 字符串 | 记忆来源渠道标识 |
| 内容 | 中文分号分隔 | 一条或多条事项，用 `；` 分隔 |

### 来源标识

| 来源 | 说明 |
|------|------|
| `web-chat` | Web UI 对话 |
| `telegram` | Telegram 渠道 |
| `dingtalk` | 钉钉渠道 |
| `feishu` | 飞书渠道 |
| `qq` | QQ 渠道 |
| `cron` | 定时任务 |
| `auto-overflow` | 上下文滚动压缩自动写入 |
| `system` | 系统自动写入 |

### 示例

```
2026-02-15|web-chat|用户询问天气API方案；决定使用OpenWeatherMap；缓存策略选Redis TTL=3600s
2026-02-15|telegram|用户要求每天早上9点发送日报；已创建cron任务
2026-02-14|web-chat|项目使用Vue3+TypeScript前端；后端FastAPI+SQLAlchemy
2026-02-14|dingtalk|用户偏好Python开发；IDE使用VS Code；终端用iTerm2
```

## 核心组件

### MemoryStore

**文件**: `backend/modules/agent/memory.py`

记忆存储引擎，负责文件级别的读写操作。

```python
from backend.modules.agent.memory import MemoryStore
from pathlib import Path

memory = MemoryStore(Path("workspace/memory"))
```

#### 方法列表

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `append_entry(source, content)` | `str, str` | `int` (行号) | 追加一条记忆 |
| `read_lines(start, end?)` | `int, int\|None` | `str` | 按行号读取（1-based） |
| `search(keywords, max_results=15, match_mode="or")` | `list[str], int, str` | `str` | 关键词搜索（支持 or/and 模式） |
| `delete_lines(line_numbers)` | `list[int]` | `int` (删除数) | 删除指定行 |
| `get_recent(count=10)` | `int` | `str` | 获取最近 N 条 |
| `get_stats()` | — | `dict` | 统计信息 |
| `read_all()` | — | `str` | 读取全部内容 |
| `write_all(content)` | `str` | `None` | 覆盖写入 |
| `get_line_count()` | — | `int` | 总行数 |

#### 搜索行为

- 支持两种匹配模式：
  - `or` 模式（默认）：任意关键词匹配即可
  - `and` 模式：所有关键词都必须匹配
- 不区分大小写
- 默认最多返回 15 条结果，可通过 `max_results` 参数控制
- 超出限制时返回提示 `"共 N 条匹配，仅显示前 M 条"`
- 搜索出错或无匹配时不会返回全部记忆，避免上下文溢出

#### 使用示例

```python
# 写入
line_num = memory.append_entry("web-chat", "用户偏好Python；项目用FastAPI")
# → 返回行号，如 42

# 搜索（OR 模式，默认）
result = memory.search(["python", "fastapi"])
# → "[15] 2026-02-14|web-chat|项目使用FastAPI后端；Python 3.11"
# → "[42] 2026-02-15|web-chat|用户偏好Python；项目用FastAPI"

# 搜索（AND 模式）
result = memory.search(["python", "fastapi"], match_mode="and")
# → "[42] 2026-02-15|web-chat|用户偏好Python；项目用FastAPI"

# 按行读取
result = memory.read_lines(42)
# → "[42] 2026-02-15|web-chat|用户偏好Python；项目用FastAPI"

# 范围读取
result = memory.read_lines(40, 45)

# 最近记忆
result = memory.get_recent(5)

# 统计
stats = memory.get_stats()
# → {"total": 42, "sources": {"web-chat": 30, "telegram": 12}, "date_range": "2026-01-01 ~ 2026-02-15"}
```

### ConversationSummarizer

**文件**: `backend/modules/agent/memory.py`

对话总结器，使用 LLM 将对话历史总结为一行记忆条目。

```python
from backend.modules.agent.memory import ConversationSummarizer

summarizer = ConversationSummarizer(provider=llm_provider, char_limit=2000)
```

#### 方法列表

| 方法 | 说明 |
|------|------|
| `summarize_conversation(messages, previous_summary="")` | 异步总结对话，返回总结文本 |
| `should_summarize(messages, message_threshold=20, char_threshold=10000)` | 判断是否需要总结 |
| `get_messages_to_keep(messages, keep_recent=10)` | 分割消息为待总结和待保留两部分 |

#### 总结流程

1. `MessageAnalyzer.format_messages_for_summary()` 格式化消息（过滤寒暄）
2. 使用 `CONVERSATION_TO_MEMORY_PROMPT` 或 `RECURSIVE_SUMMARY_PROMPT` 构建提示词
3. 通过 `provider.chat_stream()` 调用 LLM 生成总结
4. 返回纯文本总结（多事项用 `；` 分隔）

#### 总结触发条件

- 消息数量超过 20 条（`message_threshold`）
- 总字符数超过 10000（`char_threshold`）
- 满足任一条件即触发

### MessageAnalyzer

**文件**: `backend/modules/agent/analyzer.py`

消息分析器，提供对话消息的预处理能力。

#### 寒暄过滤

`MessageAnalyzer` 维护一个类级别的 `_SKIP_PREFIXES` 元组，包含常见的无意义短消息前缀：

```python
_SKIP_PREFIXES = (
    "好的", "知道了", "明白", "收到", "谢谢", "好", "行",
    "嗯", "哦", "ok", "OK", "Ok", "嗯嗯", "哦哦", "好好",
    "了解", "可以", "没问题", "对", "是的", "没错", "确实",
    "哈哈", "呵呵", "嘻嘻", "666", "👍", "🙏", "感谢",
    "thanks", "thx", "yes", "no", "yep", "nope", "sure",
    "got it", "noted", "fine", "cool", "nice",
)
```

过滤规则：消息长度 ≤ 8 且以上述前缀开头时跳过。这意味着 `"好的"` 会被过滤，但 `"好的，我来帮你分析一下"` 不会。

#### 方法列表

| 方法 | 说明 |
|------|------|
| `format_messages_for_summary(messages, max_chars=4000)` | 格式化消息为文本，过滤寒暄，截断过长内容 |
| `should_summarize(messages, message_threshold=20, char_threshold=10000)` | 判断是否需要总结 |
| `split_messages(messages, keep_recent=10)` | 分割消息为 (待总结, 待保留) |

### Memory Tools

**文件**: `backend/modules/tools/memory_tool.py`

面向 Agent 的记忆工具，以 LLM Function Calling 的形式暴露给 Agent。

#### memory_write

写入一条记忆到长期记忆文件。

```json
{
  "name": "memory_write",
  "parameters": {
    "content": "用户偏好Python开发；项目使用Vue3前端"
  }
}
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `content` | string | ✅ | — | 记忆内容，多事项用 `；` 分隔 |

⚠️ **注意**：来源渠道（source）由系统自动设置，无需手动指定。Web 端默认为 `web-chat`，渠道端自动使用对应的渠道名称（如 `telegram`、`dingtalk` 等）。

返回示例：`"已写入记忆第 42 行（共 42 条）"`

#### memory_search

搜索长期记忆，支持多关键词搜索和 OR/AND 匹配模式。

```json
{
  "name": "memory_search",
  "parameters": {
    "keywords": "python fastapi",
    "max_results": 15,
    "match_mode": "or"
  }
}
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `keywords` | string | ✅ | — | 搜索关键词，空格分隔 |
| `max_results` | integer | ❌ | `15` | 最大返回条数 |
| `match_mode` | string | ❌ | `"or"` | 匹配模式：`"or"`（任意匹配）或 `"and"`（全部匹配） |

返回示例（OR 模式）：
```
记忆库共 42 条

[10] 2026-02-14|web-chat|用户偏好Python开发；IDE使用VS Code
[15] 2026-02-14|web-chat|项目使用FastAPI后端；Python 3.11
[42] 2026-02-15|web-chat|用户偏好Python开发；项目用FastAPI
```

返回示例（AND 模式）：
```
记忆库共 42 条

[15] 2026-02-14|web-chat|项目使用FastAPI后端；Python 3.11
[42] 2026-02-15|web-chat|用户偏好Python开发；项目用FastAPI
```

#### memory_read

按行号读取记忆，或读取最近 N 条。

```json
{
  "name": "memory_read",
  "parameters": {
    "start_line": 40,
    "end_line": 45
  }
}
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `start_line` | integer | ❌ | — | 起始行号（1-based） |
| `end_line` | integer | ❌ | — | 结束行号（包含） |
| `recent_count` | integer | ❌ | `10` | 不指定行号时读取最近 N 条 |

## API 接口

记忆系统通过 REST API 暴露给前端和外部调用方。

**基础路径**: `/api/memory`

### GET /api/memory/long-term

读取全部记忆内容。

**响应**:
```json
{
  "content": "2026-02-15|web-chat|用户偏好Python\n2026-02-15|telegram|API限流100req/min"
}
```

### PUT /api/memory/long-term

覆盖写入全部记忆（用于前端编辑器保存）。

**请求体**:
```json
{
  "content": "2026-02-15|web-chat|用户偏好Python\n2026-02-15|telegram|API限流100req/min"
}
```

**响应**:
```json
{
  "success": true,
  "message": "Memory updated"
}
```

### GET /api/memory/stats

获取记忆统计信息。

**响应**:
```json
{
  "total": 42,
  "sources": {
    "web-chat": 30,
    "telegram": 8,
    "dingtalk": 4
  },
  "date_range": "2026-01-01 ~ 2026-02-15"
}
```

### GET /api/memory/recent?count=10

获取最近 N 条记忆。

**参数**: `count` (int, 默认 10)

**响应**:
```json
{
  "content": "[41] 2026-02-15|web-chat|...\n[42] 2026-02-15|telegram|..."
}
```

### POST /api/memory/search

搜索记忆。

**请求体**:
```json
{
  "keywords": "python fastapi",
  "max_results": 15
}
```

**响应**:
```json
{
  "results": "[15] 2026-02-14|web-chat|...\n[42] 2026-02-15|web-chat|...",
  "total": 42
}
```

### POST /api/chat/sessions/{session_id}/summarize

总结会话内容并保存到长期记忆。

**响应**:
```json
{
  "success": true,
  "summary": "讨论了API设计方案；决定使用RESTful风格；认证方案选JWT",
  "message": "已保存到记忆第 43 行（共 43 条）"
}
```

## 前端集成

### 组件结构

```
frontend/src/modules/memory/
├── MemoryPanel.vue      # 记忆面板容器（切换查看/编辑模式）
├── MemoryViewer.vue     # 记忆查看器（显示 MEMORY.md 内容）
├── MemoryEditor.vue     # 记忆编辑器（直接编辑 MEMORY.md）
└── MemorySearch.vue     # 记忆搜索（本地关键词搜索）
```

### 状态管理

**文件**: `frontend/src/store/memory.ts`

使用 Pinia store 管理记忆状态：

```typescript
const memoryStore = useMemoryStore()

// 加载记忆
await memoryStore.loadLongTermMemory()

// 保存记忆
await memoryStore.saveLongTermMemory(content)

// 本地搜索（不调用后端 API）
const results = memoryStore.searchMemory("python fastapi")
// → [{ line: 42, content: "2026-02-15|web-chat|...", type: "long-term", date: "2026-02-15" }]
```

### 会话总结按钮

**文件**: `frontend/src/modules/chat/SessionPanel.vue`

每个会话项右侧有 🧠 按钮，点击后：

1. 弹出确认对话框
2. 调用 `chatAPI.summarizeSessionToMemory(sessionId)`
3. 后端获取会话消息 → 过滤寒暄 → LLM 总结 → 写入 MEMORY.md
4. 前端 toast 提示结果

按钮状态：
- 总结中：图标旋转动画（`.spinning`）
- 防重复点击：`summarizingSessionId` 锁

## Agent 集成

### 系统提示词中的记忆指导

在 `ContextBuilder._get_identity()` 中，系统提示词包含记忆使用指导：

```
## 记忆系统
你有三个记忆工具: memory_write（写入）、memory_search（搜索）、memory_read（读取）。
格式: 日期|来源|事项1；事项2；事项3（一行一条，多事项用；分隔）

**写入时机**: 用户偏好/习惯、重要决策/结论、项目配置/技术细节、用户明确要求记住的内容。
**搜索时机**: 用户问到过往信息、需要了解偏好、不确定是否讨论过某话题时。
**读取时机**: 搜索后查看上下文（按行号），或浏览最近记忆。
**不记录**: 寒暄确认、敏感信息（密码/API key）、临时无长期价值的内容。

**搜索技巧**:
- 默认 OR 模式（任意关键词匹配）：适合广泛搜索
- AND 模式（所有关键词匹配）：适合精确查找
- 来源渠道由系统自动设置，无需手动指定
```

### 工具注册

在 `backend/modules/tools/setup.py` 的 `register_all_tools()` 中，当提供 `memory_store` 参数时注册三个记忆工具：

```python
# Section 8: 注册记忆工具
if memory_store is not None:
    memory_write = MemoryWriteTool(memory_store)
    memory_write.set_channel(channel)  # 设置渠道来源
    tools.register(memory_write)
    tools.register(MemorySearchTool(memory_store))
    tools.register(MemoryReadTool(memory_store))
```

⚠️ **渠道来源设置**：`MemoryWriteTool` 支持通过 `set_channel()` 方法设置当前渠道，写入记忆时会自动使用该渠道作为来源标识。Web 端默认为 `web-chat`，渠道端（Telegram、钉钉等）会自动设置对应的渠道名称。

### 提示词模板

**文件**: `backend/modules/agent/prompts.py`

| 模板 | 用途 |
|------|------|
| `CONVERSATION_TO_MEMORY_PROMPT` | 将对话总结为一行记忆条目 |
| `RECURSIVE_SUMMARY_PROMPT` | 将新对话合并到已有总结 |
| `MEMORY_ENTRY_TEMPLATE` | 记忆条目格式模板 |
| `OVERFLOW_SUMMARY_PROMPT` | 上下文溢出时将旧消息总结为记忆条目 |
| `HEARTBEAT_GREETING_PROMPT` | Heartbeat 主动问候生成提示词 |

## 会话总结流程

完整的会话总结到记忆的数据流：

```
1. 用户点击 SessionPanel.vue 中的 🧠 按钮
   │
2. 前端调用 chatAPI.summarizeSessionToMemory(sessionId)
   │  → POST /api/chat/sessions/{id}/summarize
   │
3. 后端 summarize_session_to_memory() 处理:
   │
   ├─ 3a. 从数据库获取会话消息
   │       SessionManager.get_messages(session_id)
   │
   ├─ 3b. 格式化消息
   │       MessageAnalyzer.format_messages_for_summary()
   │       - 过滤寒暄（长度≤8 且匹配 _SKIP_PREFIXES）
   │       - 截断过长内容（>300字符）
   │       - 限制总字符数（max_chars=4000）
   │
   ├─ 3c. 构建提示词
   │       CONVERSATION_TO_MEMORY_PROMPT.format(messages=formatted)
   │
   ├─ 3d. 调用 LLM 生成总结
   │       provider.chat_stream(messages=[...], temperature=0.3)
   │       - 收集所有 chunk 拼接为完整响应
   │
   ├─ 3e. 检查是否需要记录
   │       如果 LLM 返回 "无需记录"，直接返回
   │
   └─ 3f. 写入记忆
          MemoryStore.append_entry(source=session_name, content=summary)
          → 追加一行到 MEMORY.md
```

## 配置参数

| 参数 | 位置 | 默认值 | 说明 |
|------|------|--------|------|
| 记忆目录 | `workspace/memory/` | 工作空间下 | 记忆文件存储目录 |
| 记忆文件 | `MEMORY.md` | — | 记忆存储文件名 |
| 搜索默认条数 | `max_results` | `15` | 搜索默认返回条数 |
| 搜索默认模式 | `match_mode` | `"or"` | 搜索默认匹配模式（or/and） |
| 总结字符限制 | `char_limit` | `2000` | ConversationSummarizer 字符限制 |
| 总结消息阈值 | `message_threshold` | `20` | 触发自动总结的消息数 |
| 总结字符阈值 | `char_threshold` | `10000` | 触发自动总结的总字符数 |
| 保留最近消息 | `keep_recent` | `10` | 总结时保留最近 N 条消息 |
| 格式化最大字符 | `max_chars` | `4000` | 格式化消息的最大字符数 |
| 寒暄过滤阈值 | 长度 ≤ 8 | — | 短于等于 8 字符且匹配前缀时过滤 |
| 溢出总结最小阈值 | 3 条 | — | 溢出消息少于 3 条时不总结 |
| LLM 温度 | `temperature` | `0.3` | 总结时使用的温度参数 |

## 测试

**文件**: `tests/test_memory.py`

运行测试：

```bash
python tests/test_memory.py
```

测试覆盖 13 个测试用例：

| 测试 | 说明 |
|------|------|
| 空状态 | 空记忆库的各种操作返回正确 |
| 写入 | `append_entry` 返回正确行号 |
| 读取 | 单行、范围、边界修正 |
| 搜索 | 单词、多词AND、大小写、无匹配、空关键词 |
| 搜索限制 | 默认15条、自定义条数、不截断 |
| 最近记忆 | `get_recent` 返回正确条数 |
| 删除 | 删除指定行、删除不存在的行 |
| 统计 | 来源分布、日期范围 |
| 覆盖写入 | `write_all` 正确覆盖 |
| 寒暄过滤 | `MessageAnalyzer` 正确过滤短消息 |
| should_summarize | 消息数和字符数阈值判断 |
| split_messages | 消息分割正确 |
| 工具参数 | 三个工具的参数定义正确 |
| 工具执行 | 三个工具的 `execute` 方法正确 |
| 工具搜索限制 | 通过工具搜索时的返回条数限制 |

## 上下文滚动压缩 (Overflow Summarization)

当对话消息数超过 `max_history_messages` 时，系统会自动将溢出的旧消息总结写入 MEMORY.md，避免有价值的信息随窗口截断丢失。

### 工作原理

```
用户发送消息
  │
  ▼
chat.py send_message()
  │
  ├─ session_manager.summarize_overflow()
  │   │
  │   ├─ 计算总消息数，判断是否超过 max_history
  │   │
  │   ├─ 查询 Session.last_summarized_msg_id
  │   │   └─ 跳过已总结过的消息，避免重复
  │   │
  │   ├─ 获取溢出的、尚未总结的 user/assistant 消息
  │   │
  │   ├─ MessageAnalyzer.format_messages_for_summary()
  │   │
  │   ├─ OVERFLOW_SUMMARY_PROMPT → LLM (temperature=0.3)
  │   │
  │   ├─ MemoryStore.append_entry(source="auto-overflow", content=summary)
  │   │
  │   └─ 更新 Session.last_summarized_msg_id
  │
  └─ session_manager.get_history_with_summary()
      └─ 正常加载最近 max_history 条消息
```

### 关键设计

| 要素 | 说明 |
|------|------|
| 触发时机 | 每次发送消息前，在加载历史之前调用 `summarize_overflow()` |
| 去重机制 | `Session.last_summarized_msg_id` 记录已总结到的消息 ID，只总结新溢出的部分 |
| 最小阈值 | 溢出消息中 user/assistant 少于 3 条时跳过总结（太少不值得） |
| 来源标识 | 写入 MEMORY.md 时 source 为 `auto-overflow` |
| 提示词 | `OVERFLOW_SUMMARY_PROMPT`，与手动总结类似但强调"即将被截断的旧对话" |
| 数据库支持 | `sessions` 表的 `last_summarized_msg_id` 列（通过数据库迁移添加） |
| 消息过滤 | 只总结 `user` 和 `assistant` 角色的消息，跳过 `system` 和 `tool` 消息 |
| 寒暄过滤 | 通过 `MessageAnalyzer.format_messages_for_summary()` 自动过滤短寒暄消息 |

### 示例

当 `max_history_messages=100`，会话有 120 条消息时：

1. 溢出 20 条旧消息
2. 过滤出其中的 user/assistant 消息
3. LLM 总结为一行记忆条目
4. 写入 MEMORY.md：`2026-02-17|auto-overflow|用户讨论了API设计方案；决定使用JWT认证；...`
5. 更新 `last_summarized_msg_id` 为第 20 条消息的 ID
6. 下次溢出时只总结第 20 条之后的新溢出消息

## 设计决策

### 为什么用纯文本文件而不是数据库？

- 用户可直接用文本编辑器查看和修改记忆
- 便于版本控制（git diff 友好）
- 无需额外的数据库表和迁移
- 记忆量通常不大（几百到几千行），文件 I/O 性能足够

### 为什么不用向量数据库做语义搜索？

- 关键词搜索对结构化记忆（`日期|来源|内容`）已经足够
- 避免引入额外依赖（embedding 模型、向量数据库）
- 保持系统简单，降低部署门槛
- 如果未来需要语义搜索，可以在 `MemoryStore` 上层扩展

### 为什么让 LLM 做总结而不是自定义 NLP？

- LLM 理解上下文的能力远超规则引擎
- 避免维护 TF-IDF、实体识别等自定义管道
- 总结质量更高，能提取真正有价值的信息
- Provider 无关，切换模型不影响总结逻辑

### 为什么搜索默认限制 15 条？

- 避免记忆量大时搜索出错导致返回全部内容
- 15 条在大多数场景下足够，且不会占用过多 LLM 上下文
- 可通过 `max_results` 参数按需调整

## 相关文件

| 文件 | 说明 |
|------|------|
| `backend/modules/agent/memory.py` | MemoryStore + ConversationSummarizer |
| `backend/modules/agent/analyzer.py` | MessageAnalyzer |
| `backend/modules/agent/prompts.py` | 提示词模板 |
| `backend/modules/agent/context.py` | 上下文构建器（含记忆指导） |
| `backend/modules/tools/memory_tool.py` | 记忆工具（write/search/read） |
| `backend/modules/tools/setup.py` | 工具注册（Section 8） |
| `backend/api/memory.py` | REST API 端点 |
| `backend/api/chat.py` | 会话总结端点 + 溢出总结调用 |
| `backend/modules/session/manager.py` | SessionManager（含 `summarize_overflow()`） |
| `backend/models/session.py` | Session 模型（含 `last_summarized_msg_id`） |
| `frontend/src/store/memory.ts` | 前端状态管理 |
| `frontend/src/modules/memory/` | 前端记忆组件 |
| `frontend/src/modules/chat/SessionPanel.vue` | 会话总结按钮 |
| `frontend/src/api/endpoints.ts` | API 类型定义 |
| `tests/test_memory.py` | 单元测试 |
