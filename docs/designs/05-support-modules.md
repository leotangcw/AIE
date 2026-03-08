# 后端支撑模块设计

**版本**: v1.0
**更新日期**: 2026-03-08

---

## 1. Channels 模块 (消息渠道)

**文件路径**: `backend/modules/channels/`

### 1.1 模块概述

Channels 模块负责与企业通信平台集成，支持消息的接收和发送。

### 1.2 模块结构

```
channels/
├── __init__.py               # 模块导出
├── manager.py                # ChannelManager - 渠道管理器
├── handler.py                # ChannelMessageHandler - 消息处理器
│
├── 渠道适配器
├── feishu.py                 # 飞书适配器
├── dingtalk.py               # 钉钉适配器
├── qq.py                     # QQ 适配器
├── telegram.py               # Telegram 适配器
├── wechat.py                 # 微信适配器
│
└── feishu_websocket_worker.py # 飞书 WebSocket 工作线程
```

### 1.3 核心组件

#### ChannelManager

**文件**: `manager.py`

```python
class ChannelManager:
    """渠道管理器"""

    def __init__(self, config, message_queue):
        """
        Args:
            config: 配置对象
            message_queue: 消息队列
        """

    async def start_all(self):
        """启动所有启用的渠道"""

    async def stop_all(self):
        """停止所有渠道"""

    @property
    def enabled_channels(self) -> list:
        """获取启用的渠道列表"""
```

#### ChannelMessageHandler

**文件**: `handler.py`

```python
class ChannelMessageHandler:
    """渠道消息处理器"""

    def __init__(
        self,
        provider,              # LLM Provider
        workspace: Path,       # 工作空间
        model: str,            # 模型
        bus: EnterpriseMessageQueue,  # 消息队列
        context_builder,       # 上下文构建器
        tool_params: dict,     # 工具参数
        subagent_manager,      # 子 Agent 管理器
        max_iterations: int,   # 最大迭代次数
        rate_limiter: RateLimiter,    # 限流器
        temperature: float,    # 温度
        max_tokens: int,       # 最大 token 数
        max_history_messages: int,  # 最大历史消息数
        memory_store: MemoryStore,  # 记忆存储
    ):
        """初始化消息处理器"""

    async def start_processing(self):
        """启动消息处理循环"""

    async def process_message(
        self,
        message: ChannelMessage,
    ):
        """处理单个消息"""

    def set_channel_manager(self, channel_manager: ChannelManager):
        """设置渠道管理器 (用于发送回复)"""
```

### 1.4 渠道适配器接口

```python
class ChannelAdapter(ABC):
    """渠道适配器基类"""

    @abstractmethod
    async def start(self):
        """启动渠道"""

    @abstractmethod
    async def stop(self):
        """停止渠道"""

    @abstractmethod
    async def send_message(
        self,
        chat_id: str,
        content: str,
    ):
        """发送消息"""

    @abstractmethod
    def parse_incoming_message(
        self,
        raw_message: dict,
    ) -> ChannelMessage:
        """解析收到的消息"""
```

### 1.5 消息格式

```python
@dataclass
class ChannelMessage:
    """统一的消息格式"""
    channel_id: str           # 渠道 ID (feishu, dingtalk, etc.)
    chat_id: str              # 聊天 ID
    sender_id: str            # 发送者 ID
    content: str              # 消息内容
    timestamp: datetime       # 时间戳
    message_type: str = "text" # 消息类型 (text, image, etc.)
    raw_data: dict = None     # 原始数据
```

### 1.6 支持的渠道

| 渠道 | 状态 | 功能 |
|------|------|------|
| 飞书 | ✅ | 文本消息、图片消息 |
| 钉钉 | ✅ | 文本消息、图片消息 |
| QQ | ✅ | 文本消息 |
| Telegram | ✅ | 文本消息 |
| 微信 | 🚧 | 文本消息 |

---

## 2. Cron 模块 (定时任务)

**文件路径**: `backend/modules/cron/`

### 2.1 模块概述

Cron 模块提供定时任务调度功能，支持 Cron 表达式和定时执行。

### 2.2 模块结构

```
cron/
├── __init__.py           # 模块导出
├── scheduler.py          # CronScheduler - 调度器
├── executor.py           # CronExecutor - 执行器
├── service.py            # CronService - 服务层
└── types.py              # 类型定义
```

### 2.3 核心组件

#### CronScheduler

**文件**: `scheduler.py`

```python
class CronScheduler:
    """Cron 调度器"""

    def __init__(
        self,
        db_session_factory,     # 数据库会话工厂
        on_execute: callable,   # 执行回调
    ):
        """初始化调度器"""

    async def start(self):
        """启动调度器"""

    async def stop(self):
        """停止调度器"""

    async def trigger_reschedule(self):
        """触发重新调度"""

    async def add_job(
        self,
        job_id: str,
        cron_expression: str,   # Cron 表达式
        message: str,           # 执行消息
        channel: str,           # 目标渠道
        chat_id: str,           # 目标聊天 ID
        enabled: bool = True,
    ) -> CronJob:
        """添加定时任务"""

    async def remove_job(self, job_id: str):
        """删除定时任务"""
```

#### CronExecutor

**文件**: `executor.py`

```python
class CronExecutor:
    """Cron 执行器"""

    def __init__(
        self,
        agent: AgentLoop,           # Agent
        bus: EnterpriseMessageQueue, # 消息队列
        session_manager: SessionManager,  # 会话管理器
        channel_manager: ChannelManager,  # 渠道管理器
        heartbeat_service: HeartbeatService, # 心跳服务
    ):
        """初始化执行器"""

    async def execute(
        self,
        job_id: str,
        message: str,
        channel: str,
        chat_id: str,
        deliver_response: bool,
    ) -> str:
        """执行定时任务"""
```

#### CronService

**文件**: `service.py`

```python
class CronService:
    """Cron 服务 (数据库操作)"""

    def __init__(self, db_session, scheduler: CronScheduler):
        """初始化服务"""

    async def get_job(self, job_id: str) -> CronJob:
        """获取任务"""

    async def create_job(self, job_data: dict) -> CronJob:
        """创建任务"""

    async def update_job(self, job_id: str, job_data: dict) -> CronJob:
        """更新任务"""

    async def delete_job(self, job_id: str):
        """删除任务"""

    async def list_jobs(self, channel: str = None) -> list:
        """列出任务"""
```

### 2.4 Cron 表达式格式

```
# 标准 Cron 表达式 (5 字段)
┌───────────── 分钟 (0 - 59)
│ ┌───────────── 小时 (0 - 23)
│ │ ┌───────────── 日 (1 - 31)
│ │ │ ┌───────────── 月 (1 - 12)
│ │ │ │ ┌───────────── 星期 (0 - 6)
│ │ │ │ │
* * * * *
```

### 2.5 任务类型

| 类型 | 描述 | 示例 |
|------|------|------|
| 心跳任务 | 定期问候用户 | `0 9 * * *` (每天早上 9 点) |
| 研究任务 | 定期研究总结 | `0 17 * * 5` (每周五下午 5 点) |
| 提醒任务 | 定时提醒 | `30 14 * * *` (每天下午 2:30) |
| 自定义任务 | 用户自定义 | 任意 Cron 表达式 |

---

## 3. Messaging 模块 (消息队列)

**文件路径**: `backend/modules/messaging/`

### 3.1 模块概述

Messaging 模块提供消息队列和限流功能，确保消息处理的可靠性和稳定性。

### 3.2 模块结构

```
messaging/
├── __init__.py               # 模块导出
├── enterprise_queue.py       # EnterpriseMessageQueue - 企业消息队列
└── rate_limiter.py           # RateLimiter - 限流器
```

### 3.3 核心组件

#### EnterpriseMessageQueue

**文件**: `enterprise_queue.py`

```python
class EnterpriseMessageQueue:
    """企业级消息队列"""

    def __init__(
        self,
        enable_dedup: bool = True,    # 启用去重
        dedup_window: int = 10,       # 去重窗口 (秒)
    ):
        """初始化消息队列"""

    async def put(self, message: ChannelMessage):
        """添加消息到队列"""

    async def get(self) -> ChannelMessage:
        """从队列获取消息"""

    async def is_duplicate(self, message: ChannelMessage) -> bool:
        """检查是否重复消息"""
```

#### RateLimiter

**文件**: `rate_limiter.py`

```python
class RateLimiter:
    """令牌桶限流器"""

    def __init__(
        self,
        rate: int = 10,         # 令牌数
        per: int = 60,          # 时间窗口 (秒)
    ):
        """初始化限流器"""

    async def acquire(self) -> bool:
        """获取令牌"""

    async def wait_for_token(self):
        """等待令牌"""
```

### 3.4 消息处理流程

```
┌─────────────────────────────────────────────────────────────┐
│                  消息处理流程                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  渠道消息                                                     │
│     │                                                        │
│     ▼                                                        │
│  ┌─────────────────┐                                        │
│  │ 消息去重检查     │ ← EnterpriseMessageQueue               │
│  └────────┬────────┘                                        │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐                                        │
│  │ 限流检查         │ ← RateLimiter                          │
│  └────────┬────────┘                                        │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐                                        │
│  │ ChannelMessage  │                                        │
│  │ Handler         │                                        │
│  └────────┬────────┘                                        │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐                                        │
│  │ AgentLoop       │                                        │
│  └────────┬────────┘                                        │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐                                        │
│  │ 发送回复         │                                        │
│  └─────────────────┘                                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. WebSocket 模块

**文件路径**: `backend/ws/`

### 4.1 模块概述

WebSocket 模块提供实时双向通信能力，支持流式响应和事件通知。

### 4.2 模块结构

```
ws/
├── __init__.py               # 模块导出
├── connection.py             # 连接处理
├── events.py                 # 事件定义
├── streaming.py              # 流式响应
├── tool_notifications.py     # 工具执行通知
└── task_notifications.py     # 任务进度通知
```

### 4.3 核心组件

#### WebSocket Connection Handler

**文件**: `connection.py`

```python
async def handle_websocket(
    websocket: WebSocket,
    agent_loop: AgentLoop,
):
    """处理 WebSocket 连接"""

    # 1. 连接建立
    await websocket.accept()

    # 2. 认证检查 (远程访问)
    if not is_local:
        if not validate_token(token):
            await websocket.close(code=4001)
            return

    # 3. 消息处理循环
    while True:
        data = await websocket.receive_json()
        await handle_message(websocket, data, agent_loop)
```

#### 事件定义

**文件**: `events.py`

```python
class WebSocketEvent(str, Enum):
    """WebSocket 事件类型"""
    MESSAGE_CHUNK = "message_chunk"
    MESSAGE_DONE = "message_done"
    TOOL_EXECUTION = "tool_execution"
    TASK_PROGRESS = "task_progress"
    ERROR = "error"
    CANCEL = "cancel"
```

#### 流式响应

**文件**: `streaming.py`

```python
async def stream_response(
    websocket: WebSocket,
    agent_loop: AgentLoop,
    message: str,
    session_id: str,
):
    """流式响应"""

    async for chunk in agent_loop.process_message(
        message=message,
        session_id=session_id,
        yield_intermediate=True,
    ):
        await websocket.send_json({
            "event": "message_chunk",
            "data": {"content": chunk}
        })

    await websocket.send_json({
        "event": "message_done"
    })
```

### 4.4 消息格式

#### 客户端 → 服务端

```json
{
    "type": "send_message",
    "data": {
        "session_id": "xxx",
        "content": "你好"
    }
}
```

#### 服务端 → 客户端

```json
{
    "event": "message_chunk",
    "data": {
        "content": "你好！有什么可以帮你的吗？"
    }
}
```

### 4.5 工具执行通知

```json
{
    "event": "tool_execution",
    "data": {
        "tool_name": "read_file",
        "arguments": {"path": "file.txt"},
        "status": "started" | "completed" | "error",
        "result": "...",
        "error": "..."
    }
}
```

---

## 5. Auth 模块 (认证)

**文件路径**: `backend/modules/auth/`

### 5.1 模块概述

Auth 模块提供认证和授权功能。

### 5.2 模块结构

```
auth/
├── __init__.py               # 模块导出
├── middleware.py             # RemoteAuthMiddleware - 认证中间件
├── router.py                 # 认证路由
├── utils.py                  # 认证工具
└── session.py                # 会话管理
```

### 5.3 核心组件

#### RemoteAuthMiddleware

**文件**: `middleware.py`

```python
class RemoteAuthMiddleware(BaseHTTPMiddleware):
    """远程访问认证中间件"""

    async def dispatch(self, request, call_next):
        # 1. 获取客户端 IP
        client_ip = get_client_ip(request)

        # 2. 判断是否为本地访问
        if client_ip in LOCAL_IPS:
            return await call_next(request)

        # 3. 远程访问需要认证
        token = request.cookies.get("AIE_token")
        if not token or not validate_session(token):
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized"}
            )

        return await call_next(request)
```

#### 会话管理

```python
sessions = {}

def create_session() -> str:
    """创建新会话"""
    token = generate_token()
    sessions[token] = {
        "created_at": datetime.now(),
        "last_activity": datetime.now(),
    }
    return token

def validate_session(token: str) -> bool:
    """验证会话"""
    return token in sessions

def destroy_session(token: str):
    """销毁会话"""
    if token in sessions:
        del sessions[token]
```

---

## 6. 配置模块

**文件路径**: `backend/modules/config/`

### 6.1 模块结构

```
config/
├── __init__.py               # 模块导出
├── loader.py                 # config_loader - 配置加载器
└── settings.py               # 配置模型
```

### 6.2 配置加载器

```python
class ConfigLoader:
    """配置加载器"""

    def __init__(self):
        self.config = None

    async def load(self):
        """加载配置"""
        # 1. 加载默认配置
        # 2. 加载 YAML 配置
        # 3. 加载环境变量
        # 4. 验证配置

    @property
    def config(self) -> Settings:
        """获取配置"""
```

### 6.3 配置模型

使用 Pydantic 定义配置结构:

```python
class Settings(BaseSettings):
    """系统配置"""

    # 模型配置
    model: ModelConfig

    # 提供商配置
    providers: dict[str, ProviderConfig]

    # 渠道配置
    channels: ChannelsConfig

    # 工作区配置
    workspace: WorkspaceConfig

    # 安全配置
    security: SecurityConfig

    # 角色配置
    persona: PersonaConfig
```

---

## 7. 待办事项 (TODO)

### Channels 模块
- [ ] 完善企业微信适配器
- [ ] 添加 WeLink 适配器
- [ ] 支持更多消息类型 (语音、视频)

### Cron 模块
- [ ] 添加任务依赖关系
- [ ] 支持任务分组
- [ ] 添加任务执行历史

### Messaging 模块
- [ ] 支持分布式消息队列 (Redis)
- [ ] 实现优先级队列
- [ ] 添加消息持久化

### WebSocket 模块
- [ ] 支持多连接负载均衡
- [ ] 添加连接心跳检测
- [ ] 实现断线重连优化

### Auth 模块
- [ ] 支持 OAuth2
- [ ] 添加 RBAC 权限控制
- [ ] 实现会话过期刷新
