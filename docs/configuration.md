# 配置系统 (Configuration)

> CountBot 的配置管理系统，基于数据库持久化，支持热更新、API 密钥加密和性格预设。

## 目录

- [设计理念](#设计理念)
- [架构概览](#架构概览)
- [配置结构](#配置结构)
- [核心组件](#核心组件)
  - [ConfigLoader](#configloader)
  - [AppConfig](#appconfig)
- [配置项详解](#配置项详解)
  - [LLM 提供商](#llm-提供商)
  - [模型配置](#模型配置)
  - [工作空间](#工作空间)
  - [安全配置](#安全配置)
  - [渠道配置](#渠道配置)
  - [人设配置](#人设配置)
- [性格预设](#性格预设)
- [API 密钥加密](#api-密钥加密)
- [API 接口](#api-接口)
- [相关文件](#相关文件)

## 设计理念

1. **数据库持久化** — 配置存储在 SQLite 的 `settings` 表，键值对形式
2. **Pydantic 验证** — 所有配置项使用 Pydantic v2 模型定义，自动验证
3. **热更新** — 通过 API 修改配置后立即生效，无需重启
4. **安全存储** — 支持 API 密钥加密存储
5. **合理默认值** — 所有配置项都有默认值，开箱即用

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    配置系统                               │
│                                                          │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │  ConfigLoader │    │  AppConfig   │                   │
│  │  (加载/保存)  │◄──►│  (Pydantic)  │                   │
│  └──────┬───────┘    └──────────────┘                   │
│         │                                                │
│         │ load() / save()                                │
│         ▼                                                │
│  ┌──────────────────────────────────────────────────┐   │
│  │              SQLite settings 表                    │   │
│  │                                                    │   │
│  │  key                          │ value              │   │
│  │  ─────────────────────────────┼──────────────────  │   │
│  │  config.model.provider        │ "zhipu"            │   │
│  │  config.model.model           │ "glm"   │   │
│  │  config.model.temperature     │ 0.7                │   │
│  │  config.security.audit_log... │ true               │   │
│  │  config.channels.telegram...  │ ...                │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## 配置结构

```python
AppConfig
├── providers: dict[str, ProviderConfig]   # LLM 提供商
├── model: ModelConfig                      # 模型参数
├── workspace: WorkspaceConfig              # 工作空间
├── security: SecurityConfig                # 安全配置
├── channels: ChannelsConfig                # 渠道配置
│   ├── telegram: TelegramConfig
│   ├── dingtalk: DingTalkConfig
│   ├── feishu: FeishuConfig
│   ├── qq: QQConfig
│   ├── wechat: WeChatConfig
│   └── discord: DiscordConfig
├── persona: PersonaConfig                  # 人设配置
├── theme: str                              # 主题 (auto/light/dark)
├── language: str                           # 语言 (auto/zh/en)
└── font_size: str                          # 字体大小
```

## 核心组件

### ConfigLoader

**文件**: `backend/modules/config/loader.py`

配置加载器，负责从数据库加载和保存配置。

```python
from backend.modules.config.loader import config_loader

# 加载配置
config = await config_loader.load()

# 获取单个值
value = await config_loader.get("model.temperature")

# 设置单个值
await config_loader.set("model.temperature", 0.5)

# 保存完整配置
await config_loader.save_config(new_config)
```

#### 存储格式

配置以扁平化键值对存储在 `settings` 表：

```
config.model.provider → "zhipu"
config.model.model → "glm-4.7-flash"
config.model.temperature → 0.7
config.security.audit_log_enabled → true
config.channels.telegram.enabled → false
config.channels.telegram.token → "BOT_TOKEN"
```

#### 加载流程

```
config_loader.load()
  │
  ├─ SELECT * FROM settings WHERE key LIKE 'config.%'
  ├─ 将扁平键值对还原为嵌套字典
  ├─ AppConfig(**config_dict) (Pydantic 验证)
  ├─ 如果启用加密，解密 API 密钥
  └─ 返回 AppConfig 实例
```

### AppConfig

**文件**: `backend/modules/config/schema.py`

应用配置根模型，使用 Pydantic v2 定义。

初始化时自动注册所有已知的 LLM 提供商：

```python
config = AppConfig()
# → 自动创建所有 provider 的默认配置
# → zhipu 默认启用并预填 API Key
```

## 配置项详解

### LLM 提供商

```python
class ProviderConfig(BaseModel):
    api_key: str = ""
    api_base: str | None = None
    enabled: bool = False
```

支持的提供商（通过 LiteLLM）：

| 提供商 | provider_id | 默认 API Base |
|--------|-------------|---------------|
| 智谱 AI | `zhipu` | `https://open.bigmodel.cn/api/paas/v4` |
| OpenAI | `openai` | `https://api.openai.com/v1` |
| Anthropic | `anthropic` | `https://api.anthropic.com` |
| DeepSeek | `deepseek` | `https://api.deepseek.com/v1` |
| 其他 | 通过 registry 注册 | — |

### 模型配置

```python
class ModelConfig(BaseModel):
    provider: str = "zhipu"           # 当前使用的提供商
    model: str = "glm"     # 模型名称
    temperature: float = 0.7          # 温度 (0.0-2.0)
    max_tokens: int = 0              # 最大输出 token (0-100000, 0=使用提供商默认值)
    max_iterations: int = 25          # Agent 最大迭代次数 (1-150)
```

所有模型参数在 Web 端和频道端均生效：

| 参数 | 范围 | 生效位置 | 说明 |
|------|------|----------|------|
| `temperature` | 0.0-2.0 | AgentLoop、SubagentManager、ChannelMessageHandler | 值越低回复越确定，越高越有创意 |
| `max_tokens` | 0-100000 | AgentLoop、SubagentManager、ChannelMessageHandler | 单次 LLM 回复的最大 token 数（0=使用提供商默认值） |
| `max_iterations` | 1-150 | AgentLoop、ChannelMessageHandler | 限制 Agent 循环次数和工具调用总数 |

### 工作空间

```python
class WorkspaceConfig(BaseModel):
    path: str = ""  # 工作空间路径
```

### 安全配置

```python
class SecurityConfig(BaseModel):
    # API 密钥加密
    api_key_encryption_enabled: bool = True

    # 危险命令检测
    dangerous_commands_blocked: bool = True
    custom_deny_patterns: list[str] = []

    # 命令白名单
    command_whitelist_enabled: bool = False
    custom_allow_patterns: list[str] = []

    # 审计日志
    audit_log_enabled: bool = True

    # 其他
    command_timeout: int = 30          # 命令超时 (1-300s)
    max_output_length: int = 10000     # 最大输出长度 (100-1000000)
    restrict_to_workspace: bool = True # 限制在工作空间内（需重启生效）
```

⚠️ **重启要求**：以下配置项修改后需要重启应用才能生效：
- `restrict_to_workspace` — 工作空间隔离
- `api_key_encryption_enabled` — API 密钥加密（影响已保存的密钥）

其他安全配置项（如 `dangerous_commands_blocked`、`audit_log_enabled` 等）修改后立即生效。

### 渠道配置

详见 [channels.md](./channels.md)。

### 人设配置

```python
class PersonaConfig(BaseModel):
    ai_name: str = "小C"              # AI 名称
    user_name: str = "主人"           # 用户称呼
    personality: str = "grumpy"       # 性格类型
    custom_personality: str = ""      # 自定义性格描述
    max_history_messages: int = 100   # 最大历史消息数 (-1=不限)
```

## 性格预设

**文件**: `backend/modules/agent/personalities.py`

CountBot 提供 12 种性格预设：

| ID | 名称 | 特点 |
|----|------|------|
| `grumpy` | 暴躁老哥 | 暴躁、嘴硬心软、网络用语、实在 |
| `roast` | 吐槽达人 | 吐槽、幽默、友好、机智 |
| `gentle` | 温柔姐姐 | 温柔、体贴、关怀、治愈 |
| `blunt` | 直球选手 | 直率、简洁、高效、干脆 |
| `toxic` | 毒舌大佬 | 毒舌、犀利、幽默、聪明 |
| `chatty` | 话痨本痨 | 话痨、热情、知识丰富、发散 |
| `philosopher` | 哲学家 | 深邃、思辨、启发、通透 |
| `cute` | 软萌助手 | 可爱、活泼、认真、暖心 |
| `humorous` | 段子手 | 幽默、机智、轻松、有趣 |
| `hyper` | 元气满满 | 兴奋、热情、正能量、活力 |
| `chuuni` | 中二之魂 | 中二、戏剧化、华丽、靠谱 |
| `zen` | 佛系大师 | 佛系、淡然、智慧、平静 |
| `custom` | 自定义 | 使用 `custom_personality` 字段 |

每个预设包含：
- `description` — 性格描述
- `traits` — 性格特点标签
- `speaking_style` — 说话风格指导

### 使用方式

```python
from backend.modules.agent.personalities import get_personality_prompt

# 获取预设性格提示词
prompt = get_personality_prompt("grumpy")

# 使用自定义性格
prompt = get_personality_prompt("custom", "你是一个海盗风格的AI助手")
```

性格提示词注入到系统提示词的"性格设定"部分，影响 AI 的回复风格。

## API 密钥加密

**文件**: `backend/modules/config/security.py`

启用 `api_key_encryption_enabled` 后，API 密钥在存储到数据库前加密：

```
保存: api_key → encrypt() → 密文存入数据库
加载: 密文 → decrypt() → 明文 api_key
```

加密/解密通过 `security_manager` 单例处理。

## API 接口

**文件**: `backend/api/settings.py`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/settings` | GET | 获取完整配置 |
| `/api/settings` | PUT | 更新配置 |
| `/api/settings/providers` | GET | 获取提供商列表 |
| `/api/settings/personalities` | GET | 获取性格预设列表 |

### 获取配置

```
GET /api/settings
```

响应：
```json
{
  "providers": {
    "zhipu": { "api_key": "***", "api_base": "...", "enabled": true },
    "openai": { "api_key": "", "api_base": "...", "enabled": false }
  },
  "model": {
    "provider": "zhipu",
    "model": "glm-5",
    "temperature": 0.7,
    "max_tokens": 0,
    "max_iterations": 25
  },
  "security": { ... },
  "channels": { ... },
  "persona": {
    "ai_name": "小C",
    "user_name": "主人",
    "personality": "grumpy"
  },
  "theme": "auto",
  "language": "auto"
}
```

### 更新配置

```
PUT /api/settings
{
  "model": {
    "temperature": 0.5
  },
  "persona": {
    "personality": "humorous"
  }
}
```

## 相关文件

| 文件 | 说明 |
|------|------|
| `backend/modules/config/loader.py` | ConfigLoader 配置加载器 |
| `backend/modules/config/schema.py` | Pydantic 配置模型 |
| `backend/modules/config/security.py` | API 密钥加密 |
| `backend/modules/agent/personalities.py` | 性格预设 |
| `backend/modules/auth/middleware.py` | 远程访问认证中间件 |
| `backend/modules/auth/router.py` | 认证 API 端点 |
| `backend/modules/auth/utils.py` | 密码验证、session 管理 |
| `backend/models/setting.py` | Setting 数据库模型 |
| `backend/api/settings.py` | 配置 API |
| `backend/database.py` | 数据库初始化 |

> 远程访问认证的详细说明请参阅 [auth.md](./auth.md)。
