# 工具系统 (Tools)

> CountBot 的工具子系统，为 Agent 提供文件操作、Shell 命令、Web 抓取、记忆读写、截图、文件搜索等能力。

## 目录

- [设计理念](#设计理念)
- [架构概览](#架构概览)
- [工具基类](#工具基类)
- [工具注册表](#工具注册表)
- [内置工具](#内置工具)
  - [文件系统工具](#文件系统工具)
  - [Shell 工具](#shell-工具)
  - [Web 工具](#web-工具)
  - [记忆工具](#记忆工具)
  - [截图工具](#截图工具)
  - [文件搜索工具](#文件搜索工具)
  - [Spawn 工具](#spawn-工具)
  - [媒体发送工具](#媒体发送工具)
- [工具注册流程](#工具注册流程)
- [审计日志](#审计日志)
- [自定义工具开发](#自定义工具开发)
- [相关文件](#相关文件)

## 设计理念

1. **统一接口** — 所有工具继承 `Tool` 基类，实现 `name`、`description`、`parameters`、`execute`
2. **JSON Schema 参数** — 参数定义使用 JSON Schema，与 OpenAI Function Calling 兼容
3. **自动验证** — 执行前自动验证参数类型和约束
4. **审计追踪** — 每次工具调用记录到文件审计日志
5. **安全隔离** — 文件操作限制在工作空间内，Shell 命令有白名单/黑名单

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    ToolRegistry                          │
│                                                          │
│  register() → _tools: dict[name, Tool]                  │
│  get_definitions() → [{"type": "function", ...}]        │
│  execute(name, args) → str                              │
│                                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │read_file │ │write_file│ │edit_file │ │list_dir  │  │
│  ├──────────┤ ├──────────┤ ├──────────┤ ├──────────┤  │
│  │  exec    │ │web_fetch │ │screenshot│ │file_search│ │
│  ├──────────┤ ├──────────┤ ├──────────┤ ├──────────┤  │
│  │  spawn   │ │send_media│ │memory_*  │ │          │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│                                                          │
│  FileAuditLogger ← 记录每次调用                          │
└─────────────────────────────────────────────────────────┘
```

## 工具基类

**文件**: `backend/modules/tools/base.py`

所有工具必须继承 `Tool` 抽象基类：

```python
from backend.modules.tools.base import Tool

class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "工具描述，供 LLM 理解"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "参数说明"},
            },
            "required": ["param1"],
        }

    async def execute(self, param1: str, **kwargs) -> str:
        return f"执行结果: {param1}"
```

### 参数验证

`Tool` 基类提供递归参数验证，支持：

| 类型 | 验证 |
|------|------|
| `string` | 类型检查、`minLength`、`maxLength` |
| `integer` / `number` | 类型检查、`minimum`、`maximum` |
| `boolean` | 类型检查 |
| `array` | 类型检查、`items` 递归验证 |
| `object` | `required` 字段检查、`properties` 递归验证 |
| `enum` | 枚举值检查 |

### 工具定义输出

`get_definition()` 返回 OpenAI Function Calling 格式：

```json
{
  "type": "function",
  "function": {
    "name": "my_tool",
    "description": "工具描述",
    "parameters": { "type": "object", "properties": {...}, "required": [...] }
  }
}
```

## 工具注册表

**文件**: `backend/modules/tools/registry.py`

`ToolRegistry` 管理所有工具的注册、查询和执行。

```python
from backend.modules.tools.registry import ToolRegistry

registry = ToolRegistry()
registry.register(MyTool())

# 获取所有工具定义（传给 LLM）
definitions = registry.get_definitions()

# 执行工具（自动验证参数 + 审计日志）
result = await registry.execute("my_tool", {"param1": "hello"})
```

### 执行流程

```
execute(tool_name, arguments)
  │
  ├─ 查找工具实例
  ├─ 生成调用 ID (UUID)
  ├─ 记录审计日志（调用开始）
  ├─ validate_params(arguments)
  │   └─ 验证失败 → 返回错误字符串
  ├─ tool.execute(**arguments)
  ├─ 记录审计日志（调用结果）
  └─ 返回结果字符串
```

注意：`execute()` 不会抛出异常，而是返回错误字符串，确保 Agent Loop 不会中断。

## 内置工具

### 文件系统工具

**文件**: `backend/modules/tools/filesystem.py`

| 工具 | 说明 |
|------|------|
| `read_file` | 读取文件内容，支持行号范围 |
| `write_file` | 写入文件（创建或覆盖） |
| `edit_file` | 编辑文件（查找替换） |
| `list_dir` | 列出目录内容 |

所有文件系统工具共享 `WorkspaceValidator`，确保路径在工作空间内：

```python
class WorkspaceValidator:
    def validate_path(self, path: str) -> Path:
        """验证路径是否在工作空间内，返回绝对路径"""
        # restrict_to_workspace=True 时，拒绝工作空间外的路径
```

#### read_file

```json
{
  "path": "src/main.py",
  "start_line": 10,
  "end_line": 20
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `path` | string | ✅ | 文件路径（相对于工作空间） |
| `start_line` | integer | ❌ | 起始行号 |
| `end_line` | integer | ❌ | 结束行号 |

特殊行为：当读取技能文件（`skills/*/SKILL.md`）时，自动通过 `SkillsLoader` 加载。

#### write_file

```json
{
  "path": "output/result.txt",
  "content": "文件内容"
}
```

自动创建不存在的目录。

#### edit_file

```json
{
  "path": "src/main.py",
  "old_str": "旧代码",
  "new_str": "新代码"
}
```

使用精确字符串匹配进行替换。

#### list_dir

```json
{
  "path": "src",
  "recursive": false
}
```

### Shell 工具

**文件**: `backend/modules/tools/shell.py`

| 工具 | 说明 |
|------|------|
| `exec` | 执行 Shell 命令 |

```json
{
  "command": "ls -la",
  "working_dir": "src"
}
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `command` | string | ✅ | — | Shell 命令 |
| `working_dir` | string | ❌ | 工作空间根目录 | 工作目录（相对于工作空间） |

#### 安全机制

**危险命令检测**（`DANGEROUS_PATTERNS`）：

```python
DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+/",        # 删除根目录
    r"mkfs\.",               # 格式化磁盘
    r"dd\s+if=",             # 磁盘写入
    r":(){ :\|:& };:",       # Fork 炸弹
    r">\s*/dev/sd",          # 覆盖磁盘
    # ... 更多模式
]
```

**命令白名单**（可选）：启用后只允许匹配白名单的命令执行。

**工作空间隔离**：`restrict_to_workspace=True` 时，`cwd` 必须在工作空间内。

**超时控制**：默认 30 秒超时，可配置。

**输出截断**：超过 `max_output_length`（默认 10000 字符）时截断。

### Web 工具

**文件**: `backend/modules/tools/web.py`

| 工具 | 说明 | 依赖 |
|------|------|------|
| `web_fetch` | 抓取网页内容 | trafilatura / readability |

> 注意：`web.py` 中还定义了 `WebSearchTool`（基于 Brave Search API），但该工具未在 `register_all_tools()` 中注册，需要自行添加并配置 `BRAVE_API_KEY` 环境变量才能使用。

#### web_fetch

```json
{
  "url": "https://example.com",
  "extractMode": "markdown"
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `url` | string | ❌ | 单个 URL |
| `urls` | array | ❌ | 多个 URL（批量模式） |
| `extractMode` | string | ❌ | 提取模式：`text`（默认，纯文本）或 `markdown`（保留链接和结构） |
| `maxChars` | integer | ❌ | 每页最大字符数（默认 50000） |

`url` 和 `urls` 至少提供一个。

支持两种内容提取引擎：
- `trafilatura` — 优先使用，适合文章类内容
- `readability` — 备选方案

### 记忆工具

**文件**: `backend/modules/tools/memory_tool.py`

详见 [memory.md](./memory.md)。

| 工具 | 说明 |
|------|------|
| `memory_write` | 写入记忆 |
| `memory_search` | 搜索记忆 |
| `memory_read` | 读取记忆 |

### 截图工具

**文件**: `backend/modules/tools/screenshot.py`

| 工具 | 说明 |
|------|------|
| `screenshot` | 截取桌面或网页截图 |

支持两种模式：
- **桌面截图** — 使用系统截图命令（macOS: `screencapture`）
- **网页截图** — 使用 Playwright 无头浏览器

```json
{
  "type": "desktop",
  "region": "full"
}
```

截图保存到 `workspace/screenshots/` 目录。

### 文件搜索工具

**文件**: `backend/modules/tools/file_search.py`

| 工具 | 说明 |
|------|------|
| `file_search` | 跨平台文件搜索 |

```json
{
  "path": "/Users/user/Documents",
  "pattern": "*.pdf",
  "type": "file",
  "max_depth": 3,
  "limit": 20
}
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `path` | string | ✅ | — | 搜索目录 |
| `pattern` | string | ❌ | `*` | 文件名模式（支持 `*` `?` 通配符） |
| `type` | string | ❌ | `all` | 类型过滤：`file` / `dir` / `all` |
| `max_depth` | integer | ❌ | `-1` | 递归深度（-1 无限制） |
| `limit` | integer | ❌ | `20` | 最大结果数（1-100） |

### Spawn 工具

**文件**: `backend/modules/tools/spawn.py`

| 工具 | 说明 |
|------|------|
| `spawn` | 创建后台子代理执行任务 |

```json
{
  "task": "分析项目代码结构并生成报告",
  "label": "代码分析"
}
```

详见 [subagent.md](./subagent.md)。

### 媒体发送工具

**文件**: `backend/modules/tools/send_media.py`

| 工具 | 说明 |
|------|------|
| `send_media` | 发送文件/图片到聊天渠道 |

```json
{
  "file_paths": ["report.pdf", "chart.png"],
  "message": "项目报告"
}
```

支持格式：
- 图片：PNG, JPG, JPEG, GIF, BMP, WEBP
- 文档：PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX, TXT
- 压缩：ZIP, RAR, 7Z
- 媒体：MP3, MP4, AVI, MOV
- 数据：JSON, XML, CSV, MD

限制：
- 仅支持渠道会话（飞书/QQ/钉钉等）
- 单个文件最大 20MB
- QQ 渠道需要上传到 OSS 获取公网 URL

## 工具注册流程

**文件**: `backend/modules/tools/setup.py`

`register_all_tools()` 统一注册所有工具：

```
register_all_tools()
  │
  ├─ 1. 文件系统工具 (read_file, write_file, edit_file, list_dir)
  ├─ 2. Shell 工具 (exec)
  ├─ 3. Web 工具 (web_fetch)
  ├─ 4. Spawn 工具 (spawn) — 需要 SubagentManager
  ├─ 5. 媒体发送工具 (send_media) — 需要 ChannelManager
  ├─ 6. 截图工具 (screenshot)
  ├─ 7. 文件搜索工具 (file_search)
  └─ 8. 记忆工具 (memory_write, memory_search, memory_read) — 需要 MemoryStore
```

条件注册：部分工具需要对应的管理器实例才会注册。例如 `spawn` 需要 `SubagentManager`，`send_media` 需要 `ChannelManager`。

## 审计日志

**文件**: `backend/modules/tools/file_audit_logger.py`

每次工具调用记录到 `data/audit_logs/` 目录：

```json
{
  "call_id": "uuid",
  "tool_name": "exec",
  "arguments": {"command": "ls -la"},
  "session_id": "session-xxx",
  "timestamp": "2026-02-15T10:30:00",
  "status": "success",
  "duration_ms": 150,
  "result": "total 48\ndrwxr-xr-x ..."
}
```

可通过 `SecurityConfig.audit_log_enabled` 开关。

## 自定义工具开发

### 步骤

1. 创建工具类，继承 `Tool`：

```python
# backend/modules/tools/my_tool.py
from backend.modules.tools.base import Tool

class MyCustomTool(Tool):
    @property
    def name(self) -> str:
        return "my_custom_tool"

    @property
    def description(self) -> str:
        return "自定义工具描述"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "输入内容"},
            },
            "required": ["input"],
        }

    async def execute(self, input: str, **kwargs) -> str:
        # 实现工具逻辑
        return f"处理结果: {input}"
```

2. 在 `setup.py` 中注册：

```python
# 在 register_all_tools() 中添加
from backend.modules.tools.my_tool import MyCustomTool
tools.register(MyCustomTool())
```

### 注意事项

- `execute()` 必须返回 `str`，不要返回其他类型
- `execute()` 应该捕获异常并返回错误字符串，而不是抛出异常
- `parameters` 必须是合法的 JSON Schema
- `name` 必须全局唯一
- 工具描述要清晰，LLM 依赖描述来决定何时调用

## 相关文件

| 文件 | 说明 |
|------|------|
| `backend/modules/tools/base.py` | 工具抽象基类 |
| `backend/modules/tools/registry.py` | 工具注册表 |
| `backend/modules/tools/setup.py` | 工具统一注册 |
| `backend/modules/tools/filesystem.py` | 文件系统工具 |
| `backend/modules/tools/shell.py` | Shell 命令工具 |
| `backend/modules/tools/web.py` | Web 抓取工具 |
| `backend/modules/tools/memory_tool.py` | 记忆工具 |
| `backend/modules/tools/screenshot.py` | 截图工具 |
| `backend/modules/tools/file_search.py` | 文件搜索工具 |
| `backend/modules/tools/spawn.py` | 子代理创建工具 |
| `backend/modules/tools/send_media.py` | 媒体发送工具 |
| `backend/modules/tools/file_audit_logger.py` | 审计日志 |
| `backend/modules/tools/conversation_history.py` | 工具对话历史 |
| `backend/modules/tools/example_tool.py` | 示例工具 |
