# 子代理系统 (Subagent)

> CountBot 的后台子代理系统，支持创建独立的后台 Agent 处理耗时或复杂任务。

## 目录

- [设计理念](#设计理念)
- [架构概览](#架构概览)
- [核心组件](#核心组件)
  - [SubagentManager](#subagentmanager)
  - [SubagentTask](#subagenttask)
  - [SpawnTool](#spawntool)
- [任务生命周期](#任务生命周期)
- [子代理执行流程](#子代理执行流程)
- [工具权限](#工具权限)
- [通知机制](#通知机制)
- [API 接口](#api-接口)
- [使用场景](#使用场景)
- [配置参数](#配置参数)
- [相关文件](#相关文件)

## 设计理念

1. **异步执行** — 子代理在后台独立运行，不阻塞主对话
2. **独立上下文** — 每个子代理有独立的消息列表和工具注册表
3. **进度追踪** — 实时更新任务进度（0-100%）
4. **结果通知** — 任务完成后通过 WebSocket 通知前端
5. **资源隔离** — 子代理有独立的迭代限制和工具集

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    主 Agent Loop                         │
│                                                          │
│  用户: "分析项目代码结构并生成报告"                        │
│  Agent: spawn(task="分析项目代码结构并生成报告")          │
│       │                                                  │
│       ▼                                                  │
│  SpawnTool.execute()                                     │
│       │                                                  │
│       ▼                                                  │
│  SubagentManager.create_task() → task_id                │
│  SubagentManager.execute_task(task_id)                   │
│       │                                                  │
│       │  asyncio.create_task (后台运行)                   │
│       ▼                                                  │
│  ┌──────────────────────────────────────────────────┐   │
│  │              SubagentTask                         │   │
│  │                                                    │   │
│  │  独立的 Agent Loop:                                │   │
│  │  ├─ 系统提示词（子代理专用）                        │   │
│  │  ├─ 独立工具注册表                                  │   │
│  │  │  (read_file, write_file, edit_file,             │   │
│  │  │   list_dir, exec, web_fetch)                    │   │
│  │  ├─ max_iterations = 15                            │   │
│  │  └─ 进度追踪 (0% → 100%)                          │   │
│  │                                                    │   │
│  │  完成后: status=COMPLETED, result="..."            │   │
│  └──────────────────────────────────────────────────┘   │
│       │                                                  │
│       ▼                                                  │
│  WebSocket 通知前端: 任务完成                             │
└─────────────────────────────────────────────────────────┘
```

## 核心组件

### SubagentManager

**文件**: `backend/modules/agent/subagent.py`

子代理管理器，负责任务的创建、执行、查询和清理。

```python
from backend.modules.agent.subagent import SubagentManager

manager = SubagentManager(
    provider=llm_provider,
    workspace=Path("/workspace"),
    model="glm-5",
)
```

#### 方法列表

| 方法 | 说明 |
|------|------|
| `create_task(label, message, session_id)` | 创建任务，返回 task_id |
| `execute_task(task_id)` | 异步执行任务 |
| `cancel_task(task_id)` | 取消运行中的任务 |
| `get_task(task_id)` | 获取任务信息 |
| `list_tasks(status, session_id)` | 列出任务 |
| `get_running_tasks()` | 获取运行中的任务 |
| `delete_task(task_id)` | 删除任务 |
| `get_running_count()` | 运行中任务数量 |
| `get_stats()` | 统计信息 |
| `cleanup_old_tasks(max_age_hours)` | 清理过期任务 |
| `register_notification_callback(cb)` | 注册通知回调 |

### SubagentTask

**文件**: `backend/modules/agent/subagent.py`

任务数据类，封装单个子代理任务的状态。

```python
@dataclass
class SubagentTask:
    task_id: str          # UUID
    label: str            # 显示标签
    message: str          # 任务描述
    session_id: str       # 关联会话
    status: TaskStatus    # 状态
    progress: int         # 进度 (0-100)
    result: str           # 执行结果
    error: str            # 错误信息
    created_at: datetime
    completed_at: datetime
```

### TaskStatus

```python
class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

### SpawnTool

**文件**: `backend/modules/tools/spawn.py`

面向 Agent 的子代理创建工具。

```json
{
  "name": "spawn",
  "parameters": {
    "task": "分析项目代码结构并生成报告",
    "label": "代码分析"
  }
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task` | string | ✅ | 任务描述 |
| `label` | string | ❌ | 显示标签（默认取 task 前 30 字符） |

返回示例：`"子 Agent [代码分析] 已启动 (ID: uuid)。完成后我会通知你。"`

## 任务生命周期

```
create_task()          execute_task()         _run_task()
  │                      │                      │
  ▼                      ▼                      ▼
PENDING ──────────► RUNNING ──────────► COMPLETED
                       │                    │
                       │                    ├─► FAILED (异常)
                       │                    └─► CANCELLED (取消)
                       │
                       └─ cancel_task() ──► CANCELLED
```

## 子代理执行流程

### 1. 构建独立环境

子代理有独立的系统提示词和工具注册表：

```python
# 子代理专用系统提示词
system_prompt = _build_subagent_prompt(task)

# 独立工具注册表（比主 Agent 少）
tools = ToolRegistry()
tools.register(ReadFileTool(workspace))
tools.register(WriteFileTool(workspace))
tools.register(EditFileTool(workspace))
tools.register(ListDirTool(workspace))
tools.register(ExecTool(workspace, timeout=300, allow_dangerous=False))
tools.register(WebSearchTool())  # 可选
tools.register(WebFetchTool())   # 可选
```

### 2. 执行 Agent Loop

子代理运行独立的 ReAct 循环：

```
while iteration < 15:
    │
    ├─ provider.chat_stream(messages, tools)
    │   ├─ 收集 content
    │   └─ 收集 tool_calls
    │
    ├─ if tool_calls:
    │   ├─ 执行工具
    │   ├─ 添加 tool result
    │   └─ progress += 5 (最大 90%)
    │
    └─ else: break
```

### 3. 完成处理

```python
task.result = "".join(response_chunks)
task.status = TaskStatus.COMPLETED
task.progress = 100
task.completed_at = datetime.now()
```

## 工具权限

子代理可用的工具是主 Agent 的子集：

| 工具 | 主 Agent | 子代理 | 说明 |
|------|----------|--------|------|
| read_file | ✅ | ✅ | |
| write_file | ✅ | ✅ | |
| edit_file | ✅ | ✅ | |
| list_dir | ✅ | ✅ | |
| exec | ✅ | ✅ | 超时 300s（主 Agent 30s） |
| web_fetch | ✅ | ✅ | 可选 |
| spawn | ✅ | ❌ | 防止递归创建 |
| send_media | ✅ | ❌ | |
| screenshot | ✅ | ❌ | |
| memory_* | ✅ | ❌ | |

子代理的 Shell 工具超时设为 300 秒（主 Agent 默认 30 秒），适合执行耗时命令。

## 通知机制

### WebSocket 通知

子代理状态变化时通过 WebSocket 通知前端：

```python
manager.register_notification_callback(notify_callback)

# 通知事件类型
await _notify(task_id, "started")    # 任务开始
await _notify(task_id, "completed")  # 任务完成
await _notify(task_id, "failed")     # 任务失败
await _notify(task_id, "cancelled")  # 任务取消
```

### 前端展示

前端通过 WebSocket 接收任务状态更新，在 UI 中展示：
- 任务列表（运行中/已完成/失败）
- 进度条
- 任务结果

## API 接口

**文件**: `backend/api/tasks.py`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/tasks` | GET | 列出任务 |
| `/api/tasks/{id}` | GET | 获取任务详情 |
| `/api/tasks/{id}/cancel` | POST | 取消任务 |
| `/api/tasks/{id}` | DELETE | 删除任务 |
| `/api/tasks/stats` | GET | 任务统计 |

### 任务列表

```
GET /api/tasks?session_id=xxx&status=running
```

响应：
```json
[
  {
    "task_id": "uuid",
    "label": "代码分析",
    "message": "分析项目代码结构并生成报告",
    "status": "running",
    "progress": 45,
    "created_at": "2026-02-15T10:00:00",
    "completed_at": null
  }
]
```

### 任务统计

```
GET /api/tasks/stats
```

响应：
```json
{
  "total": 10,
  "running": 1,
  "completed": 8,
  "failed": 1,
  "cancelled": 0
}
```

## 使用场景

| 场景 | 示例 |
|------|------|
| 代码分析 | "分析整个项目的代码结构并生成文档" |
| 批量处理 | "将 data/ 目录下所有 CSV 转换为 JSON" |
| 长时间编译 | "编译项目并运行所有测试" |
| 数据采集 | "搜索并整理 Python 最佳实践资料" |
| 报告生成 | "分析日志文件并生成错误报告" |

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_iterations` | 15 | 子代理最大迭代次数 |
| Shell 超时 | 300s | 子代理 Shell 命令超时 |
| `max_age_hours` | 24h | 过期任务清理阈值 |
| `allow_dangerous` | false | 子代理不允许危险命令 |
| `restrict_to_workspace` | true | 限制在工作空间内 |

## 相关文件

| 文件 | 说明 |
|------|------|
| `backend/modules/agent/subagent.py` | SubagentManager + SubagentTask |
| `backend/modules/tools/spawn.py` | SpawnTool |
| `backend/modules/agent/task_manager.py` | 任务管理辅助 |
| `backend/api/tasks.py` | 任务 API |
| `backend/ws/task_notifications.py` | WebSocket 任务通知 |
