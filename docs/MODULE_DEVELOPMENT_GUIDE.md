# 模块开发规范

> 本文档规定了 AIE 项目中各独立模块的开发规范，确保模块间的一致性和可维护性。

---

## 📋 目录

- [模块设计原则](#模块设计原则)
- [模块目录结构](#模块目录结构)
- [模块配置](#模块配置)
- [模块接口规范](#模块接口规范)
- [模块测试规范](#模块测试规范)
- [模块文档规范](#模块文档规范)
- [模块版本管理](#模块版本管理)

---

## 🎯 模块设计原则

### 1. 高内聚，低耦合

- 每个模块只负责单一职责
- 模块间通过定义的接口通信
- 避免循环依赖

### 2. 独立可测试

- 模块可以独立运行测试
- 不依赖外部服务（使用 Mock）
- 提供测试夹具（fixtures）

### 3. 配置驱动

- 行为通过配置控制
- 支持环境变量覆盖
- 提供合理的默认值

### 4. 完善的日志

- 关键操作记录日志
- 错误信息清晰可追溯
- 日志级别合理

---

## 📁 模块目录结构

### 后端模块结构

```
backend/modules/{module_name}/
├── __init__.py        # 模块导出
├── config.py          # 模块配置
├── service.py         # 核心服务逻辑
├── models.py          # 数据模型（如有）
├── handlers.py        # 请求处理器（如有）
├── utils.py           # 工具函数
├── exceptions.py      # 模块异常定义
└── tests/             # 测试目录
    ├── __init__.py
    ├── conftest.py    # pytest fixtures
    ├── test_service.py
    └── test_handlers.py
```

### 示例：Agent 模块

```
backend/modules/agent/
├── __init__.py
├── config.py
├── loop.py            # Agent 循环核心
├── context.py         # 上下文构建
├── memory.py          # 记忆存储
├── skills.py          # 技能加载
├── analyzer.py        # 消息分析
├── exceptions.py
└── tests/
    ├── conftest.py
    ├── test_loop.py
    ├── test_context.py
    └── test_memory.py
```

### 前端模块结构

```
frontend/src/modules/{module_name}/
├── index.ts           # 模块导出
├── components/        # Vue 组件
│   ├── ModulePanel.vue
│   └── ModuleItem.vue
├── composables/       # 组合式 API
│   ├── useModule.ts
│   └── useModuleStore.ts
├── types/             # TypeScript 类型
│   └── index.ts
├── api/               # API 调用
│   └── index.ts
├── utils/             # 工具函数
│   └── index.ts
└── tests/             # 测试目录
    ├── ModulePanel.test.ts
    └── useModule.test.ts
```

---

## ⚙️ 模块配置

### 配置类定义

```python
# backend/modules/agent/config.py
from pydantic import BaseModel, Field
from typing import Optional


class AgentConfig(BaseModel):
    """Agent 模块配置"""

    # 必需配置
    model_name: str = Field(..., description="LLM 模型名称")
    api_key: str = Field(..., description="API 密钥")

    # 可选配置，带默认值
    max_tokens: int = Field(default=2048, description="最大生成 token 数")
    temperature: float = Field(default=0.7, description="生成温度")
    max_history_messages: int = Field(default=50, description="保留历史消息数")

    # 高级配置
    enable_memory: bool = Field(default=True, description="是否启用记忆")
    enable_skills: bool = Field(default=True, description="是否启用技能")

    class Config:
        env_prefix = "AGENT_"  # 环境变量前缀
        extra = "ignore"  # 忽略额外字段
```

### 配置加载

```python
# backend/modules/agent/__init__.py
import os
from .config import AgentConfig


def load_config() -> AgentConfig:
    """从环境变量和配置文件加载配置"""
    return AgentConfig(
        model_name=os.getenv("AGENT_MODEL_NAME", "claude-sonnet-4-6"),
        api_key=os.getenv("AGENT_API_KEY", ""),
        max_tokens=int(os.getenv("AGENT_MAX_TOKENS", "2048")),
        temperature=float(os.getenv("AGENT_TEMPERATURE", "0.7")),
    )
```

### 环境变量示例

```bash
# .env.example
# Agent 模块配置
AGENT_MODEL_NAME=claude-sonnet-4-6
AGENT_API_KEY=your-api-key
AGENT_MAX_TOKENS=2048
AGENT_TEMPERATURE=0.7
AGENT_ENABLE_MEMORY=true
AGENT_ENABLE_SKILLS=true
```

---

## 🔌 模块接口规范

### 服务层接口

```python
# backend/modules/agent/service.py
from abc import ABC, abstractmethod
from typing import Optional


class IAgentService(ABC):
    """Agent 服务接口"""

    @abstractmethod
    async def process_message(
        self,
        message: str,
        session_id: str,
        context: Optional[dict] = None,
    ) -> dict:
        """处理用户消息"""
        pass

    @abstractmethod
    async def get_session_history(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[dict]:
        """获取会话历史"""
        pass

    @abstractmethod
    async def clear_session(
        self,
        session_id: str,
    ) -> bool:
        """清空会话"""
        pass
```

### API 路由接口

```python
# backend/api/agent.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/agent", tags=["agent"])


class MessageRequest(BaseModel):
    message: str
    session_id: str


class MessageResponse(BaseModel):
    content: str
    session_id: str


@router.post("/chat", response_model=MessageResponse)
async def chat(request: MessageRequest):
    """处理聊天消息"""
    try:
        # 调用服务层
        result = await agent_service.process_message(
            message=request.message,
            session_id=request.session_id,
        )
        return MessageResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 🧪 模块测试规范

### 测试文件命名

```
backend/modules/{module}/tests/
├── conftest.py           # pytest 配置和 fixtures
├── test_{feature}.py     # 功能测试
├── test_{component}.py   # 组件测试
└── test_integration.py   # 集成测试
```

### pytest fixtures

```python
# backend/modules/agent/tests/conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.modules.agent import AgentLoop, AgentConfig


@pytest.fixture
def agent_config():
    """创建测试配置"""
    return AgentConfig(
        model_name="test-model",
        api_key="test-key",
        max_tokens=100,
    )


@pytest.fixture
def agent_loop(agent_config):
    """创建 Agent 实例"""
    return AgentLoop(config=agent_config)


@pytest.fixture
def mock_llm_provider():
    """模拟 LLM Provider"""
    mock = AsyncMock()
    mock.generate.return_value = {
        "content": "Hello, I am an AI assistant.",
        "tool_calls": [],
    }
    return mock


@pytest.fixture
def sample_messages():
    """示例消息列表"""
    return [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
```

### 单元测试示例

```python
# backend/modules/agent/tests/test_loop.py
import pytest
from unittest.mock import AsyncMock, patch

from backend.modules.agent.loop import AgentLoop


class TestAgentLoop:
    """AgentLoop 测试类"""

    def test_init(self, agent_config):
        """测试初始化"""
        loop = AgentLoop(config=agent_config)
        assert loop.config == agent_config
        assert loop.is_running is False

    @pytest.mark.asyncio
    async def test_process_message(self, agent_loop, mock_llm_provider):
        """测试消息处理"""
        with patch.object(agent_loop, "_provider", mock_llm_provider):
            result = await agent_loop.process_message("Hello")

            assert result is not None
            assert "content" in result
            mock_llm_provider.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_with_tool_call(
        self, agent_loop, mock_llm_provider
    ):
        """测试带工具调用的消息处理"""
        mock_llm_provider.generate.return_value = {
            "content": "",
            "tool_calls": [
                {"name": "search", "arguments": {"query": "test"}}
            ],
        }

        result = await agent_loop.process_message("Search for test")

        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "search"
```

### 测试覆盖率

```bash
# 运行模块测试并生成覆盖率报告
pytest backend/modules/agent/tests/ \
    --cov=backend.modules.agent \
    --cov-report=html \
    --cov-report=term-missing \
    --cov-fail-under=80
```

---

## 📚 模块文档规范

### 模块 README

每个模块应包含 `README.md`：

```markdown
# Agent 模块

> Agent 核心循环，处理用户消息并生成响应

## 功能

- 消息处理
- 上下文管理
- 工具调用
- 记忆集成

## 使用示例

```python
from backend.modules.agent import AgentLoop

loop = AgentLoop(config)
response = await loop.process_message("Hello")
```

## 配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| model_name | str | - | LLM 模型 |
| max_tokens | int | 2048 | 最大生成数 |

## API

### process_message()

处理用户消息。

**参数**:
- `message` (str): 用户消息
- `session_id` (str): 会话 ID

**返回**:
- `dict`: 响应内容
```

### 代码注释

```python
class AgentLoop:
    """Agent 循环处理器

    负责管理对话循环，包括:
    - 消息预处理
    - LLM 调用
    - 工具执行
    - 响应生成

    Example:
        >>> loop = AgentLoop(config)
        >>> response = await loop.process_message("Hello")
    """

    async def process_message(self, message: str) -> dict:
        """处理单条消息

        Args:
            message: 用户输入的消息文本

        Returns:
            包含响应内容和工具调用的字典

        Raises:
            AgentError: 当处理失败时
            LLMError: 当 LLM 调用失败时
        """
        pass
```

---

## 📦 模块版本管理

### 版本号规范

遵循 [Semantic Versioning](https://semver.org/)：

```
MAJOR.MINOR.PATCH

v1.0.0  # 初始版本
v1.1.0  # 向后兼容的新功能
v1.1.1  # 向后兼容的问题修复
v2.0.0  # 不兼容的 API 变更
```

### 模块版本声明

```python
# backend/modules/agent/__init__.py
__version__ = "1.0.0"
__author__ = "AIE Team"
__all__ = ["AgentLoop", "AgentConfig", "process_message"]
```

### CHANGELOG

每个模块维护变更日志：

```markdown
# Changelog

## [1.1.0] - 2026-03-08

### Added
- 添加技能系统支持
- 添加记忆搜索功能

### Changed
- 优化上下文构建性能

### Fixed
- 修复工具调用参数解析错误

## [1.0.0] - 2026-03-01

### Added
- 初始版本
- 基础 Agent 循环
- 上下文管理
```

---

## 🔗 模块间通信

### 事件总线

```python
# backend/modules/events.py
from typing import Callable, Any


class EventBus:
    """简单事件总线"""

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = {}

    def on(self, event: str, handler: Callable):
        """注册事件处理器"""
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)

    def emit(self, event: str, data: Any):
        """触发事件"""
        if event in self._handlers:
            for handler in self._handlers[event]:
                handler(data)


# 全局事件总线实例
event_bus = EventBus()
```

### 模块间调用

```python
# 在 tools 模块中调用 memory 模块
from backend.modules.events import event_bus
from backend.modules.memory import MemoryStore


class ToolExecutor:
    def __init__(self, memory_store: MemoryStore):
        self.memory = memory_store

    async def execute_tool(self, name: str, args: dict):
        # 执行工具
        result = await self._call_tool(name, args)

        # 发布事件通知其他模块
        event_bus.emit("tool_executed", {
            "tool_name": name,
            "arguments": args,
            "result": result,
        })

        return result
```

---

## ✅ 模块开发检查清单

开发新模块时，确保完成以下项目：

- [ ] 创建模块目录结构
- [ ] 定义配置类
- [ ] 实现核心服务
- [ ] 定义异常类
- [ ] 编写单元测试（覆盖率 > 80%）
- [ ] 编写模块文档
- [ ] 添加到模块注册表
- [ ] 更新 CHANGELOG

---

## 📖 参考资源

- [Python 模块最佳实践](https://docs.python-guide.org/writing/structure/)
- [FastAPI 最佳实践](https://fastapi.tiangolo.com/)
- [Vue 3 组合式 API](https://vuejs.org/guide/reusability/composables.html)
