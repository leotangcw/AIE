# Agent 模块设计

**版本**: v1.0
**更新日期**: 2026-03-08
**文件路径**: `backend/modules/agent/`

---

## 1. 模块概述

Agent 模块是 AIE 系统的核心 AI 处理引擎，负责:
- 接收用户消息
- 构建上下文
- 调用 LLM 进行推理
- 执行工具
- 生成响应

---

## 2. 模块结构

```
agent/
├── __init__.py           # 模块导出
├── loop.py               # AgentLoop - AI 处理主循环
├── context.py            # ContextBuilder - 上下文构建器
├── memory.py             # MemoryStore - 记忆存储
├── skills.py             # SkillsLoader - 技能加载器
├── subagent.py           # SubagentManager - 子 Agent 管理器
├── personalities.py      # 性格配置
├── rules.py              # 规则引擎
├── experience.py         # 经验学习
├── knowledge.py          # 知识库集成
├── research.py           # 研究功能
├── research_logger.py    # 研究日志
├── security.py           # 安全检查
├── heartbeat.py          # 心跳服务
├── task_manager.py       # 任务管理器
├── prompts.py            # Prompt 模板
├── consolidator.py       # 记忆压缩器
├── vector_store.py       # 向量存储
├── compactor.py          # (空) 记忆压缩
└── analyzer.py           # 分析器
```

---

## 3. 核心组件设计

### 3.1 AgentLoop

**文件**: `loop.py`

#### 职责
- 处理用户消息
- 管理 AI 对话迭代
- 执行工具调用
- 流式响应生成

#### 核心方法

```python
class AgentLoop:
    def __init__(
        self,
        provider,              # LLM 提供商
        workspace: Path,       # 工作空间
        tools,                 # 工具注册表
        context_builder=None,  # 上下文构建器
        session_manager=None,  # 会话管理器
        subagent_manager=None, # 子 Agent 管理器
        model: str = None,     # 模型名称
        max_iterations: int = 25,  # 最大迭代次数
        max_retries: int = 3,      # 工具执行重试次数
        temperature: float = 0.7,  # 温度
        max_tokens: int = 4096,    # 最大 token 数
    ):
        """初始化 AgentLoop"""

    async def process_message(
        self,
        message: str,              # 用户消息
        session_id: str,           # 会话 ID
        context: list = None,      # 对话历史
        media: list = None,        # 媒体附件
        channel: str = None,       # 来源渠道
        chat_id: str = None,       # 来源聊天 ID
        cancel_token=None,         # 取消令牌
        yield_intermediate: bool = True,  # 是否输出中间内容
    ) -> AsyncIterator[str]:
        """处理用户消息并生成流式响应"""

    async def execute_tool(
        self,
        tool_name: str,        # 工具名称
        arguments: dict,       # 工具参数
    ) -> str:
        """执行单个工具"""

    async def process_direct(
        self,
        content: str,          # 消息内容
        session_id: str,       # 会话 ID
        channel: str,          # 渠道
        chat_id: str,          # 聊天 ID
    ) -> str:
        """直接处理消息（用于 CLI 或 Cron）"""
```

#### 处理流程

```
┌─────────────────────────────────────────────────────────────┐
│                    AgentLoop 流程                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. 接收消息                                                 │
│     │                                                        │
│     ▼                                                        │
│  2. 构建上下文 (ContextBuilder)                              │
│     │                                                        │
│     ▼                                                        │
│  3. 调用 LLM (Provider)                                      │
│     │                                                        │
│     ▼                                                        │
│  4. 有工具调用？ ────是───→ 5. 执行工具                      │
│     │                    │                                   │
│     │否                  │                                   │
│     │                    ▼                                   │
│     │              6. 添加工具结果到上下文                    │
│     │                    │                                   │
│     │                    ▼                                   │
│     │              7. 返回步骤 3 继续迭代                      │
│     │                                                        │
│     ▼                                                        │
│  8. 返回最终响应                                              │
│     │                                                        │
│     ▼                                                        │
│  9. 保存到会话历史                                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### 迭代限制

- `max_iterations`: 最大迭代次数 (默认 25)
- 防止无限工具调用循环
- 每次迭代记录日志

### 3.2 ContextBuilder

**文件**: `context.py`

#### 职责
- 构建 LLM 对话上下文
- 管理对话历史
- 集成记忆、技能、规则

#### 核心方法

```python
class ContextBuilder:
    def __init__(
        self,
        workspace: Path,       # 工作空间
        memory: MemoryStore,   # 记忆存储
        skills: SkillsLoader,  # 技能加载器
        persona_config,        # 角色配置
    ):
        """初始化上下文构建器"""

    def build_messages(
        self,
        history: list,         # 对话历史
        current_message: str,  # 当前消息
        media: list = None,    # 媒体附件
        channel: str = None,   # 渠道
        chat_id: str = None,   # 聊天 ID
    ) -> list:
        """构建完整的消息列表"""

    def add_assistant_message(
        self,
        messages: list,        # 消息列表
        content: str = None,   # 内容
        tool_calls: list = None,  # 工具调用
        reasoning_content: str = None,  # 推理内容
    ) -> list:
        """添加 AI 消息"""

    def add_tool_result(
        self,
        messages: list,        # 消息列表
        tool_id: str,          # 工具 ID
        tool_name: str,        # 工具名称
        result: str,           # 执行结果
    ) -> list:
        """添加工具执行结果"""
```

#### 消息格式

```python
# 系统消息
{
    "role": "system",
    "content": "你是小 C，一个专业的 AI 助手..."
}

# 用户消息
{
    "role": "user",
    "content": "你好，请帮我..."
}

# AI 消息 (带工具调用)
{
    "role": "assistant",
    "content": "我来帮你...",
    "tool_calls": [
        {
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "read_file",
                "arguments": {"path": "file.txt"}
            }
        }
    ]
}

# 工具结果
{
    "role": "tool",
    "tool_call_id": "call_123",
    "name": "read_file",
    "content": "文件内容..."
}
```

### 3.3 MemoryStore

**文件**: `memory.py`

#### 职责
- 长期记忆存储
- 记忆检索
- 记忆压缩

#### 核心方法

```python
class MemoryStore:
    def __init__(self, memory_dir: Path):
        """初始化记忆存储"""

    def add_memory(
        self,
        session_id: str,       # 会话 ID
        content: str,          # 记忆内容
        importance: float,     # 重要性分数
    ) -> str:
        """添加记忆"""

    def get_memories(
        self,
        query: str,            # 查询
        top_k: int = 5,        # 返回数量
    ) -> list:
        """检索记忆"""

    def compact_memories(
        self,
        session_id: str,       # 会话 ID
    ) -> str:
        """压缩记忆"""
```

### 3.4 SkillsLoader

**文件**: `skills.py`

#### 职责
- 加载技能文件
- 管理技能目录
- 提供技能查询

#### 技能文件格式

技能文件使用 Markdown 格式:

```markdown
---
name: 技能名称
description: 技能描述
version: 1.0.0
---

## 触发条件
当用户请求...时触发

## 执行步骤
1. 第一步...
2. 第二步...

## 示例
用户：...
AI: ...
```

### 3.5 SubagentManager

**文件**: `subagent.py`

#### 职责
- 管理子 Agent
- 协调多 Agent 协作
- 任务分配

---

## 4. 辅助组件

### 4.1 性格系统 (personalities.py)

提供多种 AI 性格预设:

| ID | 名称 | 描述 |
|----|------|------|
| grumpy | 暴躁型 | 直接、不耐烦 |
| gentle | 温柔型 | 温和、体贴 |
| humorous | 幽默型 | 风趣、有趣 |
| professional | 专业型 | 正式、专业 |
| cute | 可爱型 | 活泼、可爱 |

### 4.2 规则引擎 (rules.py)

#### 职责
- 加载企业规则
- 评估行为合规性
- 应用规则约束

### 4.3 经验学习 (experience.py)

#### 职责
- 从反馈中学习
- 总结经验教训
- 优化行为

### 4.4 知识库集成 (knowledge.py)

#### 职责
- 连接知识源
- RAG 检索增强
- 知识更新

### 4.5 研究功能 (research.py, research_logger.py)

#### 职责
- 执行深度研究
- 记录研究过程
- 生成研究报告

### 4.6 心跳服务 (heartbeat.py)

#### 职责
- 定期问候用户
- 检测空闲会话
- 触发主动交互

---

## 5. 配置参数

### 5.1 AgentLoop 配置

```yaml
agent:
  max_iterations: 25      # 最大迭代次数
  max_retries: 3          # 工具执行重试次数
  retry_delay: 1.0        # 重试延迟 (秒)
  temperature: 0.7        # LLM 温度
  max_tokens: 4096        # 最大 token 数
```

### 5.2 记忆配置

```yaml
memory:
  enabled: true
  max_history_messages: 100  # 最大历史消息数
  importance_threshold: 0.5  # 重要性阈值
```

---

## 6. 使用示例

### 6.1 基本使用

```python
from backend.modules.agent.loop import AgentLoop
from backend.modules.providers.litellm_provider import LiteLLMProvider
from backend.modules.tools.setup import register_all_tools

# 创建 Provider
provider = LiteLLMProvider(
    api_key="sk-xxx",
    default_model="gpt-4",
)

# 注册工具
tools = register_all_tools(
    workspace=Path("./workspace"),
)

# 创建 AgentLoop
agent = AgentLoop(
    provider=provider,
    workspace=Path("./workspace"),
    tools=tools,
    max_iterations=25,
)

# 处理消息
async for chunk in agent.process_message(
    message="你好，请帮我分析这个文件",
    session_id="session_123",
):
    print(chunk, end="")
```

### 6.2 直接处理 (用于 CLI/Cron)

```python
response = await agent.process_direct(
    content="执行定时任务",
    session_id="cron:task_1",
    channel="cron",
)
print(response)
```

---

## 7. 错误处理

### 7.1 工具执行错误

```python
try:
    result = await agent.execute_tool(tool_name, args)
except Exception as e:
    # 记录错误
    # 发送错误通知
    # 返回错误消息
```

### 7.2 LLM 错误

```python
# Provider 返回错误
if chunk.is_error:
    yield chunk.error
    return
```

---

## 8. 性能优化

### 8.1 流式处理
- 使用 AsyncIterator 流式返回结果
- 减少用户等待时间

### 8.2 上下文管理
- 智能截断过长的对话历史
- 记忆压缩减少 token 消耗

### 8.3 工具调用优化
- 限制最大工具调用次数
- 工具执行结果缓存

---

## 9. 待办事项 (TODO)

### 高优先级
- [ ] 实现更智能的记忆压缩算法
- [ ] 优化长上下文处理
- [ ] 增加更多性格预设

### 中优先级
- [ ] 多 Agent 协作优化
- [ ] 经验学习自动化
- [ ] 知识库 RAG 优化

### 低优先级
- [ ] 语音交互支持
- [ ] 可视化调试工具
