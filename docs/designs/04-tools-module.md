# Tools 模块设计

**版本**: v1.0
**更新日期**: 2026-03-08
**文件路径**: `backend/modules/tools/`

---

## 1. 模块概述

Tools 模块为 AIE 系统提供完整的工具系统，允许 AI Agent 执行各种操作。

### 核心功能
- 工具注册和管理
- 文件系统操作
- Shell 命令执行
- Web 搜索和抓取
- 图片上传
- 记忆管理
- 审计日志

---

## 2. 模块结构

```
tools/
├── __init__.py           # 模块导出
├── base.py               # Tool 基类
├── registry.py           # 工具注册表
├── setup.py              # 工具注册初始化
├── conversation_history.py # 工具调用对话历史
├── file_audit_logger.py  # 文件审计日志
│
├── 核心工具
├── filesystem.py         # 文件系统工具
├── shell.py              # Shell 执行工具
├── web.py                # Web 工具
├── memory_tool.py        # 记忆管理工具
├── image_uploader.py     # 图片上传工具
│
├── 媒体工具
├── send_media.py         # 媒体发送工具
├── screenshot.py         # 截图工具
│
├── 其他工具
├── file_search.py        # 文件搜索
├── example_tool.py       # 示例工具
├── factory.py            # (空) 工具工厂
├── spawn.py              # 派生工具
└── README.md             # 模块文档
```

---

## 3. 核心组件设计

### 3.1 Tool 基类

**文件**: `base.py`

#### 职责
- 定义工具接口
- 提供通用实现

#### 核心类

```python
class Tool(ABC):
    """所有工具必须继承的抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """JSON Schema 格式的参数定义"""

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """执行工具"""
```

### 3.2 ToolRegistry

**文件**: `registry.py`

#### 职责
- 工具注册
- 工具执行
- 工具定义生成 (用于 LLM)

#### 核心方法

```python
class ToolRegistry:
    def register(self, tool: Tool):
        """注册工具"""

    def get_tool(self, name: str) -> Tool:
        """获取工具"""

    async def execute(
        self,
        tool_name: str,
        arguments: dict,
        auto_record: bool = True,
    ) -> str:
        """执行工具"""

    def get_definitions(self) -> list:
        """获取所有工具定义 (用于 LLM)"""

    def set_session_id(self, session_id: str):
        """设置会话 ID (用于审计)"""

    def set_channel(self, channel: str):
        """设置渠道 (用于审计)"""
```

### 3.3 工具注册初始化

**文件**: `setup.py`

#### 职责
- 注册所有内置工具
- 配置工具参数

#### 注册的工具

```python
def register_all_tools(**kwargs) -> ToolRegistry:
    """注册所有工具"""

    registry = ToolRegistry()

    # 文件系统工具
    registry.register(ReadFileTool(workspace))
    registry.register(WriteFileTool(workspace))
    registry.register(EditFileTool(workspace))
    registry.register(ListDirTool(workspace))
    registry.register(SearchFileTool(workspace))

    # Shell 工具
    registry.register(ExecTool(workspace))

    # Web 工具
    registry.register(WebSearchTool())
    registry.register(WebFetchTool())

    # 记忆工具
    registry.register(MemoryTool(memory_store))

    # 图片工具
    registry.register(ImageUploader())
    registry.register(SendMediaTool())

    # 其他工具
    registry.register(ScreenshotTool())
    registry.register(SpawnTool(subagent_manager))

    return registry
```

---

## 4. 核心工具设计

### 4.1 文件系统工具

**文件**: `filesystem.py`

#### ReadFileTool
读取文件内容

```python
class ReadFileTool(Tool):
    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "读取文件内容"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"}
            },
            "required": ["path"]
        }

    async def execute(self, path: str) -> str:
        # 验证路径在工作空间内
        # 读取文件内容
        # 返回内容
```

#### WriteFileTool
写入文件内容

```python
class WriteFileTool(Tool):
    async def execute(
        self,
        path: str,
        content: str,
    ) -> str:
        # 验证路径
        # 写入文件
        # 返回成功消息
```

#### EditFileTool
编辑文件 (搜索替换)

```python
class EditFileTool(Tool):
    async def execute(
        self,
        path: str,
        old_text: str,
        new_text: str,
    ) -> str:
        # 读取文件
        # 搜索替换
        # 写回文件
```

#### ListDirTool
列出目录内容

```python
class ListDirTool(Tool):
    async def execute(self, path: str) -> str:
        # 列出目录内容
        # 返回格式化结果
```

### 4.2 Shell 工具

**文件**: `shell.py`

#### ExecTool
执行 Shell 命令

```python
class ExecTool(Tool):
    def __init__(
        self,
        workspace: Path,
        timeout: int = 30,
        allow_dangerous: bool = False,
    ):
        """
        Args:
            workspace: 工作空间
            timeout: 超时时间 (秒)
            allow_dangerous: 是否允许危险命令
        """

    async def execute(self, command: str) -> str:
        # 1. 危险命令检测
        if self.is_dangerous(command):
            raise ValueError("危险命令被阻止")

        # 2. 执行命令
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # 3. 等待完成 (带超时)
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=self.timeout
        )

        # 4. 返回结果
        return f"stdout: {stdout.decode()}\nstderr: {stderr.decode()}"

    # 危险命令列表
    DANGEROUS_COMMANDS = [
        "rm -rf",
        "format",
        "dd",
        "shutdown",
        "chmod -R 777 /",
        # ... 更多
    ]
```

### 4.3 Web 工具

**文件**: `web.py`

#### WebSearchTool
Web 搜索

```python
class WebSearchTool(Tool):
    def __init__(self, api_key: str = None):
        """
        Args:
            api_key: Brave Search API 密钥
        """

    async def execute(
        self,
        query: str,
        count: int = 5,
    ) -> str:
        # 调用 Brave Search API
        # 返回搜索结果
```

#### WebFetchTool
获取网页内容

```python
class WebFetchTool(Tool):
    async def execute(self, url: str) -> str:
        # 获取网页内容
        # 提取文本
        # 返回内容
```

### 4.4 记忆工具

**文件**: `memory_tool.py`

```python
class MemoryTool(Tool):
    def __init__(self, memory_store: MemoryStore):
        """初始化记忆工具"""

    async def execute(
        self,
        action: str,  # add, search, delete
        content: str = None,
        query: str = None,
    ) -> str:
        if action == "add":
            return self.memory_store.add_memory(content)
        elif action == "search":
            return self.memory_store.search(query)
        elif action == "delete":
            return self.memory_store.delete(content)
```

### 4.5 图片上传工具

**文件**: `image_uploader.py`

```python
class ImageUploader(Tool):
    def __init__(self, oss_config: dict = None):
        """
        Args:
            oss_config: OSS 配置
        """

    async def execute(
        self,
        file_path: str,
    ) -> str:
        # 上传图片
        # 返回 URL
```

---

## 5. 审计日志

### 5.1 文件审计日志

**文件**: `file_audit_logger.py`

#### 职责
- 记录工具调用
- 记录 AI 响应
- 审计追踪

#### 日志格式

```python
class FileAuditLogger:
    def record_tool_execution(
        self,
        session_id: str,
        tool_name: str,
        arguments: dict,
        result: str = None,
        error: str = None,
        duration_ms: int = None,
    ):
        """记录工具执行"""

    def record_ai_response(
        self,
        session_id: str,
        user_message: str,
        ai_response: str,
        duration_ms: int = None,
    ):
        """记录 AI 响应"""
```

### 5.2 工具调用对话历史

**文件**: `conversation_history.py`

#### 职责
- 记录工具调用对话
- 统计执行耗时
- 提供查询接口

---

## 6. 安全设计

### 6.1 工作空间限制

所有文件操作都限制在指定的工作空间内:

```python
def validate_path(self, path: str) -> Path:
    """验证路径在工作空间内"""
    resolved = (self.workspace / path).resolve()
    if not resolved.is_relative_to(self.workspace):
        raise ValueError("路径遍历攻击被阻止")
    return resolved
```

### 6.2 危险命令检测

```python
DANGEROUS_PATTERNS = [
    r"rm\s+(-[rf]+\s+)?/",
    r"format\s+",
    r"dd\s+if=",
    r"shutdown\s+",
    r"chmod\s+-R\s+777\s+/",
    r"mkfs\.",
    r">\s*/dev/sd",
]
```

### 6.3 超时控制

- Shell 命令默认超时：30 秒
- Web 请求超时：10 秒
- 文件操作超时：60 秒

### 6.4 输出截断

```python
MAX_OUTPUT_LENGTH = 10000

def truncate_output(output: str) -> str:
    if len(output) > MAX_OUTPUT_LENGTH:
        return output[:MAX_OUTPUT_LENGTH] + "\n... (输出已截断)"
    return output
```

---

## 7. 使用示例

### 7.1 基本使用

```python
from pathlib import Path
from backend.modules.tools.setup import register_all_tools

# 注册工具
workspace = Path("./workspace")
tools = register_all_tools(workspace=workspace)

# 执行工具
result = await tools.execute(
    tool_name="read_file",
    arguments={"path": "test.txt"},
)
print(result)
```

### 7.2 获取工具定义 (用于 LLM)

```python
definitions = tools.get_definitions()

# 传递给 LLM
response = await provider.chat_stream(
    messages=messages,
    tools=definitions,
)
```

### 7.3 创建自定义工具

```python
from backend.modules.tools import Tool

class MyCustomTool(Tool):
    @property
    def name(self) -> str:
        return "my_custom_tool"

    @property
    def description(self) -> str:
        return "我的自定义工具"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            },
            "required": ["input"]
        }

    async def execute(self, input: str) -> str:
        return f"处理结果：{input}"

# 注册
tools.register(MyCustomTool())
```

---

## 8. 错误处理

### 8.1 工具执行错误

```python
try:
    result = await tools.execute(tool_name, args)
except ValueError as e:
    # 参数错误
    return f"参数错误：{e}"
except FileNotFoundError as e:
    # 文件不存在
    return f"文件不存在：{e}"
except Exception as e:
    # 其他错误
    return f"工具执行失败：{e}"
```

### 8.2 错误通知

```python
# 发送错误通知到 WebSocket
await notify_tool_execution(
    session_id=session_id,
    tool_name=tool_name,
    arguments=arguments,
    error=str(e),
)
```

---

## 9. 性能优化

### 9.1 异步执行
- 所有工具使用异步实现
- 支持并发工具执行

### 9.2 结果缓存
- 只读操作可以缓存
- 写操作使缓存失效

### 9.3 批量操作
- 批量文件读取
- 批量 Web 请求

---

## 10. 待办事项 (TODO)

### 高优先级
- [ ] 添加更多文件操作工具
- [ ] 优化大文件处理
- [ ] 实现工具调用链

### 中优先级
- [ ] 添加数据库工具
- [ ] 添加 API 调用工具
- [ ] 实现工具组合

### 低优先级
- [ ] 工具性能监控
- [ ] 工具使用统计
- [ ] 自动化工具测试
