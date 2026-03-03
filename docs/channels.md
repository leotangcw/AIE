# 多渠道系统 (Channels)

> CountBot 的多渠道消息接入系统，支持同时接入 Telegram、钉钉、飞书、QQ、微信等即时通讯平台。

## 目录

- [设计理念](#设计理念)
- [架构概览](#架构概览)
- [核心组件](#核心组件)
  - [BaseChannel](#basechannel)
  - [ChannelManager](#channelmanager)
  - [ChannelMessageHandler](#channelmessagehandler)
- [消息流转](#消息流转)
- [支持的渠道](#支持的渠道)
- [渠道配置](#渠道配置)
- [消息队列](#消息队列)
- [会话管理](#会话管理)
- [内置命令](#内置命令)
- [安全控制](#安全控制)
- [API 接口](#api-接口)
- [添加新渠道](#添加新渠道)
- [相关文件](#相关文件)

## 设计理念

1. **统一抽象** — 所有渠道实现 `BaseChannel` 接口，上层逻辑无需关心具体平台
2. **消息队列** — 入站/出站消息通过 `EnterpriseMessageQueue` 解耦
3. **独立会话** — 每个渠道+聊天 ID 组合维护独立会话
4. **白名单控制** — 每个渠道可配置允许的发送者列表
5. **速率限制** — 通过 `RateLimiter` 防止消息洪水

## 架构概览

```
┌──────────────────────────────────────────────────────────┐
│                    外部平台                                │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐│
│  │  TG  │ │  DT  │ │  FS  │ │  QQ  │ │  WX  │ │  DC  ││
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘│
└─────┼────────┼────────┼────────┼────────┼────────┼─────┘
      │        │        │        │        │        │
┌─────┼────────┼────────┼────────┼────────┼────────┼─────┐
│     ▼        ▼        ▼        ▼        ▼        ▼     │
│  ┌─────────────────────────────────────────────────┐   │
│  │              ChannelManager                      │   │
│  │  channels: dict[name, BaseChannel]               │   │
│  │  start_all() / stop_all()                        │   │
│  └──────────────────┬──────────────────────────────┘   │
│                     │ InboundMessage                    │
│                     ▼                                   │
│  ┌─────────────────────────────────────────────────┐   │
│  │           EnterpriseMessageQueue                 │   │
│  │  入站队列 ←→ 出站队列                             │   │
│  │  去重 (dedup_window=60s)                          │   │
│  └──────────────────┬──────────────────────────────┘   │
│                     │                                   │
│                     ▼                                   │
│  ┌─────────────────────────────────────────────────┐   │
│  │          ChannelMessageHandler                    │   │
│  │  RateLimiter → Agent Loop → 回复                  │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## 核心组件

### BaseChannel

**文件**: `backend/modules/channels/base.py`

渠道抽象基类，定义所有渠道必须实现的接口。

```python
class BaseChannel(ABC):
    name: str = "base"

    async def start(self) -> None: ...      # 启动渠道
    async def stop(self) -> None: ...       # 停止渠道
    async def send(self, msg: OutboundMessage) -> None: ...  # 发送消息
    async def test_connection(self) -> dict: ...  # 测试连接
```

#### 消息数据类

```python
@dataclass
class InboundMessage:
    """入站消息"""
    channel: str        # 渠道名称
    sender_id: str      # 发送者 ID
    chat_id: str        # 聊天 ID
    content: str        # 消息内容
    media: list[str]    # 媒体文件路径
    metadata: dict      # 元数据

@dataclass
class OutboundMessage:
    """出站消息"""
    channel: str        # 目标渠道
    chat_id: str        # 目标聊天 ID
    content: str        # 消息内容
    media: list[str]    # 媒体文件路径
    metadata: dict      # 元数据
```

#### 白名单检查

```python
def is_allowed(self, sender_id: str) -> bool:
    """检查发送者是否在白名单中"""
    allow_list = getattr(self.config, "allow_from", [])
    if not allow_list:
        return True  # 未配置白名单 = 允许所有人
    return str(sender_id) in allow_list
```

### ChannelManager

**文件**: `backend/modules/channels/manager.py`

渠道管理器，负责初始化、启动和管理所有渠道。

```python
manager = ChannelManager(config=app_config, bus=message_queue)
await manager.start_all()
```

#### 方法列表

| 方法 | 说明 |
|------|------|
| `start_all()` | 启动所有已启用的渠道 |
| `stop_all()` | 停止所有渠道 |
| `send_message(msg)` | 发送出站消息 |
| `get_channel(name)` | 获取渠道实例 |
| `test_channel(name)` | 测试渠道连接 |
| `get_status()` | 获取所有渠道状态 |
| `enabled_channels` | 已启用的渠道列表 |

#### 初始化流程

`_init_channels()` 根据配置按需初始化渠道：

```python
# 仅初始化 enabled=true 的渠道
if channels_config.telegram.enabled:
    self.channels["telegram"] = TelegramChannel(config)
if channels_config.dingtalk.enabled:
    self.channels["dingtalk"] = DingTalkChannel(config)
# ... 其他渠道
```

### ChannelMessageHandler

**文件**: `backend/modules/channels/handler.py`

渠道消息处理器，负责接收入站消息、调用 Agent 处理、发送回复。

#### 初始化参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `provider` | LiteLLMProvider | — | LLM 提供商实例 |
| `workspace` | Path | — | 工作空间路径 |
| `model` | str | — | 模型名称 |
| `bus` | EnterpriseMessageQueue | — | 消息队列实例 |
| `context_builder` | ContextBuilder | — | 上下文构建器 |
| `tool_params` | dict | — | 工具注册参数 |
| `max_iterations` | int | 10 | Agent 最大迭代次数 |
| `temperature` | float | 0.7 | 温度参数（从 ModelConfig 读取） |
| `max_tokens` | int | 4096 | 最大输出 token 数（参数默认值，实际从 ModelConfig 读取） |
| `max_history_messages` | int | 50 | 最大对话历史条数（参数默认值，实际从 PersonaConfig 读取，-1=不限） |
| `rate_limiter` | RateLimiter | None | 速率限制器 |

> `temperature`、`max_tokens` 和 `max_history_messages` 与 Web 端共享同一套配置，通过设置页面统一管理。频道端的对话历史条数限制不再硬编码，而是读取 `PersonaConfig.max_history_messages`。

#### 处理流程

```
handle_message(InboundMessage)
  │
  ├─ 速率限制检查 (RateLimiter)
  ├─ 内置命令检查 (/new, /list, /switch, /clear, /stop, /help)
  ├─ 获取或创建会话 (_get_or_create_session)
  ├─ 保存用户消息到数据库
  ├─ 调用 Agent Loop 处理
  │   └─ _process_with_agent() → 收集流式响应
  ├─ 保存 AI 回复到数据库
  └─ 发送回复到渠道 (_send_reply)
```

## 消息流转

### 入站消息流

```
外部平台 → BaseChannel._handle_message()
  │  (白名单检查)
  ▼
ChannelManager._on_inbound_message()
  │
  ▼
EnterpriseMessageQueue.publish_inbound()
  │  (去重检查)
  ▼
ChannelMessageHandler.handle_message()
  │
  ▼
AgentLoop.process_message()
  │
  ▼
回复文本
```

### 出站消息流

```
AgentLoop 响应 / Cron 任务结果
  │
  ▼
ChannelMessageHandler._send_reply()
  │
  ▼
ChannelManager.send_message(OutboundMessage)
  │
  ▼
BaseChannel.send(OutboundMessage)
  │
  ▼
外部平台
```

## 支持的渠道

| 渠道 | 文件 | 协议 | 说明 |
|------|------|------|------|
| Telegram | `telegram.py` | Bot API (polling) | 支持文本、图片、文件 |
| 钉钉 | `dingtalk.py` | Stream WebSocket | 钉钉机器人 |
| 飞书 | `feishu.py` | WebSocket | 飞书机器人 |
| QQ | `qq.py` | Bot API | QQ 频道/群机器人 |
| 微信 | `wechat.py` | 公众号 API | 微信公众号 |
| Discord | — | Bot API | 预留接口 |

## 渠道配置

每个渠道在 `AppConfig.channels` 中有独立配置：

### Telegram

```json
{
  "enabled": true,
  "token": "BOT_TOKEN",
  "proxy": "http://proxy:8080",
  "allow_from": ["user_id_1", "user_id_2"]
}
```

### 钉钉

```json
{
  "enabled": true,
  "client_id": "APP_KEY",
  "client_secret": "APP_SECRET",
  "allow_from": []
}
```

### 飞书

```json
{
  "enabled": true,
  "app_id": "APP_ID",
  "app_secret": "APP_SECRET",
  "encrypt_key": "ENCRYPT_KEY",
  "verification_token": "TOKEN",
  "allow_from": []
}
```

### QQ

```json
{
  "enabled": true,
  "app_id": "APP_ID",
  "secret": "SECRET",
  "allow_from": [],
  "markdown_enabled": true,
  "group_markdown_enabled": true,
  "oss": {
    "secret_id": "",
    "secret_key": "",
    "bucket": "",
    "region": "ap-guangzhou"
  }
}
```

### 微信

```json
{
  "enabled": true,
  "app_id": "APP_ID",
  "app_secret": "APP_SECRET",
  "token": "TOKEN",
  "encoding_aes_key": "AES_KEY",
  "allow_from": []
}
```

## 消息队列

**文件**: `backend/modules/messaging/enterprise_queue.py`

`EnterpriseMessageQueue` 提供入站/出站消息的异步队列：

- **去重**：`dedup_window=60s`，防止重复消息
- **异步**：基于 `asyncio.Queue`
- **解耦**：渠道层和处理层通过队列通信

### 流量控制

**文件**: `backend/modules/messaging/rate_limiter.py`

`RateLimiter` 基于令牌桶算法限制每个发送者的消息频率：

```python
rate_limiter = RateLimiter(rate=10, per=60)
# → 每 60 秒最多 10 条消息
```

## 会话管理

每个渠道+聊天 ID 组合维护独立会话：

```
会话命名格式: {channel}:{chat_id}
示例: telegram:123456789
      dingtalk:group_xxx
      feishu:chat_xxx
```

会话存储在 SQLite 数据库中，与 Web UI 会话共享同一张表。

## 内置命令

渠道消息支持以下内置命令，用于会话管理和任务控制：

| 命令 | 说明 |
|------|------|
| `/new` | 创建新会话，当前聊天切换到新会话 |
| `/list` | 列出当前渠道+聊天的最近 10 个会话 |
| `/switch {id}` | 切换到指定会话（需要完整 session ID） |
| `/clear` | 清除当前会话的所有历史消息 |
| `/stop` | 停止当前正在执行的 Agent 任务 |
| `/help` | 显示所有可用命令的帮助信息 |

### 命令别名

部分命令支持别名：

| 主命令 | 别名 |
|--------|------|
| `/new` | `/newsession`, `/new_session` |
| `/list` | `/sessions`, `/list_sessions` |
| `/clear` | `/clear_history` |
| `/stop` | `/cancel` |
| `/help` | `/h`, `/?` |

### 命令使用示例

创建新会话：
```
/new
→ New session created: 7d504737-...
  Name: telegram:123456789:20260220_093000
```

列出会话：
```
/list
→ Sessions (recent 10):
  1. telegram:123456789
     ID: 7d504737-...
     Created: 2026-02-20 09:30
     Messages: 15
  ...
  Use /switch <session_id> to switch.
```

切换会话：
```
/switch 7d504737-4da7-4b11-a794-d463bf516a20
→ Switched to session: telegram:123456789
```

停止任务：
```
/stop
→ Task stopped.
```

### 命令处理流程

```
用户发送消息
  |
  +-- 匹配内置命令？
  |     |
  |     +-- /new → 创建新会话，绑定到当前 channel:chat_id
  |     +-- /list → 查询 sessions 表，按 channel:chat_id 前缀过滤
  |     +-- /switch → 验证 session_id 存在后切换
  |     +-- /clear → 删除当前会话所有 messages
  |     +-- /stop → 取消 _active_tasks 中的 CancellationToken
  |     +-- /help → 返回命令列表
  |
  +-- 非命令 → 进入 Agent 处理流程
```

## 安全控制

### 远程访问认证与渠道的关系

CountBot 的远程访问认证模块（`RemoteAuthMiddleware`）仅拦截 HTTP `/api/*` 和 `/ws/*` 路径。所有渠道（Telegram、钉钉、飞书、QQ、微信）均使用主动连接模式（长轮询或 WebSocket Stream），由后端主动连接到平台服务器，不经过 HTTP 中间件，因此完全不受远程认证影响。

即使启用了远程访问密码保护，渠道消息的收发也不会受到任何干扰。

详细认证机制参见 [auth.md](./auth.md)。

### 白名单

每个渠道可配置 `allow_from` 列表：

```json
{
  "allow_from": ["user_id_1", "group_id|user_id_2"]
}
```

- 空列表 = 允许所有人
- 支持 `|` 分隔的复合 ID（如 QQ 群+用户）

### 消息去重

`EnterpriseMessageQueue` 在 60 秒窗口内去重，防止平台重复推送。

### 速率限制

`RateLimiter` 防止单个用户消息洪水攻击。

## API 接口

**文件**: `backend/api/channels.py`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/channels/status` | GET | 获取所有渠道状态 |
| `/api/channels/{name}/test` | POST | 测试渠道连接 |

### 渠道状态

```
GET /api/channels/status
```

响应：
```json
{
  "telegram": {
    "enabled": true,
    "running": true,
    "display_name": "Telegram"
  },
  "dingtalk": {
    "enabled": true,
    "running": false,
    "error": "DNS resolution failed"
  }
}
```

## 添加新渠道

### 步骤

1. 创建渠道类，继承 `BaseChannel`：

```python
# backend/modules/channels/my_channel.py
from backend.modules.channels.base import BaseChannel, OutboundMessage

class MyChannel(BaseChannel):
    name = "my_channel"

    def __init__(self, config):
        super().__init__(config)

    async def start(self) -> None:
        self._running = True
        # 启动消息监听...

    async def stop(self) -> None:
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        # 发送消息到平台...

    async def test_connection(self) -> dict:
        return {"success": True, "message": "Connected"}
```

2. 在 `schema.py` 添加配置模型：

```python
class MyChannelConfig(BaseModel):
    enabled: bool = False
    api_key: str = ""
    allow_from: list[str] = Field(default_factory=list)
```

3. 在 `ChannelManager._init_channels()` 中注册：

```python
if channels_config.my_channel.enabled:
    from backend.modules.channels.my_channel import MyChannel
    self.channels["my_channel"] = MyChannel(channels_config.my_channel)
```

## 相关文件

| 文件 | 说明 |
|------|------|
| `backend/modules/channels/base.py` | 渠道基类 + 消息数据类 |
| `backend/modules/channels/manager.py` | 渠道管理器 |
| `backend/modules/channels/handler.py` | 消息处理器 |
| `backend/modules/channels/telegram.py` | Telegram 渠道 |
| `backend/modules/channels/dingtalk.py` | 钉钉渠道 |
| `backend/modules/channels/feishu.py` | 飞书渠道 |
| `backend/modules/channels/qq.py` | QQ 渠道 |
| `backend/modules/channels/wechat.py` | 微信渠道 |
| `backend/modules/messaging/enterprise_queue.py` | 消息队列 |
| `backend/modules/messaging/rate_limiter.py` | 流量控制器 |
| `backend/modules/config/schema.py` | 渠道配置模型 |
| `backend/api/channels.py` | 渠道管理 API |
