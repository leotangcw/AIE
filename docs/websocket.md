# WebSocket 实时通信

> CountBot 的 WebSocket 子系统，提供实时流式响应、工具执行通知和任务状态推送。

## 目录

- [设计理念](#设计理念)
- [架构概览](#架构概览)
- [连接管理](#连接管理)
- [消息协议](#消息协议)
  - [客户端消息](#客户端消息)
  - [服务端消息](#服务端消息)
- [事件路由](#事件路由)
- [流式推送](#流式推送)
- [工具通知](#工具通知)
- [任务通知](#任务通知)
- [取消机制](#取消机制)
- [前端集成](#前端集成)
- [相关文件](#相关文件)

## 设计理念

1. **会话绑定** — 每个 WebSocket 连接绑定到一个会话，只接收该会话的消息
2. **多连接支持** — 同一会话可有多个连接（多标签页），消息广播到所有连接
3. **流式优先** — LLM 响应逐 chunk 推送，前端实时渲染
4. **结构化消息** — 所有消息使用 JSON 格式，带 `type` 字段区分类型
5. **优雅降级** — 连接断开时自动清理，不影响后台任务

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    前端 (Vue 3)                           │
│                                                          │
│  WebSocket("ws://localhost:8000/ws/chat")                │
│       │                                                  │
│       │ subscribe / message / cancel                     │
│       ▼                                                  │
│  ┌──────────────────────────────────────────────────┐   │
│  │           ConnectionManager                        │   │
│  │                                                    │   │
│  │  connections: dict[conn_id, WebSocket]             │   │
│  │  session_map: dict[conn_id, session_id]            │   │
│  │  session_connections: dict[session_id, set[id]]    │   │
│  └──────────────────────┬───────────────────────────┘   │
│                         │                                │
│                         ▼                                │
│  ┌──────────────────────────────────────────────────┐   │
│  │              route_event()                         │   │
│  │                                                    │   │
│  │  subscribe → bind_session()                        │   │
│  │  message   → handle_message_event()                │   │
│  │  cancel    → cancel_session()                      │   │
│  │  ping      → handle_ping_event()                   │   │
│  └──────────────────────┬───────────────────────────┘   │
│                         │                                │
│                         ▼                                │
│  ┌──────────────────────────────────────────────────┐   │
│  │              AgentLoop                             │   │
│  │                                                    │   │
│  │  process_message() → yield chunks                  │   │
│  │       │                                            │   │
│  │       ├─ send_message_chunk() → 流式内容           │   │
│  │       ├─ send_tool_call() → 工具开始               │   │
│  │       └─ send_tool_result() → 工具结果             │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## 连接管理

**文件**: `backend/ws/connection.py`

### ConnectionManager

管理所有 WebSocket 连接的生命周期。

```python
class ConnectionManager:
    connections: dict[str, WebSocket]           # conn_id → WebSocket
    session_map: dict[str, str]                 # conn_id → session_id
    session_connections: dict[str, set[str]]    # session_id → {conn_ids}
```

#### 连接流程

```
客户端连接 ws://localhost:8000/ws/chat
  │
  ├─ ConnectionManager.connect(websocket)
  │   └─ 分配 connection_id (UUID)
  │
  ├─ 客户端发送 subscribe 事件
  │   └─ ConnectionManager.bind_session(conn_id, session_id)
  │
  ├─ 正常通信...
  │
  └─ 断开连接
      └─ ConnectionManager.disconnect(conn_id)
          └─ 清理 session_map 和 session_connections
```

#### 消息发送

```python
# 发送到指定连接
await manager.send_message(conn_id, message)

# 发送到会话的所有连接
count = await manager.send_to_session(session_id, message)

# 广播到所有连接
count = await manager.broadcast(message)
```

## 消息协议

所有消息使用 JSON 格式。

### 客户端消息

#### subscribe — 订阅会话

```json
{
  "type": "subscribe",
  "session_id": "uuid"
}
```

#### message — 发送消息

```json
{
  "type": "message",
  "session_id": "uuid",
  "content": "你好",
  "media": ["path/to/image.png"]
}
```

#### cancel — 取消执行

```json
{
  "type": "cancel",
  "session_id": "uuid"
}
```

#### unsubscribe — 取消订阅

```json
{
  "type": "unsubscribe",
  "session_id": "uuid"
}
```

#### ping — 心跳

```json
{
  "type": "ping"
}
```

### 服务端消息

#### message_chunk — 流式内容

```json
{
  "type": "message_chunk",
  "content": "你好！",
  "message_id": 1
}
```

#### tool_call — 工具调用开始

```json
{
  "type": "tool_call",
  "tool": "exec",
  "arguments": {"command": "ls -la"},
  "message_id": 2
}
```

#### tool_result — 工具执行结果

```json
{
  "type": "tool_result",
  "tool": "exec",
  "result": "total 48\ndrwxr-xr-x ...",
  "duration": 0.15,
  "message_id": 3
}
```

#### message_complete — 消息完成

```json
{
  "type": "message_complete",
  "message_id": "uuid"
}
```

#### error — 错误

```json
{
  "type": "error",
  "message": "处理消息时出错",
  "code": "PROCESSING_ERROR"
}
```

#### task_update — 任务状态更新

```json
{
  "type": "task_update",
  "task_id": "uuid",
  "status": "completed",
  "progress": 100,
  "result": "任务结果..."
}
```

## 事件路由

**文件**: `backend/ws/events.py`

`route_event()` 根据消息 `type` 分发到对应处理函数：

| type | 处理函数 | 说明 |
|------|----------|------|
| `subscribe` | `handle_subscribe_event()` | 绑定会话 |
| `unsubscribe` | `handle_unsubscribe_event()` | 解绑会话 |
| `message` | `handle_message_event()` | 处理用户消息 |
| `cancel` | `cancel_session()` | 取消执行 |
| `ping` | `handle_ping_event()` | 心跳响应 |

### handle_message_event 流程

```
handle_message_event(data, connection_id)
  │
  ├─ 获取 session_id, content, media
  ├─ 保存用户消息到数据库
  ├─ 获取会话历史
  ├─ 创建 CancelToken
  │
  ├─ AgentLoop.process_message(...)
  │   │
  │   ├─ async for chunk:
  │   │   └─ send_message_chunk(session_id, chunk)
  │   │
  │   └─ (工具调用通知由 AgentLoop 内部发送)
  │
  ├─ 保存 AI 回复到数据库
  ├─ send_message_complete(session_id)
  └─ 清理 CancelToken
```

## 流式推送

**文件**: `backend/ws/streaming.py`

提供两种流式推送策略：

### StreamingResponseHandler

直接推送，可选分块和延迟：

```python
handler = StreamingResponseHandler(
    session_id="uuid",
    chunk_size=50,    # 每块 50 字符
    delay_ms=0,       # 无延迟
)
await handler.stream_iterator(agent_response)
```

### BufferedStreamingHandler

缓冲推送，减少网络开销：

```python
handler = BufferedStreamingHandler(
    session_id="uuid",
    buffer_size=100,         # 缓冲 100 字符
    flush_interval_ms=100,   # 100ms 自动刷新
)
await handler.stream_iterator(agent_response)
```

缓冲策略：
- 缓冲区满（≥ buffer_size）时自动刷新
- 超过 flush_interval_ms 未刷新时自动刷新
- 迭代结束时强制刷新

### 便捷函数

```python
from backend.ws.streaming import stream_response, stream_text

# 流式推送迭代器
stats = await stream_response(session_id, iterator, use_buffer=True)

# 流式推送文本
stats = await stream_text(session_id, "Hello World", chunk_size=50)
```

## 工具通知

**文件**: `backend/ws/tool_notifications.py`

Agent Loop 在工具执行前后发送通知：

```python
# 工具开始执行
await notify_tool_execution(
    session_id=session_id,
    tool_name="exec",
    arguments={"command": "ls -la"},
)

# 工具执行完成
await notify_tool_execution(
    session_id=session_id,
    tool_name="exec",
    arguments={"command": "ls -la"},
    result="total 48\n...",
)

# 工具执行失败
await notify_tool_execution(
    session_id=session_id,
    tool_name="exec",
    arguments={"command": "ls -la"},
    error="Command timed out",
)
```

前端收到通知后在聊天界面展示工具调用卡片。

## 任务通知

**文件**: `backend/ws/task_notifications.py`

子代理任务状态变化时推送通知：

```python
await notify_task_update(
    session_id=session_id,
    task_id="uuid",
    status="completed",
    progress=100,
    result="任务结果...",
)
```

## 取消机制

**文件**: `backend/ws/connection.py`

### CancellationToken

```python
token = get_cancel_token(session_id)
# → 创建或获取该会话的取消令牌

cancel_session(session_id)
# → 设置令牌为已取消状态

cleanup_cancel_token(session_id)
# → 清理令牌
```

Agent Loop 在每次迭代和工具执行前检查 `cancel_token.is_cancelled`，实现即时取消。

## 远程访问认证

WebSocket 连接同样受远程访问认证保护。本地访问（`127.0.0.1` / `::1`）不受影响。

### 认证方式

远程客户端通过 URL query 参数传递 session token：

```
ws://192.168.x.x:8000/ws/chat?token=YOUR_SESSION_TOKEN
```

也支持通过 Cookie（`CountBot_token`）传递。

### 认证失败处理

| 场景 | 服务端行为 | 关闭码 |
|------|-----------|--------|
| 远程访问 + 已设置密码 + 无效/无 token | 关闭连接 | `4001` |
| 远程访问 + 未设置密码 | 放行（需先通过 HTTP 设置密码） | — |
| 本地访问 | 直接放行 | — |

### 前端处理

```typescript
ws.onclose = (event) => {
  if (event.code === 4001) {
    // 认证失败，跳转登录页
    window.location.href = '/login'
  }
}
```

### 防代理绕过

与 HTTP 中间件一致，如果 WebSocket 握手请求包含 `X-Forwarded-For` 头，即使 `client.host` 是本地 IP，也不会被视为本地请求。

详细认证机制参见 [auth.md](./auth.md)。

## 前端集成

前端通过 WebSocket 连接实现实时通信：

```typescript
// 建立连接
const ws = new WebSocket("ws://localhost:8000/ws/chat")

// 订阅会话
ws.send(JSON.stringify({
  type: "subscribe",
  session_id: currentSessionId,
}))

// 发送消息
ws.send(JSON.stringify({
  type: "message",
  session_id: currentSessionId,
  content: userInput,
}))

// 接收消息
ws.onmessage = (event) => {
  const data = JSON.parse(event.data)
  switch (data.type) {
    case "message_chunk":
      appendToChat(data.content)
      break
    case "tool_call":
      showToolCard(data.tool, data.arguments)
      break
    case "tool_result":
      updateToolCard(data.tool, data.result)
      break
    case "message_complete":
      finishMessage()
      break
    case "error":
      showError(data.message)
      break
  }
}

// 取消执行
ws.send(JSON.stringify({
  type: "cancel",
  session_id: currentSessionId,
}))
```

## 相关文件

| 文件 | 说明 |
|------|------|
| `backend/ws/connection.py` | ConnectionManager + 消息类型 |
| `backend/ws/events.py` | 事件路由和处理 |
| `backend/ws/streaming.py` | 流式推送策略 |
| `backend/ws/tool_notifications.py` | 工具执行通知 |
| `backend/ws/task_notifications.py` | 任务状态通知 |
| `backend/app.py` | WebSocket 端点注册 |
