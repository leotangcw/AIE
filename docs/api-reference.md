# API 参考 (API Reference)

> CountBot 完整的 REST API 和 WebSocket 接口参考文档。

## 基础信息

| 项目 | 值 |
|------|-----|
| 基础路径 | `http://localhost:8000` |
| API 前缀 | `/api` |
| WebSocket | `/ws/chat` |
| 认证 | 远程访问时需要 Bearer Token 或 Cookie |
| 响应格式 | JSON |

## 认证

本地访问（`127.0.0.1` / `::1`）无需认证。远程访问时，所有 `/api/*` 和 `/ws/*` 路径（白名单除外）需要认证。

### 认证方式

- **Cookie**: `CountBot_token=<token>`
- **Header**: `Authorization: Bearer <token>`
- **WebSocket**: `ws://host/ws/chat?token=<token>`

### 白名单路径（无需认证）

- `/api/auth/*` — 认证相关接口
- `/api/health` — 健康检查
- `/docs` — API 文档
- `/openapi.json` — OpenAPI 规范

详见 [auth.md](./auth.md)。

## 健康检查

### GET /api/health

检查服务是否正常运行。

**响应** `200`:
```json
{
  "status": "ok"
}
```

---

## 认证 (Auth)

### GET /api/auth/status

查询当前认证状态。

**响应** `200`:
```json
{
  "is_local": false,
  "auth_enabled": true,
  "authenticated": false
}
```

### POST /api/auth/setup

首次设置密码（仅当未设置密码时可用）。

**请求体**:
```json
{
  "username": "admin",
  "password": "MyPass123"
}
```

**响应** `200`:
```json
{
  "success": true,
  "message": "密码设置成功",
  "token": "session_token_xxx"
}
```

### POST /api/auth/login

登录。

**请求体**:
```json
{
  "username": "admin",
  "password": "MyPass123"
}
```

**响应** `200`:
```json
{
  "success": true,
  "message": "登录成功",
  "token": "session_token_xxx"
}
```

### POST /api/auth/logout

登出，清除 session。

### POST /api/auth/change-password

修改密码。

**请求体**:
```json
{
  "old_password": "MyPass123",
  "new_password": "NewPass456"
}
```

---

## 聊天 (Chat)

### POST /api/chat/send

发送消息并获取 SSE 流式响应。

**请求体**:
```json
{
  "message": "你好",
  "session_id": "uuid",
  "media": []
}
```

**响应**: `text/event-stream`

### GET /api/chat/sessions

获取会话列表。

**响应** `200`:
```json
[
  {
    "id": "uuid",
    "name": "New Chat",
    "created_at": "2026-02-15T10:00:00",
    "updated_at": "2026-02-15T10:30:00",
    "message_count": 10
  }
]
```

### POST /api/chat/sessions

创建新会话。

**请求体**:
```json
{
  "name": "我的会话"
}
```

**响应** `201`:
```json
{
  "id": "uuid",
  "name": "我的会话",
  "created_at": "2026-02-15T10:00:00"
}
```

### GET /api/chat/sessions/{session_id}

获取会话详情。

### PUT /api/chat/sessions/{session_id}

更新会话（重命名等）。

**请求体**:
```json
{
  "name": "新名称"
}
```

### DELETE /api/chat/sessions/{session_id}

删除会话及其所有消息。

### GET /api/chat/sessions/{session_id}/messages

获取会话消息列表。

**参数**: `limit` (int, 默认 100), `offset` (int, 默认 0)

**响应** `200`:
```json
[
  {
    "id": "uuid",
    "role": "user",
    "content": "你好",
    "created_at": "2026-02-15T10:00:00"
  },
  {
    "id": "uuid",
    "role": "assistant",
    "content": "你好！有什么可以帮你的？",
    "created_at": "2026-02-15T10:00:01"
  }
]
```

### POST /api/chat/sessions/{session_id}/summarize

总结会话内容并保存到长期记忆。

**响应** `200`:
```json
{
  "success": true,
  "summary": "讨论了API设计方案；决定使用RESTful风格",
  "message": "已保存到记忆第 43 行（共 43 条）"
}
```

---

## 记忆 (Memory)

### GET /api/memory/long-term

读取全部长期记忆内容。

**响应** `200`:
```json
{
  "content": "2026-02-15|web-chat|用户偏好Python\n2026-02-14|telegram|..."
}
```

### PUT /api/memory/long-term

覆盖写入全部记忆。

**请求体**:
```json
{
  "content": "记忆内容..."
}
```

### GET /api/memory/stats

获取记忆统计信息。

**响应** `200`:
```json
{
  "total": 42,
  "sources": {"web-chat": 30, "telegram": 12},
  "date_range": "2026-01-01 ~ 2026-02-15"
}
```

### GET /api/memory/recent

获取最近记忆。

**参数**: `count` (int, 默认 10)

**响应** `200`:
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

**响应** `200`:
```json
{
  "results": "[15] 2026-02-14|web-chat|...\n[42] 2026-02-15|web-chat|...",
  "total": 42
}
```

---

## 技能 (Skills)

### GET /api/skills

列出所有技能。

**响应** `200`:
```json
[
  {
    "name": "baidu-search",
    "display_name": "百度搜索",
    "description": "使用百度搜索引擎搜索信息",
    "version": "1.0.0",
    "enabled": true,
    "always": false,
    "requirements_met": true
  }
]
```

### POST /api/skills

创建新技能。

**请求体**:
```json
{
  "name": "my-skill",
  "content": "---\nname: 我的技能\ndescription: ...\n---\n# 技能内容"
}
```

### GET /api/skills/{name}

获取技能详情和完整内容。

### PUT /api/skills/{name}

更新技能内容。

**请求体**:
```json
{
  "content": "更新后的 SKILL.md 内容"
}
```

### DELETE /api/skills/{name}

删除技能。

### POST /api/skills/{name}/toggle

启用/禁用技能。

**请求体**:
```json
{
  "enabled": false
}
```

---

## 定时任务 (Cron)

### GET /api/cron/jobs

列出所有定时任务。

**响应** `200`:
```json
[
  {
    "id": "uuid",
    "name": "每日报告",
    "schedule": "0 9 * * *",
    "message": "生成今日工作报告",
    "enabled": true,
    "last_run": "2026-02-15T09:00:00",
    "next_run": "2026-02-16T09:00:00",
    "created_at": "2026-02-01T10:00:00"
  }
]
```

### POST /api/cron/jobs

创建定时任务。

**请求体**:
```json
{
  "name": "每日报告",
  "schedule": "0 9 * * *",
  "message": "生成今日工作报告",
  "enabled": true,
  "channel": "dingtalk",
  "chat_id": "group_xxx",
  "deliver_response": true
}
```

### GET /api/cron/jobs/{id}

获取任务详情（包括完整的 last_response 和 last_error）。

### PUT /api/cron/jobs/{id}

更新任务。

内置任务（`builtin:` 前缀）限制：
- 禁止修改 `name` 和 `message` 字段（返回 403）
- 允许修改 `enabled`、`schedule`、`channel`、`chat_id`、`deliver_response`

### DELETE /api/cron/jobs/{id}

删除任务。

内置任务（`builtin:` 前缀）禁止删除，返回 403。

### POST /api/cron/jobs/{id}/run

手动触发任务执行（异步，立即返回）。

如果任务正在执行中，返回 409 Conflict。

**响应** `200`:
```json
{
  "success": true,
  "message": "任务 '每日报告' 已提交执行"
}
```

### POST /api/cron/validate

验证 Cron 表达式。

**请求体**:
```json
{
  "schedule": "0 9 * * *"
}
```

**响应** `200`:
```json
{
  "valid": true,
  "description": "在第 0 分钟 在 9 点",
  "next_run": "2026-02-16T09:00:00"
}
```

---

## 工具 (Tools)

### GET /api/tools/list

获取所有可用工具列表。

**响应** `200`:
```json
[
  {
    "name": "read_file",
    "description": "Read file content",
    "parameters": { ... }
  },
  {
    "name": "exec",
    "description": "Execute shell command",
    "parameters": { ... }
  }
]
```

### POST /api/tools/execute

手动执行工具。

**请求体**:
```json
{
  "tool_name": "read_file",
  "arguments": {
    "path": "README.md"
  }
}
```

**响应** `200`:
```json
{
  "result": "文件内容...",
  "duration_ms": 15
}
```

### GET /api/tools/conversations

获取工具调用历史。

**参数**: `session_id` (string), `limit` (int, 默认 200)

**响应** `200`:
```json
[
  {
    "id": "uuid",
    "session_id": "session-xxx",
    "tool_name": "exec",
    "arguments": {"command": "ls -la"},
    "result": "total 48\n...",
    "user_message": "查看当前目录",
    "duration_ms": 150,
    "created_at": "2026-02-15T10:00:00"
  }
]
```

---

## 配置 (Settings)

### GET /api/settings

获取完整配置。

### PUT /api/settings

更新配置（部分更新）。

**请求体**:
```json
{
  "model": {
    "temperature": 0.5
  }
}
```

### GET /api/settings/providers

获取 LLM 提供商列表。

**响应** `200`:
```json
[
  {
    "id": "zhipu",
    "name": "智谱 AI",
    "default_api_base": "https://open.bigmodel.cn/api/paas/v4",
    "models": ["glm-4.7-flash", "glm-5"]
  },
  {
    "id": "openai",
    "name": "OpenAI",
    "default_api_base": "https://api.openai.com/v1",
    "models": ["gpt-5.3", "gpt-5.2"]
  }
]
```

### GET /api/settings/personalities

获取性格预设列表。

**响应** `200`:
```json
[
  {
    "id": "grumpy",
    "name": "暴躁老哥",
    "description": "贴吧暴躁老哥附体...",
    "traits": ["暴躁", "嘴硬心软", "网络用语", "实在"]
  }
]
```

---

## 渠道 (Channels)

### GET /api/channels/status

获取所有渠道状态。

**响应** `200`:
```json
{
  "telegram": {"enabled": true, "running": true},
  "dingtalk": {"enabled": true, "running": false, "error": "..."},
  "feishu": {"enabled": false, "running": false}
}
```

### POST /api/channels/{name}/test

测试渠道连接。

**响应** `200`:
```json
{
  "success": true,
  "message": "Connected successfully"
}
```

---

## 后台任务 (Tasks)

### GET /api/tasks

列出子代理任务。

**参数**: `session_id` (string), `status` (string)

### GET /api/tasks/{id}

获取任务详情。

### POST /api/tasks/{id}/cancel

取消运行中的任务。

### DELETE /api/tasks/{id}

删除任务。

### GET /api/tasks/stats

获取任务统计。

---

## 语音 (Audio)

### POST /api/audio/transcribe

语音转文字。

**请求**: `multipart/form-data`，字段 `file`（音频文件）

**响应** `200`:
```json
{
  "text": "转录的文字内容"
}
```

---

## 消息队列 (Queue)

### GET /api/queue/stats

获取消息队列统计。

**响应** `200`:
```json
{
  "inbound_pending": 0,
  "outbound_pending": 0,
  "total_processed": 150
}
```

---

## 系统 (System)

### GET /api/system/info

获取系统信息。

**响应** `200`:
```json
{
  "version": "1.0.0",
  "python_version": "3.11.x",
  "platform": "macOS",
  "workspace": "/path/to/workspace",
  "uptime": 3600
}
```

---

## WebSocket

### /ws/chat

实时聊天 WebSocket 连接。

#### 连接

```javascript
// 本地访问
const ws = new WebSocket("ws://localhost:8000/ws/chat")

// 远程访问（需要认证 token）
const token = localStorage.getItem('CountBot_token')
const ws = new WebSocket(`ws://192.168.x.x:8000/ws/chat?token=${token}`)
```

远程访问时如果 token 无效，服务端会关闭连接（code 4001）。

#### 客户端 → 服务端消息

**订阅会话**:
```json
{
  "type": "subscribe",
  "session_id": "uuid"
}
```

**发送消息**:
```json
{
  "type": "message",
  "session_id": "uuid",
  "content": "你好",
  "media": []
}
```

**取消执行**:
```json
{
  "type": "cancel",
  "session_id": "uuid"
}
```

#### 服务端 → 客户端消息

**流式内容**:
```json
{
  "type": "stream",
  "content": "你好！"
}
```

**流式结束**:
```json
{
  "type": "stream_end"
}
```

**工具调用通知**:
```json
{
  "type": "tool_call",
  "tool_name": "exec",
  "arguments": {"command": "ls"},
  "status": "started"
}
```

**工具结果通知**:
```json
{
  "type": "tool_result",
  "tool_name": "exec",
  "result": "file1.txt\nfile2.txt",
  "duration_ms": 150
}
```

**任务状态通知**:
```json
{
  "type": "task_update",
  "task_id": "uuid",
  "status": "completed",
  "progress": 100
}
```

**错误**:
```json
{
  "type": "error",
  "message": "错误信息"
}
```
