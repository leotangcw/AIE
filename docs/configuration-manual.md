# CountBot 配置手册

> 本手册覆盖 CountBot 所有配置项的完整说明，包括数据流向、生效范围和验证方法。适用于管理员和开发者。

## 目录

- [配置系统概述](#配置系统概述)
- [1. LLM 提供商配置](#1-llm-提供商配置)
- [2. 模型参数配置](#2-模型参数配置)
- [3. 人设与对话配置](#3-人设与对话配置)
- [4. 工作空间配置](#4-工作空间配置)
- [5. 安全配置](#5-安全配置)
- [6. 渠道配置](#6-渠道配置)
- [7. 技能系统配置](#7-技能系统配置)
- [8. 外观与语言配置](#8-外观与语言配置)
- [9. 远程访问认证配置](#9-远程访问认证配置)
- [10. 配置 API 参考](#10-配置-api-参考)
- [11. 配置数据流全景图](#11-配置数据流全景图)
- [附录：配置验证清单](#附录配置验证清单)

---

## 配置系统概述

### 存储方式

所有配置存储在 SQLite 数据库的 `settings` 表中，以扁平化键值对形式持久化：

```
config.model.provider    → "zhipu"
config.model.temperature → 0.7
config.channels.telegram.enabled → false
```

### 配置加载流程

```
应用启动 → config_loader.load() → 从 settings 表读取 → Pydantic 验证 → AppConfig 实例
```

### 配置更新流程

```
前端设置页面 → PUT /api/settings → 更新 AppConfig → config_loader.save_config() → 写入 settings 表
```

配置修改后立即生效，无需重启应用。

### 配置结构总览

```python
AppConfig
├── providers: dict[str, ProviderConfig]   # LLM 提供商（9 个）
├── model: ModelConfig                      # 模型参数
├── persona: PersonaConfig                  # 人设与对话
├── workspace: WorkspaceConfig              # 工作空间
├── security: SecurityConfig                # 安全
├── channels: ChannelsConfig                # 渠道（6 个）
├── theme: str                              # 主题
├── language: str                           # 语言
└── font_size: str                          # 字体大小
```

---

## 1. LLM 提供商配置

### 配置模型

```python
class ProviderConfig(BaseModel):
    api_key: str = ""           # API 密钥
    api_base: str | None = None # API 地址（可选，有默认值）
    enabled: bool = False       # 是否启用
```

### 支持的提供商

| 提供商 | ID | 默认 API Base | 默认模型 | LiteLLM 前缀 |
|--------|-----|---------------|----------|---------------|
| 智谱 AI | `zhipu` | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` | `openai` |
| OpenAI | `openai` | `https://api.openai.com/v1` | `gpt-4o` | — |
| Anthropic | `anthropic` | `https://api.anthropic.com` | `claude-sonnet-4-20250514` | — |
| DeepSeek | `deepseek` | `https://api.deepseek.com/v1` | `deepseek-chat` | `deepseek` |
| Google Gemini | `gemini` | `https://generativelanguage.googleapis.com/v1beta` | `gemini-2.0-flash` | `gemini` |
| Moonshot AI | `moonshot` | `https://api.moonshot.cn/v1` | `kimi-k2.5` | `moonshot` |
| OpenRouter | `openrouter` | `https://openrouter.ai/api/v1` | `anthropic/claude-3.5-sonnet` | `openrouter` |
| Groq | `groq` | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` | `groq` |
| Mistral AI | `mistral` | `https://api.mistral.ai/v1` | `mistral-large-latest` | `mistral` |
| Cohere | `cohere` | `https://api.cohere.com/v2` | `command-r-plus` | `cohere_chat` |
| Together AI | `together_ai` | `https://api.together.xyz/v1` | `meta-llama/Llama-3.3-70B-Instruct-Turbo` | `together_ai` |
| 阿里云百炼 | `qwen` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen3.5-plus` | `openai` |
| 腾讯云 | `hunyuan` | `https://hunyuan.tencentcloudapi.com` | `hunyuan-lite` | `hunyuan` |
| 百度千帆 | `ernie` | `https://qianfan.baidubce.com/v2` | `ernie-4.0-8k` | `openai` |
| 字节火山引擎 | `doubao` | `https://ark.cn-beijing.volces.com/api/v3` | `doubao-pro-32k` | `openai` |
| 01.AI | `yi` | `https://api.lingyiwanwu.com/v1` | `yi-large` | `openai` |
| Baichuan AI | `baichuan` | `https://api.baichuan-ai.com/v1` | `Baichuan4` | `openai` |
| MiniMax | `minimax` | `https://api.minimaxi.com/anthropic` | `MiniMax-M2.5` | `anthropic` |
| vLLM | `vllm` | `http://localhost:8000/v1` | 自定义 | `hosted_vllm` |
| Ollama | `ollama` | `http://localhost:11434` | `llama3.2` | `ollama` |
| LM Studio | `lm_studio` | `http://localhost:1234/v1` | 自定义 | `openai` |
| Custom (OpenAI) | `custom_openai` | 自定义 | 自定义 | `openai` |
| Custom (Gemini) | `custom_gemini` | 自定义 | 自定义 | `gemini` |
| Custom (Anthropic) | `custom_anthropic` | 自定义 | 自定义 | `anthropic` |

### 配置方式

通过 Web UI → 设置 → 提供商配置页面：

1. 选择提供商
2. 填入 API Key
3. （可选）修改 API Base 地址
4. 点击"测试连接"验证
5. 保存

### 数据流

```
前端 ProviderConfig.vue
  → PUT /api/settings { providers: { "zhipu": { api_key: "xxx", enabled: true } } }
  → config_loader.save_config()
  → 下次创建 LiteLLMProvider 时使用新配置
```

### API 密钥加密

启用 `security.api_key_encryption_enabled` 后，API 密钥在存入数据库前自动加密，读取时自动解密。

### 连接测试

```
POST /api/settings/test-connection
{
  "provider": "zhipu",
  "api_key": "your-key",
  "api_base": "https://open.bigmodel.cn/api/paas/v4",
  "model": "glm-5"
}
```

测试会创建临时 `LiteLLMProvider` 实例，发送 `"Hello"` 消息验证连接。

---

## 2. 模型参数配置

### 配置模型

```python
class ModelConfig(BaseModel):
    provider: str = "zhipu"           # 当前使用的提供商 ID
    model: str = "glm-5"     # 模型名称
    temperature: float = 0.7          # 温度参数 (0.0-2.0)
    max_tokens: int = 0               # 最大输出 token 数 (0-100000, 0=使用提供商默认值)
    max_iterations: int = 25          # Agent 最大迭代次数 (1-150)
```

### 参数详解

#### temperature（温度）

| 属性 | 值 |
|------|-----|
| 范围 | 0.0 ~ 2.0 |
| 默认值 | 0.7 |
| 生效位置 | AgentLoop、SubagentManager、ChannelMessageHandler |
| 影响 | 值越低回复越确定和一致，值越高回复越有创意和多样性 |

推荐值：
- 代码生成/精确任务：0.0 ~ 0.3
- 通用对话：0.5 ~ 0.8
- 创意写作：0.8 ~ 1.2

#### max_tokens（最大输出 token）

| 属性 | 值 |
|------|-----|
| 范围 | 1 ~ 100000 |
| 默认值 | 4096 |
| 生效位置 | AgentLoop、SubagentManager、ChannelMessageHandler |
| 影响 | 限制单次 LLM 回复的最大 token 数 |

注意：实际可用的 max_tokens 受模型本身限制。例如 `exapmle` 最大支持 4096 输出 token，设置更高值不会报错但不会生效。

#### max_iterations（最大迭代次数）

| 属性 | 值 |
|------|-----|
| 范围 | 1 ~ 150 |
| 默认值 | 25 |
| 生效位置 | AgentLoop（Web 端和频道端） |
| 影响 | 限制 Agent 循环次数和工具调用总数 |

当 Agent 达到迭代上限时，会在回复末尾追加提示：`[达到最大工具调用次数 25]`

### 数据流全链路

```
前端 ModelConfig.vue（滑块/输入框）
  → PUT /api/settings { model: { temperature: 0.5, max_tokens: 8192 } }
  → config_loader.save_config() → 写入 settings 表
  → 下次消息处理时：
      ├─ Web 端: websocket_endpoint() → AgentLoop(temperature=0.5, max_tokens=8192)
      │           → provider.chat_stream(temperature=0.5, max_tokens=8192)
      ├─ 频道端: ChannelMessageHandler(temperature=0.5, max_tokens=8192)
      │           → AgentLoop → provider.chat_stream(...)
      └─ 子代理: SubagentManager(temperature=0.5, max_tokens=8192)
                  → 独立 AgentLoop → provider.chat_stream(...)
```

### 验证方法

1. 修改 temperature 为 0.0，发送相同问题两次，回复应高度一致
2. 修改 max_tokens 为 50，回复应明显被截断
3. 修改 max_iterations 为 2，复杂任务应提前终止并显示提示

---

## 3. 人设与对话配置

### 配置模型

```python
class PersonaConfig(BaseModel):
    ai_name: str = "小C"              # AI 名称
    user_name: str = "主人"           # 用户称呼
    personality: str = "grumpy"       # 性格类型
    custom_personality: str = ""      # 自定义性格描述
    max_history_messages: int = 100   # 最大对话历史条数 (-1=不限, 范围: -1~500)
```

### 参数详解

#### ai_name（AI 名称）

注入到系统提示词的身份部分：`"你是 {ai_name}，一个智能助手"`。影响 AI 的自我认知和自称。

#### user_name（用户称呼）

注入到系统提示词：`"用户希望你称呼他为 {user_name}"`。影响 AI 对用户的称呼方式。

#### personality（性格类型）

CountBot 提供 12 种预设性格 + 1 种自定义：

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
| `custom` | 自定义 | 使用 `custom_personality` 字段内容 |

性格通过 `get_personality_prompt()` 转换为提示词，注入系统提示词的"性格设定"部分。

#### max_history_messages（最大对话历史条数）

| 属性 | 值 |
|------|-----|
| 范围 | -1 ~ 500（-1 表示不限制） |
| 默认值 | 100 |
| 生效位置 | Web 端（chat.py）和频道端（handler.py） |

控制每次 LLM 调用时携带的历史消息条数。值越大，AI 记忆的上下文越多，但 token 消耗也越大。

当消息数超过此限制时，溢出的旧消息会通过「上下文滚动压缩」自动总结写入 MEMORY.md（source 为 `auto-overflow`），确保有价值的信息不会丢失。详见 [memory.md](./memory.md#上下文滚动压缩-overflow-summarization)。

### 数据流

```
前端 PersonaConfig.vue
  → PUT /api/settings { persona: { personality: "grumpy", max_history_messages: 100 } }
  → config_loader.save_config()
  → 生效路径：
      ├─ personality → ContextBuilder.build_system_prompt()
      │                → get_personality_prompt("grumpy")
      │                → 注入系统提示词
      ├─ ai_name/user_name → ContextBuilder._get_identity()
      │                      → 注入系统提示词身份部分
      └─ max_history_messages
          ├─ Web 端: chat.py → get_agent_loop() 读取 → 查询历史时 .limit(N)
          └─ 频道端: ChannelMessageHandler.max_history_messages
                     → _get_session_history() 中 .limit(N)
```

### 验证方法

1. 修改 personality 为 `humorous`，AI 回复风格应变为段子手
2. 修改 ai_name 为 `小助手`，AI 应以"小助手"自称
3. 修改 max_history_messages 为 5，长对话中 AI 应忘记较早的消息
4. 设置 max_history_messages 为 -1，AI 应记住所有历史消息

---

## 4. 工作空间配置

### 配置模型

```python
class WorkspaceConfig(BaseModel):
    path: str = ""  # 工作空间路径（空字符串表示使用当前目录）
```

### 影响范围

工作空间路径影响以下功能：

| 功能 | 影响 |
|------|------|
| 文件系统工具 | `read_file`、`write_file`、`edit_file`、`list_dir` 的根目录 |
| Shell 工具 | `exec` 命令的默认工作目录 |
| 文件搜索 | `file_search` 的默认搜索路径 |
| 记忆存储 | `{workspace}/memory/MEMORY.md` |
| 技能目录 | `{workspace}/skills/` |
| 截图输出 | `{workspace}/screenshots/` |
| 安全隔离 | `restrict_to_workspace=true` 时限制文件访问范围 |

### 数据流

```
前端 WorkspaceConfig.vue
  → PUT /api/settings { workspace: { path: "/Users/xxx/projects" } }
  → config_loader.save_config()
  → 重启后生效（工作空间路径在启动时初始化）
```

注意：修改工作空间路径后需要重启应用才能完全生效，因为 `MemoryStore`、`SkillsLoader` 等组件在启动时初始化。

---

## 5. 安全配置

### 配置模型

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
    command_timeout: int = 30          # 命令超时 (1-300 秒)
    max_output_length: int = 10000     # 最大输出长度 (100-1000000 字符)
    restrict_to_workspace: bool = True # 限制在工作空间内
```

### 参数详解

#### 危险命令检测（dangerous_commands_blocked）

启用后，Shell 工具会检测以下内置危险模式：

| 模式 | 说明 |
|------|------|
| `rm -rf` | 递归强制删除 |
| `del /f` | Windows 强制删除 |
| `rmdir /s` | Windows 递归删除目录 |
| `format`/`mkfs`/`diskpart` | 磁盘格式化 |
| `dd if=` | 磁盘数据复制 |
| `> /dev/sd` | 直接写入磁盘设备 |
| `shutdown`/`reboot` | 系统关机/重启 |
| Fork 炸弹 | `:(){ :|:& };:` |

可通过 `custom_deny_patterns` 添加自定义拒绝模式（正则表达式）。

#### 命令白名单（command_whitelist_enabled）

启用后，只有匹配 `custom_allow_patterns` 的命令才能执行。适用于严格安全环境。

#### 审计日志（audit_log_enabled）

启用后，所有工具调用记录到 `data/audit_logs/` 目录，按日期分文件，包含：
- 工具名称、参数、结果
- 会话 ID、时间戳
- 执行耗时

#### restrict_to_workspace

启用后，文件系统工具和 Shell 工具的工作目录限制在工作空间内，防止访问系统其他文件。

⚠️ **重要提示**：启用或禁用工作空间隔离（`restrict_to_workspace`）需要重启应用才能生效，因为该配置在工具初始化时读取。

### 数据流

```
前端 SecurityConfig.vue
  → PUT /api/settings { security: { command_timeout: 60, restrict_to_workspace: true } }
  → config_loader.save_config()
  → 重启后生效（工具初始化时读取）
  → 生效路径：
      ├─ command_timeout → ShellTool.execute() 中的超时设置（立即生效）
      ├─ restrict_to_workspace → WorkspaceValidator.validate_path()（需重启）
      ├─ dangerous_commands_blocked → ShellTool 的危险命令检测（立即生效）
      ├─ audit_log_enabled → FileAuditLogger 开关（立即生效）
      └─ max_output_length → ShellTool 输出截断（立即生效）
```

---

## 6. 渠道配置

CountBot 支持 6 种即时通讯渠道，每个渠道独立配置。

### Telegram

```python
class TelegramConfig(BaseModel):
    enabled: bool = False
    token: str = ""                              # Bot Token（从 @BotFather 获取）
    proxy: str | None = None                     # HTTP 代理地址（可选）
    allow_from: list[str] = []                   # 白名单用户 ID（空=允许所有人）
```

获取方式：
1. 在 Telegram 中搜索 `@BotFather`
2. 发送 `/newbot` 创建机器人
3. 获取 Bot Token

### 钉钉

```python
class DingTalkConfig(BaseModel):
    enabled: bool = False
    client_id: str = ""                          # 应用 AppKey
    client_secret: str = ""                      # 应用 AppSecret
    allow_from: list[str] = []
```

获取方式：
1. 登录 [钉钉开放平台](https://open.dingtalk.com)
2. 创建内部应用
3. 获取 AppKey 和 AppSecret
4. 启用 Stream 模式

### 飞书

```python
class FeishuConfig(BaseModel):
    enabled: bool = False
    app_id: str = ""                             # 应用 App ID
    app_secret: str = ""                         # 应用 App Secret
    encrypt_key: str = ""                        # 事件加密密钥
    verification_token: str = ""                 # 事件验证 Token
    allow_from: list[str] = []
```

获取方式：
1. 登录 [飞书开放平台](https://open.feishu.cn)
2. 创建自建应用
3. 获取 App ID、App Secret
4. 配置事件订阅，获取 Encrypt Key 和 Verification Token

### QQ

```python
class QQConfig(BaseModel):
    enabled: bool = False
    app_id: str = ""                             # 机器人 App ID
    secret: str = ""                             # 机器人 Secret
    allow_from: list[str] = []
    markdown_enabled: bool = True                # 是否启用 Markdown 消息
    group_markdown_enabled: bool = True          # 群聊是否启用 Markdown
    oss: TencentOSSConfig = TencentOSSConfig()   # 腾讯云 OSS（图片上传用）
```

QQ 渠道额外支持腾讯云 OSS 配置，用于上传图片获取公网 URL：

```python
class TencentOSSConfig(BaseModel):
    secret_id: str = ""
    secret_key: str = ""
    bucket: str = ""
    region: str = "ap-guangzhou"
```

### 微信

```python
class WeChatConfig(BaseModel):
    enabled: bool = False
    app_id: str = ""                             # 公众号 App ID
    app_secret: str = ""                         # 公众号 App Secret
    token: str = ""                              # 消息验证 Token
    encoding_aes_key: str = ""                   # 消息加密密钥
    allow_from: list[str] = []
```

### Discord

```python
class DiscordConfig(BaseModel):
    enabled: bool = False
    token: str = ""                              # Bot Token
    allow_from: list[str] = []
```

### 白名单机制

所有渠道共享白名单机制：

- `allow_from` 为空列表 → 允许所有人发送消息
- `allow_from` 包含用户 ID → 仅允许列表中的用户
- 支持复合 ID 格式（如 QQ 群+用户：`"group_id|user_id"`）

### 渠道状态查询

```
GET /api/channels/status
→ { "telegram": { "enabled": true, "running": true }, ... }
```

### 渠道连接测试

```
POST /api/channels/{name}/test
→ { "success": true, "message": "Connected successfully" }
```

---

## 7. 技能系统配置

### 技能目录结构

```
skills/
├── baidu-search/
│   ├── SKILL.md              # 技能定义文件（必需）
│   └── scripts/
│       └── search.py
├── cron-manager/
│   ├── SKILL.md
│   └── scripts/
├── email/
│   ├── SKILL.md
│   └── scripts/
├── image-analysis/
│   ├── SKILL.md
│   └── scripts/
├── image-gen/
│   ├── SKILL.md
│   └── scripts/
├── map/
│   ├── SKILL.md
│   └── scripts/
├── news/
│   ├── SKILL.md
│   └── scripts/
├── weather/
│   ├── SKILL.md
│   └── scripts/
├── web-design/
│   ├── SKILL.md
│   ├── scripts/
│   └── assets/
└── agent-browser/
    ├── SKILL.md
    ├── references/
    └── templates/
```

### SKILL.md Frontmatter 字段

```yaml
---
name: baidu-search                    # 技能名称（必填）
description: 百度 AI 搜索。支持网页搜索、百度百科、秒懂百科、AI 智能生成四种模式。  # 技能描述（必填）
version: 1.0.0                   # 版本号（可选，默认 1.0.0）
always: false                    # 是否自动加载到系统提示词（可选，默认 false）
requirements:                    # Python 依赖列表（可选）
  - requests
---
```

#### always 字段说明

| 值 | 行为 |
|----|------|
| `true` | 技能完整内容自动注入系统提示词，每次 LLM 调用都携带 |
| `false` | 仅在系统提示词中列出摘要，Agent 需要时通过 `read_file` 按需加载 |

建议：仅高频使用的技能设为 `always=true`，避免系统提示词过长消耗 token。

### 启用/禁用配置

技能启用状态存储在工作空间根目录的 `.skills_config.json`：

```json
{
  "disabled": ["skill-x", "skill-y"]
}
```

不在 `disabled` 列表中的技能默认启用。

### 内置技能

| 技能 | 说明 | always | 依赖 |
|------|------|--------|------|
| `baidu-search` | 百度 AI 搜索，支持网页搜索、百度百科、秒懂百科、AI 智能生成 | false | requests |
| `cron-manager` | 定时任务管理，创建、查看、修改、删除定时任务 | false | — |
| `email` | 通过 QQ 或 163 邮箱发送和接收邮件 | false | — |
| `image-analysis` | 图片分析与识别，基于智谱/千问视觉模型 | false | — |
| `image-gen` | AI 图片生成，基于 ModelScope API | false | — |
| `map` | 高德地图路线规划与 POI 搜索 | false | — |
| `news` | 新闻与资讯查询，中文新闻 + 全球 AI 资讯 | false | — |
| `weather` | 天气查询与预报，基于 wttr.in | false | — |
| `web-design` | 网页设计与 Cloudflare Pages 部署 | false | — |
| `agent-browser` | 浏览器自动化 CLI，网页操作、截图、数据提取 | false | agent-browser (npm) |

### 技能管理 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/skills` | GET | 列出所有技能 |
| `/api/skills` | POST | 创建新技能 |
| `/api/skills/{name}` | GET | 获取技能详情 |
| `/api/skills/{name}` | PUT | 更新技能 |
| `/api/skills/{name}` | DELETE | 删除技能 |
| `/api/skills/{name}/toggle` | POST | 启用/禁用技能 |

### 自定义技能开发

1. 在 `skills/` 目录创建文件夹
2. 编写 `SKILL.md`（含 frontmatter 和使用说明）
3. （可选）在 `scripts/` 子目录添加辅助脚本
4. 通过 Web UI 或 API 启用

技能内容是纯文本 Markdown，注入系统提示词后由 LLM 理解和执行，不依赖特定的 Function Calling 格式。

---

## 8. 外观与语言配置

### 配置项

| 参数 | 类型 | 默认值 | 可选值 | 说明 |
|------|------|--------|--------|------|
| `theme` | string | `"auto"` | `auto`/`light`/`dark` | 界面主题 |
| `language` | string | `"auto"` | `auto`/`zh`/`en` | 界面语言 |
| `font_size` | string | `"medium"` | `small`/`medium`/`large` | 字体大小 |

这些配置仅影响前端 UI 展示，不影响后端逻辑。

### 数据流

```
前端 SystemSettings.vue
  → PUT /api/settings { theme: "dark", language: "zh" }
  → 前端读取后应用到 UI
```

---

## 9. 远程访问认证配置

CountBot 内置远程访问认证模块，当通过非本地 IP 访问时自动触发认证保护。

### 工作原理

- 本地访问（`127.0.0.1` / `::1`）：完全不受影响，无需任何认证
- 远程访问：自动触发认证，需要登录后才能使用 API 和 WebSocket

### 认证凭据存储

凭据存储在 SQLite `settings` 表中：

| 键 | 说明 |
|----|------|
| `auth.username` | 管理员用户名（JSON 编码） |
| `auth.password_hash` | SHA-256 + salt 哈希后的密码（JSON 编码） |

### 密码要求

- 至少 8 位字符
- 必须同时包含：大写字母、小写字母、数字

### Session Token

- 使用 `secrets.token_urlsafe(32)` 生成
- 内存存储，24 小时过期
- 应用重启后所有 session 失效
- 支持 Cookie（`CountBot_token`）和 Authorization Header（`Bearer xxx`）两种传递方式

### 中间件拦截规则

| 路径 | 行为 |
|------|------|
| `/api/auth/*` | 白名单，不拦截 |
| `/api/health` | 白名单，不拦截 |
| `/login`, `/assets/*` | 白名单，不拦截 |
| `/api/*`, `/ws/*` | 远程访问时需要认证 |
| 其他路径 | 不拦截（静态资源等） |

### 安全特性

- IP 判断基于 TCP socket 层 `client.host`，不可通过 HTTP 头伪造
- 防代理绕过：请求包含 `X-Forwarded-For` 头时，即使 `client.host` 是本地 IP 也不放行
- 密码使用 SHA-256 + 随机 salt 哈希存储
- 密码验证使用 `secrets.compare_digest` 防止时序攻击

### API 接口

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/auth/status` | GET | 查询认证状态 |
| `/api/auth/setup` | POST | 首次设置密码 |
| `/api/auth/login` | POST | 登录 |
| `/api/auth/logout` | POST | 登出 |
| `/api/auth/change-password` | POST | 修改密码 |

### 禁用远程认证

通过本地访问清除数据库中的 `auth.password_hash` 记录即可。未设置密码时不会阻止远程访问前端页面加载，但 API 调用会返回 `AUTH_SETUP_REQUIRED`。

详细说明参见 [auth.md](./auth.md)。

---

## 10. 配置 API 参考

### 获取完整配置

```
GET /api/settings
```

响应示例：

```json
{
  "providers": {
    "zhipu": { "enabled": true, "api_key": "xxx", "api_base": "https://open.bigmodel.cn/api/paas/v4" },
    "openai": { "enabled": false, "api_key": "", "api_base": null }
  },
  "model": {
    "provider": "zhipu",
    "model": "glm-5",
    "temperature": 0.7,
    "max_tokens": 0,
    "max_iterations": 25
  },
  "workspace": { "path": "" },
  "security": {
    "api_key_encryption_enabled": true,
    "dangerous_commands_blocked": true,
    "custom_deny_patterns": [],
    "command_whitelist_enabled": false,
    "custom_allow_patterns": [],
    "audit_log_enabled": true,
    "command_timeout": 30,
    "max_output_length": 10000,
    "restrict_to_workspace": true
  },
  "persona": {
    "ai_name": "小C",
    "user_name": "主人",
    "personality": "grumpy",
    "custom_personality": "",
    "max_history_messages": 100
  }
}
```

### 更新配置（部分更新）

```
PUT /api/settings
```

只需传入要修改的字段：

```json
{
  "model": { "temperature": 0.5 },
  "persona": { "personality": "humorous" }
}
```

### 获取提供商列表

```
GET /api/settings/providers
```

返回所有可用提供商的元数据（ID、名称、默认 API Base、默认模型）。

### 获取性格预设列表

```
GET /api/settings/personalities
```

返回所有性格预设的详情（ID、名称、描述、特点标签）。

### 测试提供商连接

```
POST /api/settings/test-connection
{
  "provider": "openai",
  "api_key": "sk-xxx",
  "api_base": null,
  "model": "gpt-5.3"
}
```

### 获取内置危险命令模式

```
GET /api/settings/security/dangerous-patterns
```

返回所有内置的危险命令正则模式及其描述。

### 重新加载 OSS 配置

```
POST /api/settings/reload-oss
```

热重载腾讯云 OSS 配置，无需重启应用。

---

## 11. 配置数据流全景图

以下展示每个配置项从前端 UI 到最终生效位置的完整数据流。

### 模型参数流

```
┌─────────────────────────────────────────────────────────────────┐
│  前端 ModelConfig.vue                                            │
│  temperature 滑块 / max_tokens 输入框 / max_iterations 输入框    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ PUT /api/settings
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  backend/api/settings.py → update_settings()                     │
│  → config.model.temperature = 0.5                                │
│  → config_loader.save_config() → SQLite settings 表              │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 下次消息处理时读取
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  三条路径同时生效：                                                │
│                                                                  │
│  1. Web 端 (WebSocket)                                           │
│     backend/app.py websocket_endpoint()                          │
│     → config = config_loader.config                              │
│     → AgentLoop(temperature=config.model.temperature,            │
│                  max_tokens=config.model.max_tokens)              │
│     → provider.chat_stream(temperature=..., max_tokens=...)      │
│                                                                  │
│  2. 频道端 (Telegram/钉钉/飞书/QQ/微信)                           │
│     backend/app.py lifespan()                                    │
│     → ChannelMessageHandler(temperature=..., max_tokens=...)     │
│     → AgentLoop(temperature=..., max_tokens=...)                 │
│     → provider.chat_stream(temperature=..., max_tokens=...)      │
│                                                                  │
│  3. 子代理                                                       │
│     backend/app.py _create_shared_components()                   │
│     → SubagentManager(temperature=..., max_tokens=...)           │
│     → 独立 AgentLoop → provider.chat_stream(...)                 │
└─────────────────────────────────────────────────────────────────┘
```

### 对话历史条数流

```
┌─────────────────────────────────────────────────────────────────┐
│  前端 PersonaConfig.vue                                          │
│  max_history_messages 输入框                                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │ PUT /api/settings
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  config.persona.max_history_messages = 100                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
┌──────────────────────┐  ┌──────────────────────────────────────┐
│  Web 端               │  │  频道端                               │
│  chat.py              │  │  handler.py                          │
│  get_agent_loop()     │  │  ChannelMessageHandler               │
│  读取配置 → 查询历史  │  │  .max_history_messages               │
│  .limit(100)          │  │  _get_session_history()              │
│                       │  │  .limit(100)                         │
│  溢出时自动总结:      │  │                                      │
│  summarize_overflow() │  │  -1 时不加 limit                     │
│  → 写入 MEMORY.md     │  │                                      │
│                       │  │                                      │
│  -1 时不加 limit      │  │                                      │
└──────────────────────┘  └──────────────────────────────────────┘
```

### 安全配置流

```
┌─────────────────────────────────────────────────────────────────┐
│  前端 SecurityConfig.vue                                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ PUT /api/settings
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  config.security 更新                                            │
└──────────────────────────┬──────────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
┌────────────────┐ ┌──────────────┐ ┌────────────────────┐
│ ShellTool      │ │ FileSystem   │ │ FileAuditLogger    │
│ .exec()        │ │ Tools        │ │                    │
│                │ │              │ │ audit_log_enabled   │
│ command_timeout│ │ restrict_to_ │ │ → 记录/不记录       │
│ dangerous_cmds │ │ workspace    │ │   工具调用日志       │
│ whitelist      │ │ → 路径验证   │ │                    │
│ deny_patterns  │ │              │ │                    │
└────────────────┘ └──────────────┘ └────────────────────┘
```

---

## 附录：配置验证清单

### 远程访问认证验证

| 验证项 | 操作 | 预期结果 |
|--------|------|----------|
| 本地访问不受影响 | 通过 `127.0.0.1:8000` 访问 | 直接进入主页，无需登录 |
| 远程首次访问 | 通过局域网 IP 访问 | 跳转登录页，显示「设置密码」模式 |
| 密码强度校验 | 设置密码 `abc` | 提示密码不符合要求 |
| 登录成功 | 输入正确账号密码 | 跳转主页，API 请求正常 |
| Token 失效 | 清除 localStorage 中的 `CountBot_token` | 下次 API 请求返回 401，跳转登录页 |
| WebSocket 认证 | 远程访问时打开聊天 | WebSocket 连接携带 token，正常通信 |
| 渠道不受影响 | 启用 Telegram 等渠道 | 渠道消息收发正常 |

以下清单用于验证所有配置项是否正确生效。

### 模型参数验证

| 验证项 | 操作 | 预期结果 |
|--------|------|----------|
| temperature 生效 | 设为 0.0，发送相同问题两次 | 回复高度一致 |
| max_tokens 生效 | 设为 50 | 回复明显被截断 |
| max_iterations 生效 | 设为 2，要求执行多步任务 | 提前终止并显示 `[达到最大迭代次数 2]` |
| Web 端和频道端一致 | 同时通过 Web 和 Telegram 发送相同问题 | 回复风格和长度一致 |

### 人设配置验证

| 验证项 | 操作 | 预期结果 |
|--------|------|----------|
| 性格切换 | 切换为 `humorous` | AI 回复风格变为段子手 |
| AI 名称 | 修改为 `小助手`，问"你叫什么" | AI 回答"小助手" |
| 用户称呼 | 修改为 `老板` | AI 称呼用户为"老板" |
| 历史条数限制 | 设为 3，发送 10 条消息后问第 1 条内容 | AI 不记得第 1 条消息 |
| 历史不限 | 设为 -1 | AI 记住所有历史消息 |

### 安全配置验证

| 验证项 | 操作 | 预期结果 |
|--------|------|----------|
| 危险命令拦截 | 让 AI 执行 `rm -rf /` | 命令被拦截，返回错误 |
| 命令超时 | 设为 5 秒，执行 `sleep 10` | 命令超时被终止 |
| 工作空间隔离 | 启用后重启应用，让 AI 读取 `/etc/passwd` | 路径验证失败 |
| 审计日志 | 启用后执行工具 | `data/audit_logs/` 中有记录 |

⚠️ **注意**：工作空间隔离（`restrict_to_workspace`）需要重启应用后才能生效。

### 渠道配置验证

| 验证项 | 操作 | 预期结果 |
|--------|------|----------|
| 渠道启用 | 启用 Telegram 并填入 Token | `/api/channels/status` 显示 running |
| 白名单 | 设置 allow_from | 非白名单用户消息被忽略 |
| 连接测试 | `POST /api/channels/telegram/test` | 返回 success: true |

### 技能配置验证

| 验证项 | 操作 | 预期结果 |
|--------|------|----------|
| 技能列表 | `GET /api/skills` | 返回所有技能及状态 |
| 禁用技能 | 禁用 baidu-search | AI 不再使用百度搜索 |
| always 技能 | 设为 always=true | 系统提示词中包含完整技能内容 |
| 依赖检查 | 技能有未安装的依赖 | `requirements_met: false` |
