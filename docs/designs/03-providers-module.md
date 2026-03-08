# Providers 模块设计

**版本**: v1.0
**更新日期**: 2026-03-08
**文件路径**: `backend/modules/providers/`

---

## 1. 模块概述

Providers 模块负责与大语言模型 (LLM) 进行交互，提供统一的抽象层，支持多种模型提供商。

### 核心功能
- LLM 模型抽象
- 流式响应处理
- 工具调用解析
- 多模型支持

---

## 2. 模块结构

```
providers/
├── __init__.py           # 模块导出
├── base.py               # Provider 基类
├── litellm_provider.py   # LiteLLM Provider (主要实现)
├── local_provider.py     # 本地模型 Provider
├── local_factory.py      # 本地模型工厂
├── registry.py           # Provider 注册表
├── tool_parser.py        # 工具调用解析器
└── transcription.py      # 语音转写
```

---

## 3. 核心组件设计

### 3.1 Provider 基类

**文件**: `base.py`

#### 职责
- 定义 Provider 接口
- 提供通用实现

#### 核心方法

```python
class BaseProvider(ABC):
    @abstractmethod
    async def chat_stream(
        self,
        messages: list,
        tools: list = None,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[Chunk]:
        """流式聊天"""

    @abstractmethod
    async def chat(
        self,
        messages: list,
        tools: list = None,
        model: str = None,
    ) -> str:
        """非流式聊天"""

    @abstractmethod
    async def embeddings(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """文本嵌入"""
```

### 3.2 LiteLLM Provider

**文件**: `litellm_provider.py`

#### 职责
- 基于 LiteLLM 库实现 Provider
- 支持多种模型提供商
- 处理流式响应和工具调用

#### 核心类

```python
class LiteLLMProvider(BaseProvider):
    def __init__(
        self,
        api_key: str,           # API 密钥
        api_base: str = None,   # API 基础 URL
        default_model: str = None,  # 默认模型
        timeout: float = 120.0, # 超时时间
        max_retries: int = 3,   # 最大重试次数
        provider_id: str = None, # 提供商 ID
    ):
        """初始化 LiteLLM Provider"""

    async def chat_stream(
        self,
        messages: list,
        tools: list = None,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[Chunk]:
        """
        流式聊天

        返回 Chunk 对象:
        - is_content: 是否为文本内容
        - content: 文本内容
        - is_tool_call: 是否为工具调用
        - tool_call: 工具调用对象
        - is_reasoning: 是否为推理内容
        - reasoning_content: 推理内容
        - is_done: 是否完成
        - finish_reason: 完成原因
        - is_error: 是否错误
        - error: 错误信息
        """
```

#### 支持的模型提供商

| 提供商 | 配置示例 |
|--------|---------|
| OpenAI | `provider: openai`, `model: gpt-4` |
| Anthropic | `provider: anthropic`, `model: claude-sonnet-4-20250514` |
| Azure OpenAI | `provider: azure`, `api_base: https://xxx.openai.azure.com` |
| Ollama | `provider: ollama`, `api_base: http://localhost:11434` |
| 自定义 | `provider: custom`, `api_base: https://custom.api.com` |

### 3.3 Local Provider

**文件**: `local_provider.py`

#### 职责
- 支持本地部署的模型
- Ollama 集成
- vLLM 集成

#### 支持的本地模型

| 模型类型 | 支持框架 |
|---------|---------|
| LLM | Ollama, vLLM, LLaMA.cpp |
| Embedding | Sentence Transformers |
| TTS | Coqui TTS, Edge TTS |
| ASR | Whisper, FunASR |

### 3.4 Provider Registry

**文件**: `registry.py`

#### 职责
- Provider 注册
- Provider 发现
- 元数据管理

#### 核心方法

```python
def get_provider_metadata(provider_id: str) -> ProviderMetadata:
    """获取提供商元数据"""

def register_provider(
    provider_id: str,
    metadata: ProviderMetadata,
):
    """注册提供商"""
```

### 3.5 Tool Parser

**文件**: `tool_parser.py`

#### 职责
- 解析 LLM 返回的工具调用
- 格式转换
- 参数验证

---

## 4. 数据流

### 4.1 流式响应处理

```
┌─────────────────────────────────────────────────────────────┐
│              流式响应处理流程                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  LLM 响应流                                                   │
│     │                                                        │
│     ▼                                                        │
│  LiteLLM streaming                                         │
│     │                                                        │
│     ▼                                                        │
│  Chunk 解析                                                   │
│     │                                                        │
│     ├──→ content → Chunk(is_content=True, content="...")    │
│     │                                                        │
│     ├──→ tool_call → Chunk(is_tool_call=True, ...)          │
│     │                                                        │
│     └──→ done → Chunk(is_done=True, finish_reason="stop")   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 工具调用处理

```python
# LLM 返回
{
    "choices": [{
        "delta": {
            "tool_calls": [{
                "id": "call_123",
                "function": {
                    "name": "read_file",
                    "arguments": '{"path": "file.txt"}'
                }
            }]
        }
    }]
}

# 解析后
Chunk(
    is_tool_call=True,
    tool_call=ToolCall(
        id="call_123",
        name="read_file",
        arguments={"path": "file.txt"}
    )
)
```

---

## 5. 配置

### 5.1 Provider 配置

```yaml
providers:
  openai:
    api_key: ${OPENAI_API_KEY}
    api_base: https://api.openai.com/v1

  anthropic:
    api_key: ${ANTHROPIC_API_KEY}
    api_base: https://api.anthropic.com

  ollama:
    api_key: ""  # 本地不需要
    api_base: http://localhost:11434

model:
  provider: openai  # 默认提供商
  model: gpt-4      # 默认模型
  temperature: 0.7
  max_tokens: 4096
  max_iterations: 25
```

### 5.2 环境变量

```bash
# OpenAI
OPENAI_API_KEY=sk-xxx

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxx

# Azure
AZURE_API_KEY=xxx
AZURE_API_BASE=https://xxx.openai.azure.com
AZURE_API_VERSION=2023-05-15

# Ollama
OLLAMA_API_BASE=http://localhost:11434
```

---

## 6. 使用示例

### 6.1 基本使用

```python
from backend.modules.providers.litellm_provider import LiteLLMProvider

provider = LiteLLMProvider(
    api_key="sk-xxx",
    default_model="gpt-4",
)

# 流式聊天
async for chunk in provider.chat_stream(
    messages=[
        {"role": "user", "content": "你好"}
    ],
    temperature=0.7,
):
    if chunk.is_content:
        print(chunk.content, end="")
    elif chunk.is_tool_call:
        print(f"\n调用工具：{chunk.tool_call.name}")
    elif chunk.is_done:
        print(f"\n完成：{chunk.finish_reason}")
```

### 6.2 带工具调用

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文件内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
                },
                "required": ["path"]
            }
        }
    }
]

async for chunk in provider.chat_stream(
    messages=[{"role": "user", "content": "读取 file.txt"}],
    tools=tools,
):
    if chunk.is_tool_call:
        # 执行工具
        result = await execute_tool(
            chunk.tool_call.name,
            chunk.tool_call.arguments
        )
```

### 6.3 非流式调用

```python
response = await provider.chat(
    messages=[{"role": "user", "content": "你好"}],
    model="gpt-4",
)
print(response)
```

---

## 7. 错误处理

### 7.1 错误类型

| 错误类型 | 处理策略 |
|---------|---------|
| API 超时 | 重试 (指数退避) |
| 速率限制 | 等待后重试 |
| 认证失败 | 返回错误，不重试 |
| 模型错误 | 返回错误，不重试 |
| 网络错误 | 重试 (最多 3 次) |

### 7.2 错误 Chunk

```python
Chunk(
    is_error=True,
    error="API 请求失败：超时"
)
```

---

## 8. 性能优化

### 8.1 连接池
- 使用 httpx 连接池
- 复用 TCP 连接

### 8.2 超时控制
- 请求超时：120 秒
- 流式超时：600 秒

### 8.3 重试机制
- 最大重试：3 次
- 指数退避：1s, 2s, 4s

---

## 9. 待办事项 (TODO)

### 高优先级
- [ ] 添加更多本地模型支持
- [ ] 优化 Embedding 性能
- [ ] 实现模型自动降级

### 中优先级
- [ ] 添加 TTS/ASR Provider
- [ ] 支持多模态模型
- [ ] 实现 Provider 健康检查

### 低优先级
- [ ] 模型性能监控
- [ ] Token 使用统计
- [ ] 成本优化建议
