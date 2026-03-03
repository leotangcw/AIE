# LLM 提供商 (Providers)

> CountBot 的 LLM 提供商子系统，通过 LiteLLM 统一接口支持多种大语言模型。

## 目录

- [设计理念](#设计理念)
- [架构概览](#架构概览)
- [支持的提供商](#支持的提供商)
- [核心组件](#核心组件)
  - [LLMProvider](#llmprovider)
  - [LiteLLMProvider](#litellmprovider)
  - [StreamChunk](#streamchunk)
- [流式接口](#流式接口)
- [提供商注册表](#提供商注册表)
- [配置方式](#配置方式)
- [模型切换](#模型切换)
- [工具调用解析](#工具调用解析)
- [语音转录](#语音转录)
- [添加新提供商](#添加新提供商)
- [相关文件](#相关文件)

## 设计理念

1. **统一接口** — 所有提供商实现 `LLMProvider` 基类，上层代码无需关心具体实现
2. **流式优先** — 唯一的调用方法是 `chat_stream()`，返回 `AsyncIterator[StreamChunk]`
3. **LiteLLM 驱动** — 通过 LiteLLM 库统一处理不同提供商的 API 差异
4. **注册表模式** — 提供商元数据集中管理，支持动态发现

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    Agent Loop                            │
│                                                          │
│  provider.chat_stream(messages, tools, model)            │
│       │                                                  │
│       ▼                                                  │
│  ┌──────────────────────────────────────────────────┐   │
│  │              LiteLLMProvider                       │   │
│  │                                                    │   │
│  │  _configure_litellm(api_key, api_base)            │   │
│  │       │                                            │   │
│  │       ▼                                            │   │
│  │  litellm.acompletion(                             │   │
│  │      model="openai/gpt-5.3",                       │   │
│  │      messages=[...],                              │   │
│  │      tools=[...],                                 │   │
│  │      stream=True,                                 │   │
│  │  )                                                │   │
│  │       │                                            │   │
│  │       ▼                                            │   │
│  │  async for chunk in response:                     │   │
│  │      yield StreamChunk(content=..., tool_call=...)│   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │           Provider Registry                        │   │
│  │                                                    │   │
│  │  openrouter │ anthropic │ openai │ deepseek       │   │
│  │  gemini │ moonshot │ zhipu │ groq │ mistral       │   │
│  │  qwen │ hunyuan │ ernie │ doubao │ minimax        │   │
│  │  vllm │ ollama │ lm_studio │ custom_*             │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## 支持的提供商

| 提供商 | ID | 默认模型 | API Base | 说明 |
|--------|-----|----------|----------|------|
| vLLM | `vllm` | 自定义 | `http://localhost:8000/v1` | 本地部署 |
| Ollama | `ollama` | `llama3.2` | `http://localhost:11434` | 本地部署 |
| LM Studio | `lm_studio` | 自定义 | `http://localhost:1234/v1` | 本地部署 |
| Custom (OpenAI) | `custom_openai` | 自定义 | 自定义 | OpenAI 兼容 API |
| Custom (Gemini) | `custom_gemini` | 自定义 | 自定义 | Gemini 兼容 API |
| Custom (Anthropic) | `custom_anthropic` | 自定义 | 自定义 | Anthropic 兼容 API |

## 核心组件

### LLMProvider

**文件**: `backend/modules/providers/base.py`

LLM 提供商抽象基类。

```python
class LLMProvider(ABC):
    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str | None = None,
        timeout: float = 120.0,
        max_retries: int = 3,
    ): ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncIterator[StreamChunk]: ...

    @abstractmethod
    def get_default_model(self) -> str: ...

    async def transcribe(self, audio_file: bytes, ...) -> str: ...
```

### StreamChunk

流式响应块数据类：

```python
@dataclass
class StreamChunk:
    content: str | None = None           # 文本内容
    tool_call: ToolCall | None = None    # 工具调用
    finish_reason: str | None = None     # 结束原因
    usage: dict[str, int] | None = None  # Token 用量
    error: str | None = None             # 错误信息
    reasoning_content: str | None = None # 思维链内容

    @property
    def is_content(self) -> bool: ...
    @property
    def is_tool_call(self) -> bool: ...
    @property
    def is_done(self) -> bool: ...
    @property
    def is_error(self) -> bool: ...
    @property
    def is_reasoning(self) -> bool: ...
```

### ToolCall

工具调用数据类：

```python
@dataclass
class ToolCall:
    id: str                    # 调用 ID
    name: str                  # 工具名称
    arguments: dict[str, Any]  # 工具参数
```

### LiteLLMProvider

**文件**: `backend/modules/providers/litellm_provider.py`

基于 LiteLLM 的统一提供商实现。

```python
provider = LiteLLMProvider(
    api_key="your-api-key",
    api_base="https://api.openai.com/v1",
    default_model="gpt-5.3",
    timeout=120.0,
    max_retries=3,
)
```

#### chat_stream 流程

```
chat_stream(messages, tools, model)
  │
  ├─ _configure_litellm(api_key, api_base)
  │   └─ 设置环境变量和 LiteLLM 配置
  │
  ├─ 构建模型名称
  │   └─ 根据 provider registry 添加前缀
  │       如 zhipu 的 glm-5 → openai/glm-5
  │
  ├─ litellm.acompletion(
  │     model=model_name,
  │     messages=messages,
  │     tools=tools,
  │     stream=True,
  │     temperature=temperature,
  │     max_tokens=max_tokens,
  │  )
  │
  └─ async for chunk in response:
      ├─ 解析 content → yield StreamChunk(content=...)
      ├─ 解析 tool_calls → yield StreamChunk(tool_call=...)
      ├─ 解析 reasoning → yield StreamChunk(reasoning_content=...)
      └─ 解析 finish_reason → yield StreamChunk(finish_reason=...)
```

#### 错误处理

LiteLLMProvider 将 LLM API 错误转换为友好的中文提示：

```python
_format_error_message(raw_error)
# "AuthenticationError" → "API 密钥无效，请检查设置"
# "RateLimitError" → "请求频率过高，请稍后重试"
# "ContextWindowExceeded" → "对话内容过长，请清理历史消息"
```

## 流式接口

CountBot 只使用流式接口（`chat_stream`），不提供同步的 `generate()` 方法。

### 消费方式

```python
# 方式 1: 流式消费（WebSocket / SSE）
async for chunk in provider.chat_stream(messages, tools):
    if chunk.is_content:
        yield chunk.content  # 实时推送给前端
    if chunk.is_tool_call:
        # 处理工具调用
    if chunk.is_error:
        # 处理错误

# 方式 2: 收集完整响应（CLI / Cron）
content = ""
async for chunk in provider.chat_stream(messages, tools):
    if chunk.is_content:
        content += chunk.content
```

### 思维链支持

部分模型（如 DeepSeek R1）支持思维链输出：

```python
async for chunk in provider.chat_stream(messages, tools):
    if chunk.is_reasoning:
        # 思维链内容（不展示给用户，但记录在消息中）
        reasoning += chunk.reasoning_content
```

## 提供商注册表

**文件**: `backend/modules/providers/registry.py`

集中管理所有提供商的元数据：

```python
@dataclass
class ProviderMetadata:
    id: str                    # 提供商 ID
    name: str                  # 显示名称
    default_api_base: str      # 默认 API 地址
    default_model: str         # 默认模型
    litellm_prefix: str        # LiteLLM 模型前缀
    skip_prefixes: tuple       # 跳过的前缀（避免重复添加）
    env_key: str               # 环境变量名
    env_extras: tuple          # 额外环境变量
    model_overrides: dict      # 模型级参数覆盖
```

### 模型名称映射

LiteLLM 需要特定格式的模型名称：

| 提供商 | 用户输入 | LiteLLM 格式 |
|--------|----------|---------------|
| 智谱 | `glm-5` | `openai/glm-5` |
| DeepSeek | `deepseek-chat` | `deepseek/deepseek-chat` |
| Gemini | `gemini-3.0` | `gemini/gemini-2.5-flash` |
| Ollama | `glm` | `deepseek |
| OpenAI | `gpt-5.2` | `gpt-5.3` (无前缀) |

## 配置方式

通过 Web UI → 设置页面配置：

1. 选择提供商
2. 填入 API Key
3. （可选）修改 API Base
4. 选择模型
5. 调整温度、最大 Token 等参数

配置存储在数据库 `settings` 表中。

## 模型切换

切换模型只需修改配置：

```
PUT /api/settings
{
  "model": {
    "provider": "openai",
    "model": "gpt-5.3"
  }
}
```

切换后立即生效，无需重启。

## 工具调用解析

**文件**: `backend/modules/providers/tool_parser.py`

处理不同提供商返回的工具调用格式差异。LiteLLM 已经做了大部分标准化，`tool_parser` 处理边缘情况。

## 语音转录

**文件**: `backend/modules/providers/transcription.py`

通过 LLM 提供商的语音转录 API（如 OpenAI Whisper）将音频转为文字：

```python
text = await provider.transcribe(
    audio_file=audio_bytes,
    model="whisper-1",
    language="zh",
)
```

## 添加新提供商

### 步骤

1. 在 `registry.py` 添加元数据：

```python
PROVIDER_REGISTRY["my_provider"] = ProviderMetadata(
    id="my_provider",
    name="My Provider",
    default_api_base="https://api.myprovider.com/v1",
    default_model="my-model",
    litellm_prefix="openai",  # 如果兼容 OpenAI 格式
    env_key="MY_PROVIDER_API_KEY",
)
```

2. 如果 LiteLLM 已支持该提供商，无需额外代码
3. 如果需要自定义逻辑，可以继承 `LLMProvider` 创建新实现

大多数情况下，只需在注册表中添加元数据即可，LiteLLM 会处理 API 调用。

## 相关文件

| 文件 | 说明 |
|------|------|
| `backend/modules/providers/base.py` | LLMProvider 基类 + StreamChunk |
| `backend/modules/providers/litellm_provider.py` | LiteLLM 统一实现 |
| `backend/modules/providers/registry.py` | 提供商注册表 |
| `backend/modules/providers/tool_parser.py` | 工具调用解析 |
| `backend/modules/providers/transcription.py` | 语音转录 |
| `backend/modules/config/schema.py` | ProviderConfig 配置模型 |
| `backend/api/settings.py` | 提供商配置 API |
